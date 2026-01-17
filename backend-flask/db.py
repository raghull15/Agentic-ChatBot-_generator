"""
MongoDB Database Connection Utility
Enhanced with connection pooling, retry logic, and structured logging
"""
import os
import time
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MongoDB connection string (uses same DB as auth-server by default)
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/chatbot-generator')

# Connection configuration
MAX_POOL_SIZE = 50
MIN_POOL_SIZE = 5
SERVER_SELECTION_TIMEOUT_MS = 5000
CONNECT_TIMEOUT_MS = 10000
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1  # seconds

# Global client instance
_client = None
_db = None


def get_database():
    """
    Get MongoDB database instance with connection pooling and retry logic.
    
    Features:
    - Connection pooling (50 max connections)
    - Exponential backoff retry (3 attempts)
    - Proper connection timeouts
    """
    global _client, _db
    
    if _db is not None:
        # Verify connection is still alive
        try:
            _client.admin.command('ping')
            return _db
        except Exception:
            logger.warning("MongoDB connection lost, attempting to reconnect...")
            _client = None
            _db = None
    
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            _client = MongoClient(
                MONGODB_URI,
                maxPoolSize=MAX_POOL_SIZE,
                minPoolSize=MIN_POOL_SIZE,
                serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
                connectTimeoutMS=CONNECT_TIMEOUT_MS,
                retryWrites=True,
                retryReads=True
            )
            
            # Test connection
            _client.admin.command('ping')
            
            # Parse database name from URI or use default
            db_name = MONGODB_URI.split('/')[-1].split('?')[0] or 'chatbot-generator'
            _db = _client[db_name]
            
            logger.info(f"Connected to MongoDB: {db_name} (pool: {MIN_POOL_SIZE}-{MAX_POOL_SIZE})")
            return _db
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            last_error = e
            retry_delay = RETRY_DELAY_BASE * (2 ** attempt)  # Exponential backoff
            
            if attempt < MAX_RETRIES - 1:
                logger.warning(
                    f"MongoDB connection attempt {attempt + 1}/{MAX_RETRIES} failed: {e}. "
                    f"Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
            else:
                logger.error(f"MongoDB connection failed after {MAX_RETRIES} attempts: {e}")
    
    logger.warning("Falling back to in-memory storage")
    return None


def get_agents_collection():
    """Get agents collection"""
    db = get_database()
    if db is None:
        return None
    return db['agents']


def get_token_usage_collection():
    """Get token usage collection for tracking per-query token consumption"""
    db = get_database()
    if db is None:
        return None
    return db['token_usage']


def get_users_collection():
    """Get users collection (same as auth-server)"""
    db = get_database()
    if db is None:
        return None
    return db['users']


def get_embed_tokens_collection():
    """Get embed tokens collection for secure token management"""
    db = get_database()
    if db is None:
        return None
    return db['embed_tokens']


def close_connection():
    """Close MongoDB connection gracefully"""
    global _client, _db
    if _client:
        try:
            _client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")
        finally:
            _client = None
            _db = None


def check_connection_health():
    """Check if MongoDB connection is healthy"""
    try:
        if _client is None:
            return False
        _client.admin.command('ping')
        return True
    except Exception:
        return False


# Alias for convenience
def get_db():
    """Alias for get_database()"""
    return get_database()

