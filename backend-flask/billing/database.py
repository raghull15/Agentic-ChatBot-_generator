"""
PostgreSQL Database Connection for Billing
- Connection pooling with SQLAlchemy
- Auto-creates database and tables on startup (idempotent)
- Connection string from DATABASE_URL environment variable (REQUIRED)
- NO SQLite fallback - PostgreSQL only
"""
import os
import logging
from urllib.parse import urlparse, urlunparse
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

# Global engine and session factory
_engine = None
_SessionLocal = None


def _ensure_database_exists(database_url: str) -> bool:
    """
    Ensure the target PostgreSQL database exists.
    Creates it if it doesn't exist.
    
    Args:
        database_url: Full PostgreSQL connection string
        
    Returns:
        True if database exists or was created, False on error
    """
    try:
        # Parse the database URL
        parsed = urlparse(database_url)
        
        if not parsed.scheme.startswith('postgresql'):
            raise ValueError(f"Only PostgreSQL is supported. Got: {parsed.scheme}")
        
        target_db = parsed.path.lstrip('/')
        if not target_db:
            raise ValueError("No database name specified in DATABASE_URL")
        
        # Create connection URL to 'postgres' database (default admin db)
        admin_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            '/postgres',  # Connect to default postgres database
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        
        # Connect to postgres database to check/create target database
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        
        with admin_engine.connect() as conn:
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": target_db}
            )
            exists = result.fetchone() is not None
            
            if not exists:
                logger.info(f"Creating database '{target_db}'...")
                # Use proper SQL escaping for database name
                conn.execute(text(f'CREATE DATABASE "{target_db}"'))
                logger.info(f"Database '{target_db}' created successfully")
            else:
                logger.debug(f"Database '{target_db}' already exists")
        
        admin_engine.dispose()
        return True
        
    except Exception as e:
        logger.error(f"Failed to ensure database exists: {e}")
        raise


def get_engine():
    """Get or create SQLAlchemy engine with connection pooling"""
    global _engine, DATABASE_URL
    
    if _engine is not None:
        return _engine
    
    # Enforce DATABASE_URL - no fallback
    if not DATABASE_URL:
        logger.error("=" * 60)
        logger.error("DATABASE_URL NOT SET")
        logger.error("PostgreSQL connection required but DATABASE_URL is missing")
        logger.error("=" * 60)
        raise RuntimeError(
            "DATABASE_URL environment variable is required.\n"
            "Example: DATABASE_URL=postgresql://user:password@localhost:5432/billing_db"
        )
    
    # Validate PostgreSQL URL
    parsed = urlparse(DATABASE_URL)
    if not parsed.scheme.startswith('postgresql'):
        logger.error(f"Invalid database scheme: {parsed.scheme}")
        raise RuntimeError(
            f"Only PostgreSQL is supported. Got: {parsed.scheme}\n"
            "Example: DATABASE_URL=postgresql://user:password@localhost:5432/billing_db"
        )
    
    # Log connection attempt details (without password)
    db_host = parsed.hostname or 'localhost'
    db_port = parsed.port or 5432
    db_name = parsed.path.lstrip('/') if parsed.path else 'unknown'
    db_user = parsed.username or 'unknown'
    
    logger.info("=" * 60)
    logger.info("POSTGRESQL CONNECTION ATTEMPT")
    logger.info(f"  Host: {db_host}")
    logger.info(f"  Port: {db_port}")
    logger.info(f"  Database: {db_name}")
    logger.info(f"  User: {db_user}")
    logger.info("=" * 60)
    
    try:
        # Ensure database exists (auto-create if needed)
        _ensure_database_exists(DATABASE_URL)
        
        # Create PostgreSQL engine with connection pooling
        _engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False
        )
        
        # Test connection
        with _engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("=" * 60)
        logger.info("✓ POSTGRESQL CONNECTED SUCCESSFULLY")
        logger.info(f"  Database: {db_name} @ {db_host}:{db_port}")
        logger.info("=" * 60)
        return _engine
        
    except Exception as e:
        error_msg = str(e)
        logger.error("=" * 60)
        logger.error("✗ POSTGRESQL CONNECTION FAILED")
        logger.error(f"  Host: {db_host}:{db_port}")
        logger.error(f"  Database: {db_name}")
        logger.error(f"  User: {db_user}")
        logger.error("-" * 60)
        
        # Provide helpful error messages
        if "password authentication failed" in error_msg.lower():
            logger.error("  ERROR: Password authentication failed")
            logger.error("  FIX: Check your DATABASE_URL password is correct")
        elif "could not connect" in error_msg.lower() or "connection refused" in error_msg.lower():
            logger.error("  ERROR: Cannot connect to PostgreSQL server")
            logger.error("  FIX: Ensure PostgreSQL is running and accessible")
        elif "database" in error_msg.lower() and "does not exist" in error_msg.lower():
            logger.error("  ERROR: Database does not exist")
            logger.error("  FIX: Create the database or check the database name")
        else:
            logger.error(f"  ERROR: {error_msg}")
        
        logger.error("=" * 60)

        _engine = None
        raise


def get_session_factory():
    """Get or create scoped session factory"""
    global _SessionLocal
    
    if _SessionLocal is not None:
        return _SessionLocal
    
    engine = get_engine()
    if engine is None:
        return None
    
    _SessionLocal = scoped_session(
        sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=True,  # Enable autoflush to prevent stale data in credit checks
            expire_on_commit=True  # Expire objects on commit to force refresh
        )
    )
    
    return _SessionLocal


# Alias for convenience
SessionLocal = property(lambda self: get_session_factory())


def init_db():
    """
    Initialize database - creates all tables if they don't exist.
    Seeds default settings and plans only if tables are empty.
    This is idempotent and safe to call multiple times.
    """
    engine = get_engine()
    if engine is None:
        logger.warning("Cannot initialize billing DB - no database connection")
        return False
    
    try:
        # Import models to ensure they're registered with Base
        from billing.models import Base
        
        # Create all tables (idempotent - won't recreate existing tables)
        Base.metadata.create_all(bind=engine)
        
        logger.info("Billing database tables initialized successfully")
        
        # Seed default data only if tables are empty
        _seed_default_data(engine)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize billing database: {e}")
        return False


def _seed_default_data(engine):
    """
    Seed default settings and plans only if they don't exist.
    Called after table creation to ensure fresh databases have data.
    """
    import json
    from sqlalchemy.orm import sessionmaker
    from billing.models import BillingSetting, SubscriptionPlan
    
    # Default settings
    DEFAULT_SETTINGS = {
        'tokens_per_credit': {'value': 1000, 'description': 'Tokens per 1 credit'},
        'daily_credit_cap': {'value': 100, 'description': 'Max credits per user per day'},
        'free_credits': {'value': 10, 'description': 'Credits for new users'},
        'max_tokens_per_query': {'value': 4000, 'description': 'Hard limit per query'},
        'low_credit_threshold': {'value': 50, 'description': 'Threshold for low credit notification'},
        'bot_creation_cost': {'value': 50, 'description': 'Credits required to create a new bot'},
        'demo_bot_time_limit_hours': {'value': 24, 'description': 'Demo bot expiry time in hours'},
        'demo_bot_credit_limit': {'value': 10, 'description': 'Max credits for demo bot queries'},
    }
    
    # Default plans
    DEFAULT_PLANS = [
        {'id': 'starter', 'name': 'Starter', 'description': 'Perfect for individuals', 
         'amount_paise': 49900, 'credits': 500, 'bonus_credits': 0, 'sort_order': 1},
        {'id': 'pro', 'name': 'Pro', 'description': 'For small teams and projects', 
         'amount_paise': 99900, 'credits': 1000, 'bonus_credits': 200, 'sort_order': 2},
        {'id': 'business', 'name': 'Business', 'description': 'For large-scale operations', 
         'amount_paise': 199900, 'credits': 2000, 'bonus_credits': 500, 'sort_order': 3},
    ]
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Seed settings only if none exist
        settings_count = session.query(BillingSetting).count()
        if settings_count == 0:
            logger.info("Seeding default billing settings...")
            for key, info in DEFAULT_SETTINGS.items():
                setting = BillingSetting(
                    key=key,
                    value=json.dumps(info['value']),
                    description=info['description']
                )
                session.add(setting)
            session.commit()
            logger.info(f"Seeded {len(DEFAULT_SETTINGS)} default settings")
        else:
            logger.debug(f"Settings already exist ({settings_count}), skipping seed")
        
        # Seed plans only if none exist
        plans_count = session.query(SubscriptionPlan).count()
        if plans_count == 0:
            logger.info("Seeding default subscription plans...")
            for plan_data in DEFAULT_PLANS:
                from decimal import Decimal
                plan = SubscriptionPlan(
                    id=plan_data['id'],
                    name=plan_data['name'],
                    description=plan_data['description'],
                    amount_paise=plan_data['amount_paise'],
                    credits=Decimal(str(plan_data['credits'])),
                    bonus_credits=Decimal(str(plan_data['bonus_credits'])),
                    is_active=True,
                    sort_order=plan_data['sort_order']
                )
                session.add(plan)
            session.commit()
            logger.info(f"Seeded {len(DEFAULT_PLANS)} default plans")
        else:
            logger.debug(f"Plans already exist ({plans_count}), skipping seed")
            
    except Exception as e:
        logger.error(f"Failed to seed default data: {e}")
        session.rollback()
    finally:
        session.close()


def get_db():
    """
    Get database session - use as context manager or generator.
    
    Usage as context manager:
        with get_db() as db:
            db.query(User).all()
    
    Usage as generator (for FastAPI/Flask dependency injection):
        db = next(get_db())
        try:
            ...
        finally:
            db.close()
    """
    SessionFactory = get_session_factory()
    if SessionFactory is None:
        raise RuntimeError("Billing database not available")
    
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    Context manager for database sessions.
    Handles commit on success, rollback on error.
    
    Usage:
        with get_db_session() as db:
            user = User(email="test@example.com")
            db.add(user)
            # Auto-commits on exit, auto-rollbacks on exception
    """
    SessionFactory = get_session_factory()
    if SessionFactory is None:
        raise RuntimeError("Billing database not available")
    
    session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        # Remove session from scoped_session registry to ensure fresh data next time
        SessionFactory.remove()


def check_db_health():
    """Check if database connection is healthy"""
    engine = get_engine()
    if engine is None:
        return False
    
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def close_db():
    """Close database connections - call on shutdown"""
    global _engine, _SessionLocal
    
    if _SessionLocal is not None:
        _SessionLocal.remove()
        _SessionLocal = None
    
    if _engine is not None:
        _engine.dispose()
        _engine = None
        logger.info("PostgreSQL connections closed")
