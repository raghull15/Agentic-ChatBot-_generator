"""
Audit Service - Track and query admin actions
Provides audit logging for compliance and security
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from billing.models import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Service for managing audit logs"""
    
    @staticmethod
    def log_action(
        db: Session,
        admin_id: str,
        admin_email: str,
        action: str,
        target_type: str = None,
        target_id: str = None,
        details: dict = None,
        ip_address: str = None,
        user_agent: str = None
    ) -> AuditLog:
        """
        Log an admin action
        
        Args:
            db: Database session
            admin_id: MongoDB user ID of admin
            admin_email: Email of admin
            action: Action type (ADD_CREDITS, UPDATE_SETTING, etc.)
            target_type: Type of target (user, setting, plan, etc.)
            target_id: ID of target
            details: Additional details as dict
            ip_address: IP address of admin
            user_agent: User agent string
            
        Returns:
            Created AuditLog object
        """
        log = AuditLog(
            admin_user_id=admin_id,
            admin_email=admin_email,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=json.dumps(details) if details else None,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        db.add(log)
        db.commit()
        
        logger.info(f"Audit log: {action} by {admin_email} on {target_type}:{target_id}")
        return log
    
    @staticmethod
    def get_recent_logs(
        db: Session,
        limit: int = 100,
        admin_id: str = None,
        action: str = None,
        target_type: str = None,
        days: int = None
    ) -> List[AuditLog]:
        """
        Get recent audit logs with optional filtering
        
        Args:
            db: Database session
            limit: Maximum number of logs to return
            admin_id: Filter by admin user ID
            action: Filter by action type
            target_type: Filter by target type
            days: Only get logs from last N days
            
        Returns:
            List of AuditLog objects
        """
        query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
        
        # Apply filters
        if admin_id:
            query = query.filter(AuditLog.admin_user_id == admin_id)
        
        if action:
            query = query.filter(AuditLog.action == action)
        
        if target_type:
            query = query.filter(AuditLog.target_type == target_type)
        
        if days:
            cutoff = datetime.utcnow() - timedelta(days=days)
            query = query.filter(AuditLog.timestamp >= cutoff)
        
        return query.limit(limit).all()
    
    @staticmethod
    def get_logs_for_target(db: Session, target_type: str, target_id: str, limit: int = 50) -> List[AuditLog]:
        """
        Get audit logs for a specific target
        
        Args:
            db: Database session
            target_type: Type of target (user, setting, plan)
            target_id: ID of target
            limit: Maximum logs to return
            
        Returns:
            List of AuditLog objects
        """
        return db.query(AuditLog).filter(
            AuditLog.target_type == target_type,
            AuditLog.target_id == target_id
        ).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    @staticmethod
    def get_admin_activity(db: Session, admin_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get summary of admin's activity
        
        Args:
            db: Database session
            admin_id: MongoDB user ID of admin
            days: Number of days to analyze
            
        Returns:
            Dict with activity summary
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        logs = db.query(AuditLog).filter(
            AuditLog.admin_user_id == admin_id,
            AuditLog.timestamp >= cutoff
        ).all()
        
        # Aggregate by action type
        action_counts = {}
        for log in logs:
            action_counts[log.action] = action_counts.get(log.action, 0) + 1
        
        return {
            "total_actions": len(logs),
            "by_action": action_counts,
            "first_action": logs[-1].timestamp if logs else None,
            "last_action": logs[0].timestamp if logs else None
        }
    
    @staticmethod
    def log_to_dict(log: AuditLog) -> dict:
        """Convert AuditLog to dictionary"""
        details = None
        if log.details:
            try:
                details = json.loads(log.details)
            except:
                details = log.details
        
        return {
            "id": log.id,
            "admin_user_id": log.admin_user_id,
            "admin_email": log.admin_email,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": details,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None
        }
