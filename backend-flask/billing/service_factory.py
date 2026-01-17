"""
Service Factory - Database Abstraction Layer
Provides unified interface that works with both PostgreSQL and MongoDB
Uses environment variable USE_MONGODB to switch between implementations
Default: MongoDB (USE_MONGODB=true)
"""
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Feature flag - Default to MongoDB
USE_MONGODB = os.getenv('USE_MONGODB', 'true').lower() in ('true', '1', 'yes')

logger.info(f"🔧 Billing Service Mode: {'MongoDB' if USE_MONGODB else 'PostgreSQL'}")


def get_wallet_service():
    """
    Get wallet service implementation
    
    Returns:
        WalletService (PostgreSQL) or WalletServiceMongo (MongoDB)
    """
    if USE_MONGODB:
        from billing.wallet_service_mongo import WalletServiceMongo
        return WalletServiceMongo
    else:
        from billing.wallet_service import WalletService
        return WalletService


def get_usage_service():
    """
    Get usage service implementation
    
    Returns:
        UsageService (PostgreSQL) or UsageServiceMongo (MongoDB)
    """
    if USE_MONGODB:
        from billing.usage_service_mongo import UsageServiceMongo
        return UsageServiceMongo
    else:
        from billing.usage_service import UsageService
        return UsageService


def get_settings_service():
    """
    Get settings service implementation
    
    Returns:
        SettingsService (PostgreSQL) or SettingsServiceMongo (MongoDB)
    """
    if USE_MONGODB:
        from billing.settings_service_mongo import SettingsServiceMongo
        return SettingsServiceMongo
    else:
        from billing.settings_service import SettingsService
        return SettingsService


def get_plan_service():
    """
    Get plan service implementation
    
    Returns:
        PlanService (PostgreSQL) or PlanServiceMongo (MongoDB)
    """
    if USE_MONGODB:
        from billing.settings_service_mongo import PlanServiceMongo
        return PlanServiceMongo
    else:
        from billing.settings_service import PlanService
        return PlanService


def get_user_management_service():
    """
    Get user management service implementation
    
    Returns:
        UserManagementService (PostgreSQL) or UserManagementServiceMongo (MongoDB)
    """
    if USE_MONGODB:
        from billing.settings_service_mongo import UserManagementServiceMongo
        return UserManagementServiceMongo
    else:
        from billing.settings_service import UserManagementService
        return UserManagementService


def get_payment_service():
    """
    Get payment service implementation
    
    Returns:
        PaymentService (PostgreSQL) or PaymentServiceMongo (MongoDB)
    """
    if USE_MONGODB:
        from billing.payment_service_mongo import PaymentServiceMongo
        return PaymentServiceMongo
    else:
        from billing.payment_service import PaymentService
        return PaymentService


def get_analytics_service():
    """
    Get analytics service implementation
    
    Returns:
        AnalyticsService (PostgreSQL) or AnalyticsServiceMongo (MongoDB)
    """
    if USE_MONGODB:
        from billing.analytics_service_mongo import AnalyticsServiceMongo
        return AnalyticsServiceMongo
    else:
        from billing.analytics_service import AnalyticsService
        return AnalyticsService


def get_db_context():
    """
    Get database context manager
    
    Returns:
        Context manager for database session/connection
    """
    if USE_MONGODB:
        from billing.mongodb import get_db_session as get_mongo_session
        return get_mongo_session()
    else:
        from billing.database import get_db_session
        return get_db_session()


def get_database():
    """
    Get raw database object
    
    Returns:
        SQLAlchemy Session or MongoDB Database
    """
    if USE_MONGODB:
        from billing.mongodb import get_mongo_db
        return get_mongo_db()
    else:
        from billing.database import get_db_session
        # For PostgreSQL, return session from context
        with get_db_session() as db:
            return db


def init_billing():
    """
    Initialize billing system based on mode
    
    Returns:
        True if successful, False otherwise
    """
    if USE_MONGODB:
        from billing.mongodb import init_mongodb
        try:
            init_mongodb()
            logger.info("✅ MongoDB billing initialized")
            return True
        except Exception as e:
            logger.error(f"MongoDB billing init failed: {e}")
            return False
    else:
        from billing.database import init_db
        return init_db()

