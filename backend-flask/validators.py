"""
Input Validation Utilities
Provides sanitization and validation for user inputs to prevent injection attacks
"""
import re
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def validate_sql_connection_string(connection_string: str) -> Tuple[bool, Optional[str]]:
    """
    Validate SQL connection string format.
    
    Supports:
    - PostgreSQL: postgresql://user:pass@host:port/db
    - MySQL: mysql://user:pass@host:port/db
    - SQLite: sqlite:///path/to/db.sqlite
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not connection_string or not isinstance(connection_string, str):
        return False, "Connection string is required"
    
    connection_string = connection_string.strip()
    
    # Check for dangerous patterns (SQL injection attempts)
    dangerous_patterns = [
        r';\s*(DROP|DELETE|TRUNCATE|ALTER|CREATE|INSERT|UPDATE)',
        r'--',
        r'/\*.*\*/',
        r"'\s*OR\s*'",
        r'UNION\s+SELECT',
        r';\s*EXEC',
        r'\$\{',
        r'`.*`',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, connection_string, re.IGNORECASE):
            logger.warning(f"Dangerous pattern detected in SQL connection string: {pattern}")
            return False, "Invalid characters or patterns in connection string"
    
    # Validate URL format
    valid_schemes = ['postgresql', 'postgres', 'mysql', 'sqlite', 'mssql', 'oracle']
    
    try:
        parsed = urlparse(connection_string)
        
        if parsed.scheme not in valid_schemes:
            return False, f"Unsupported database type. Supported: {', '.join(valid_schemes)}"
        
        # SQLite doesn't need host
        if parsed.scheme != 'sqlite' and not parsed.hostname:
            return False, "Database host is required"
        
        # Validate port if specified
        if parsed.port is not None:
            if not (1 <= parsed.port <= 65535):
                return False, "Invalid port number (must be 1-65535)"
        
        # Check for path (database name)
        if parsed.scheme != 'sqlite' and len(parsed.path) <= 1:
            return False, "Database name is required"
            
    except Exception as e:
        logger.error(f"Failed to parse connection string: {e}")
        return False, "Invalid connection string format"
    
    return True, None


def validate_mongodb_connection_string(connection_string: str) -> Tuple[bool, Optional[str]]:
    """
    Validate MongoDB connection string format.
    
    Supports:
    - mongodb://user:pass@host:port/db
    - mongodb+srv://user:pass@cluster.mongodb.net/db
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not connection_string or not isinstance(connection_string, str):
        return False, "Connection string is required"
    
    connection_string = connection_string.strip()
    
    # Check for dangerous patterns
    dangerous_patterns = [
        r'\$where',
        r'\$function',
        r'\$accumulator',
        r'javascript:',
        r'\{\s*\$',
        r';\s*(db\.|use\s)',
        r'\$\{',
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, connection_string, re.IGNORECASE):
            logger.warning(f"Dangerous pattern detected in MongoDB connection string: {pattern}")
            return False, "Invalid characters or patterns in connection string"
    
    # Validate URL format
    valid_schemes = ['mongodb', 'mongodb+srv']
    
    try:
        parsed = urlparse(connection_string)
        
        if parsed.scheme not in valid_schemes:
            return False, f"Invalid MongoDB URI scheme. Expected: {', '.join(valid_schemes)}"
        
        if not parsed.hostname:
            return False, "MongoDB host is required"
        
        # Validate port if specified (not for SRV)
        if parsed.port is not None and parsed.scheme == 'mongodb':
            if not (1 <= parsed.port <= 65535):
                return False, "Invalid port number (must be 1-65535)"
                
    except Exception as e:
        logger.error(f"Failed to parse MongoDB connection string: {e}")
        return False, "Invalid MongoDB connection string format"
    
    return True, None


def validate_database_name(db_name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate database name.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not db_name or not isinstance(db_name, str):
        return False, "Database name is required"
    
    db_name = db_name.strip()
    
    # Check length
    if len(db_name) > 63:
        return False, "Database name must be 63 characters or less"
    
    if len(db_name) < 1:
        return False, "Database name cannot be empty"
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', db_name):
        return False, "Database name must start with a letter and contain only letters, numbers, underscores, and hyphens"
    
    # Check for reserved words
    reserved_words = ['admin', 'local', 'config', 'system', 'null', 'undefined']
    if db_name.lower() in reserved_words:
        return False, f"'{db_name}' is a reserved database name"
    
    return True, None


def validate_table_names(tables_str: str) -> Tuple[bool, Optional[str], Optional[list]]:
    """
    Validate comma-separated table/collection names.
    
    Returns:
        Tuple of (is_valid, error_message, parsed_tables)
    """
    if not tables_str or not isinstance(tables_str, str):
        return True, None, None  # Empty is valid (means all tables)
    
    tables_str = tables_str.strip()
    if not tables_str:
        return True, None, None
    
    tables = [t.strip() for t in tables_str.split(',') if t.strip()]
    
    if not tables:
        return True, None, None
    
    # Validate each table name
    for table in tables:
        # Check for SQL injection patterns
        if re.search(r'[;\'"\\`\-\*]', table):
            return False, f"Invalid characters in table name: {table}", None
        
        # Check valid table name format
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
            return False, f"Invalid table name format: {table}", None
        
        # Check length
        if len(table) > 128:
            return False, f"Table name too long: {table}", None
    
    return True, None, tables


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize a string input by removing dangerous characters.
    
    Args:
        value: Input string
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not value or not isinstance(value, str):
        return ""
    
    # Truncate to max length
    value = value[:max_length]
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Remove control characters except newlines and tabs
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', value)
    
    return value.strip()


def validate_sample_limit(limit: any) -> Tuple[bool, Optional[str], int]:
    """
    Validate sample limit parameter.
    
    Returns:
        Tuple of (is_valid, error_message, validated_limit)
    """
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        return False, "Sample limit must be a number", 1000
    
    if limit < 1:
        return False, "Sample limit must be at least 1", 1000
    
    if limit > 100000:
        return False, "Sample limit cannot exceed 100,000", 1000
    
    return True, None, limit
