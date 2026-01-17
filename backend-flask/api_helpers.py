"""
API Response Helpers
Standardized response envelope for all API endpoints
"""
import uuid
from datetime import datetime
from flask import jsonify, request


def generate_request_id():
    """Generate unique request ID for tracing"""
    return str(uuid.uuid4())[:8]


def api_success(data, metadata=None, status=200):
    """
    Create standardized success response
    
    Args:
        data: The response payload
        metadata: Optional metadata (response_time, tokens, etc.)
        status: HTTP status code (default 200)
    
    Returns:
        Flask response tuple (response, status)
    """
    response = {
        "success": True,
        "data": data,
        "metadata": metadata or {},
        "error": None,
        "request_id": generate_request_id(),
        "timestamp": datetime.now().isoformat(),
        "api_version": "v1"
    }
    return jsonify(response), status


def api_error(code, message, status=400, metadata=None):
    """
    Create standardized error response
    
    Args:
        code: Error code (e.g., 'INVALID_TOKEN', 'RATE_LIMIT_EXCEEDED')
        message: Human-readable error message
        status: HTTP status code (default 400)
        metadata: Optional metadata
    
    Returns:
        Flask response tuple (response, status)
    """
    response = {
        "success": False,
        "data": None,
        "metadata": metadata or {},
        "error": {
            "code": code,
            "message": message
        },
        "request_id": generate_request_id(),
        "timestamp": datetime.now().isoformat(),
        "api_version": "v1"
    }
    return jsonify(response), status


# Standard error codes
class ErrorCodes:
    # Token errors
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_SUSPENDED = "TOKEN_SUSPENDED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    
    # Rate limiting
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    MONTHLY_QUOTA_EXCEEDED = "MONTHLY_QUOTA_EXCEEDED"
    
    # Domain/CORS
    DOMAIN_NOT_ALLOWED = "DOMAIN_NOT_ALLOWED"
    ORIGIN_REQUIRED = "ORIGIN_REQUIRED"
    
    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    MISSING_QUERY = "MISSING_QUERY"
    INVALID_FEEDBACK_TYPE = "INVALID_FEEDBACK_TYPE"
    
    # Server errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    AGENT_LOAD_ERROR = "AGENT_LOAD_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"


# Helper for adding rate limit headers
def add_rate_limit_headers(response, rate_info):
    """Add rate limit headers to response"""
    response.headers['X-RateLimit-Limit'] = str(rate_info.get('limit', 20))
    response.headers['X-RateLimit-Remaining'] = str(rate_info.get('remaining', 0))
    response.headers['X-RateLimit-Reset'] = rate_info.get('reset_at', '')
    return response
