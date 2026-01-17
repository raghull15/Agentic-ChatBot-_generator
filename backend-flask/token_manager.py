"""
Token Manager
Handles embed token CRUD operations, validation, and security checks
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import fnmatch


class TokenManager:
    """Manages embed tokens with security features"""
    
    def __init__(self, db):
        """
        Initialize TokenManager with database connection
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
        self.collection = db['embed_tokens'] if db is not None else None
    
    def create_token(
        self,
        agent_key: str,
        workspace_id: str,
        allowed_domains: List[str] = None,
        rate_limit: int = 20,
        monthly_quota: int = 10000,
        expires_in_days: int = None
    ) -> Dict[str, Any]:
        """
        Create a new embed token
        
        Args:
            agent_key: The agent this token is for
            workspace_id: User/workspace ID who owns the agent
            allowed_domains: List of allowed domains (supports wildcards like *.example.com)
            rate_limit: Requests per minute (default 20)
            monthly_quota: Monthly request limit (default 10000)
            expires_in_days: Optional expiration in days
        
        Returns:
            Token document
        """
        if self.collection is None:
            return {"success": False, "error": "Database not available"}
        
        public_token = str(uuid.uuid4()).replace('-', '')[:24]
        now = datetime.now()
        
        # Calculate quota reset (first of next month or 30 days rolling)
        next_month = now.replace(day=1) + timedelta(days=32)
        quota_reset_at = next_month.replace(day=1)
        
        token_doc = {
            "public_token": public_token,
            "agent_key": agent_key,
            "workspace_id": workspace_id,
            "allowed_domains": allowed_domains or ["*"],  # Default allow all
            "rate_limit": rate_limit,
            "monthly_quota": monthly_quota,
            "monthly_usage": 0,
            "quota_reset_at": quota_reset_at,
            "status": "active",  # active | suspended | revoked
            "expires_at": now + timedelta(days=expires_in_days) if expires_in_days else None,
            "created_at": now,
            "last_used_at": None,
            "created_by": workspace_id
        }
        
        self.collection.insert_one(token_doc)
        
        return {
            "success": True,
            "public_token": public_token,
            "token": token_doc
        }
    
    def get_token(self, public_token: str) -> Optional[Dict[str, Any]]:
        """Get token by public token string"""
        if self.collection is None:
            return None
        
        return self.collection.find_one({"public_token": public_token})
    
    def validate_token(self, public_token: str, origin: str = None) -> Dict[str, Any]:
        """
        Validate token and check all security constraints
        
        Args:
            public_token: The token to validate
            origin: Request origin header (for domain validation)
        
        Returns:
            Validation result with token data or error
        """
        token = self.get_token(public_token)
        
        if not token:
            return {
                "valid": False,
                "error_code": "INVALID_TOKEN",
                "error_message": "Token not found"
            }
        
        # Check status
        if token.get("status") == "suspended":
            return {
                "valid": False,
                "error_code": "TOKEN_SUSPENDED",
                "error_message": "Token has been suspended"
            }
        
        if token.get("status") == "revoked":
            return {
                "valid": False,
                "error_code": "TOKEN_REVOKED",
                "error_message": "Token has been revoked"
            }
        
        # Check expiration
        expires_at = token.get("expires_at")
        if expires_at and datetime.now() > expires_at:
            return {
                "valid": False,
                "error_code": "TOKEN_EXPIRED",
                "error_message": "Token has expired"
            }
        
        # Check domain allowlist
        if origin:
            if not self._check_domain_allowed(origin, token.get("allowed_domains", ["*"])):
                return {
                    "valid": False,
                    "error_code": "DOMAIN_NOT_ALLOWED",
                    "error_message": f"Origin '{origin}' is not in the allowed domains list"
                }
        
        # Check monthly quota
        self._reset_quota_if_needed(token)
        if token.get("monthly_usage", 0) >= token.get("monthly_quota", 10000):
            return {
                "valid": False,
                "error_code": "MONTHLY_QUOTA_EXCEEDED",
                "error_message": "Monthly request quota exceeded"
            }
        
        return {
            "valid": True,
            "token": token
        }
    
    def _check_domain_allowed(self, origin: str, allowed_domains: List[str]) -> bool:
        """
        Check if origin is in allowed domains list
        Supports wildcards like *.example.com
        """
        if "*" in allowed_domains:
            return True
        
        # Extract domain from origin (remove protocol)
        domain = origin.replace("http://", "").replace("https://", "").split("/")[0]
        
        # Allow localhost for development
        if domain.startswith("localhost") or domain.startswith("127.0.0.1"):
            return True
        
        for allowed in allowed_domains:
            # Exact match
            if domain == allowed:
                return True
            # Wildcard match (*.example.com matches sub.example.com)
            if allowed.startswith("*."):
                pattern = allowed[2:]  # Remove *.
                if domain.endswith(pattern) or domain == pattern[1:]:
                    return True
        
        return False
    
    def _reset_quota_if_needed(self, token: Dict[str, Any]):
        """Reset monthly usage if past reset date"""
        quota_reset_at = token.get("quota_reset_at")
        
        if quota_reset_at and datetime.now() > quota_reset_at:
            # Reset quota
            now = datetime.now()
            next_month = now.replace(day=1) + timedelta(days=32)
            new_reset_at = next_month.replace(day=1)
            
            self.collection.update_one(
                {"public_token": token["public_token"]},
                {
                    "$set": {
                        "monthly_usage": 0,
                        "quota_reset_at": new_reset_at
                    }
                }
            )
            token["monthly_usage"] = 0
            token["quota_reset_at"] = new_reset_at
    
    def increment_usage(self, public_token: str):
        """Increment usage counter and update last_used_at"""
        if self.collection is None:
            return
        
        self.collection.update_one(
            {"public_token": public_token},
            {
                "$inc": {"monthly_usage": 1},
                "$set": {"last_used_at": datetime.now()}
            }
        )
    
    def update_token(
        self,
        public_token: str,
        allowed_domains: List[str] = None,
        rate_limit: int = None,
        monthly_quota: int = None,
        status: str = None
    ) -> Dict[str, Any]:
        """Update token settings"""
        if self.collection is None:
            return {"success": False, "error": "Database not available"}
        
        updates = {}
        if allowed_domains is not None:
            updates["allowed_domains"] = allowed_domains
        if rate_limit is not None:
            updates["rate_limit"] = rate_limit
        if monthly_quota is not None:
            updates["monthly_quota"] = monthly_quota
        if status is not None:
            updates["status"] = status
        
        if not updates:
            return {"success": False, "error": "No updates provided"}
        
        result = self.collection.update_one(
            {"public_token": public_token},
            {"$set": updates}
        )
        
        return {
            "success": result.modified_count > 0,
            "modified": result.modified_count
        }
    
    def suspend_token(self, public_token: str) -> Dict[str, Any]:
        """Suspend a token"""
        return self.update_token(public_token, status="suspended")
    
    def revoke_token(self, public_token: str) -> Dict[str, Any]:
        """Revoke a token permanently"""
        return self.update_token(public_token, status="revoked")
    
    def activate_token(self, public_token: str) -> Dict[str, Any]:
        """Re-activate a suspended token"""
        return self.update_token(public_token, status="active")
    
    def delete_token(self, public_token: str) -> Dict[str, Any]:
        """Delete a token completely"""
        if self.collection is None:
            return {"success": False, "error": "Database not available"}
        
        result = self.collection.delete_one({"public_token": public_token})
        
        return {
            "success": result.deleted_count > 0,
            "deleted": result.deleted_count
        }
    
    def get_tokens_for_agent(self, agent_key: str) -> List[Dict[str, Any]]:
        """Get all tokens for an agent"""
        if self.collection is None:
            return []
        
        return list(self.collection.find({"agent_key": agent_key}))
    
    def get_tokens_for_workspace(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Get all tokens for a workspace/user"""
        if self.collection is None:
            return []
        
        return list(self.collection.find({"workspace_id": workspace_id}))
    
    def get_usage_stats(self, public_token: str) -> Dict[str, Any]:
        """Get usage statistics for a token"""
        token = self.get_token(public_token)
        
        if not token:
            return {"success": False, "error": "Token not found"}
        
        return {
            "success": True,
            "usage": {
                "monthly_usage": token.get("monthly_usage", 0),
                "monthly_quota": token.get("monthly_quota", 10000),
                "quota_reset_at": token.get("quota_reset_at").isoformat() if token.get("quota_reset_at") else None,
                "rate_limit": token.get("rate_limit", 20),
                "last_used_at": token.get("last_used_at").isoformat() if token.get("last_used_at") else None
            }
        }
