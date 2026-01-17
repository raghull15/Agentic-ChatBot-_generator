"""
Token Service - Converts tokens to credits
Reads tokens_per_credit from database settings
"""
from decimal import Decimal, ROUND_UP
import logging

logger = logging.getLogger(__name__)

# Default conversion rate (used as fallback)
DEFAULT_TOKENS_PER_CREDIT = 1000

# Maximum tokens allowed per single run (guardrail)
MAX_TOKENS_PER_RUN = 4000

# Cache for settings
_cached_tokens_per_credit = None


def get_tokens_per_credit(db=None) -> int:
    """
    Get tokens per credit conversion rate from database settings.
    Falls back to default if database unavailable.
    
    Args:
        db: MongoDB database instance (optional, will get fresh if not provided)
        
    Returns:
        Tokens per credit rate
    """
    global _cached_tokens_per_credit
    
    try:
        # Try to get from database
        if db is not None:
            from billing.settings_service_mongo import SettingsServiceMongo
            return SettingsServiceMongo.get_tokens_per_credit(db)
        
        # Try to get fresh db connection
        from billing.service_factory import USE_MONGODB, get_database
        if USE_MONGODB:
            db = get_database()
            from billing.settings_service_mongo import SettingsServiceMongo
            rate = SettingsServiceMongo.get_tokens_per_credit(db)
            _cached_tokens_per_credit = rate
            return rate
        else:
            from billing.settings_service import SettingsService
            from billing.database import get_db_session
            with get_db_session() as db:
                rate = SettingsService.get_tokens_per_credit(db)
                _cached_tokens_per_credit = rate
                return rate
    except Exception as e:
        logger.warning(f"Failed to get tokens_per_credit from settings: {e}. Using default: {DEFAULT_TOKENS_PER_CREDIT}")
        return _cached_tokens_per_credit or DEFAULT_TOKENS_PER_CREDIT


def tokens_to_credits(tokens: int, db=None) -> Decimal:
    """
    Convert token count to credits.
    Always rounds UP to ensure we don't undercharge.
    
    Args:
        tokens: Number of tokens used
        db: Optional database connection for getting conversion rate
        
    Returns:
        Credits as Decimal with 4 decimal precision
    """
    if tokens <= 0:
        return Decimal('0.0000')
    
    tokens_per_credit = get_tokens_per_credit(db)
    credits = Decimal(tokens) / Decimal(tokens_per_credit)
    # Round up to 4 decimal places
    return credits.quantize(Decimal('0.0001'), rounding=ROUND_UP)


def credits_to_tokens(credits: Decimal, db=None) -> int:
    """
    Convert credits to approximate token count.
    
    Args:
        credits: Number of credits
        db: Optional database connection
        
    Returns:
        Approximate token count
    """
    tokens_per_credit = get_tokens_per_credit(db)
    return int(credits * tokens_per_credit)


def estimate_max_tokens(query_length: int, k: int = 4) -> int:
    """
    Estimate maximum tokens for a query.
    Used for pre-flight credit check.
    
    Args:
        query_length: Length of user query
        k: Number of documents to retrieve
        
    Returns:
        Estimated max tokens
    """
    # Rough estimates:
    # - Query tokens: ~1.3 tokens per character
    # - System prompt: ~100 tokens
    # - RAG context: ~200 tokens per document chunk
    # - Response: ~500 tokens average
    
    query_tokens = int(query_length * 0.25)  # ~4 chars per token
    system_tokens = 100
    context_tokens = k * 200
    response_tokens = 500
    
    estimated = query_tokens + system_tokens + context_tokens + response_tokens
    
    # Cap at MAX_TOKENS_PER_RUN
    return min(estimated, MAX_TOKENS_PER_RUN)


def estimate_credits_needed(query_length: int, k: int = 4, db=None) -> Decimal:
    """
    Estimate credits needed for a query.
    
    Args:
        query_length: Length of user query
        k: Number of documents to retrieve
        db: Optional database connection
        
    Returns:
        Estimated credits
    """
    estimated_tokens = estimate_max_tokens(query_length, k)
    return tokens_to_credits(estimated_tokens, db)

