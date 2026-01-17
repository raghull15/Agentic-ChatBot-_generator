"""
MongoDB Connection and Utilities for Billing System
Replaces billing/database.py (PostgreSQL)

This module provides MongoDB connection management and helper functions
for the billing system using native PyMongo.
"""

import os
import logging
from typing import Optional
from contextlib import contextmanager

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.collection import Collection
from bson import ObjectId, Decimal128
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Global MongoDB client
_mongo_client: Optional[MongoClient] = None
_mongo_db: Optional[Database] = None


def init_mongodb():
    """Initialize MongoDB connection and create indexes"""
    global _mongo_client, _mongo_db
    
    if _mongo_client is not None:
        logger.info("MongoDB already initialized")
        return _mongo_db
    
    try:
        mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        mongo_db_name = os.getenv('MONGO_DB_NAME', 'agentic_bot')
        
        logger.info(f"Connecting to MongoDB: {mongo_url} / {mongo_db_name}")
        
        _mongo_client = MongoClient(
            mongo_url,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=30000,
            waitQueueTimeoutMS=10000,
        )
        
        _mongo_db = _mongo_client[mongo_db_name]
        
        # Test connection
        _mongo_client.server_info()
        
        logger.info("✅ MongoDB connected successfully")
        
        # Create indexes
        _create_indexes(_mongo_db)
        
        return _mongo_db
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


def _create_indexes(db: Database):
    """Create all necessary indexes for billing collections"""
    logger.info("Creating MongoDB indexes...")
    
    try:
        # billing_users indexes
        db.billing_users.create_index([('mongoUserId', ASCENDING)], unique=True, sparse=True, background=True)
        db.billing_users.create_index([('email', ASCENDING)], unique=True, background=True)
        db.billing_users.create_index([('wallet.creditsRemaining', ASCENDING)], background=True)
        
        # payments indexes
        db.payments.create_index([('userId', ASCENDING), ('createdAt', DESCENDING)], background=True)
        db.payments.create_index([('razorpayOrderId', ASCENDING)], unique=True, sparse=True, background=True)
        db.payments.create_index([('status', ASCENDING), ('createdAt', DESCENDING)], background=True)
        db.payments.create_index([('idempotencyKey', ASCENDING)], unique=True, sparse=True, background=True)
        
        # usage_logs indexes
        db.usage_logs.create_index([('userId', ASCENDING), ('createdAt', DESCENDING)], background=True)
        db.usage_logs.create_index([('agentName', ASCENDING), ('createdAt', DESCENDING)], background=True)
        # TTL index for auto-cleanup (90 days)
        db.usage_logs.create_index(
            [('createdAt', ASCENDING)],
            expireAfterSeconds=7776000,  # 90 days
            background=True
        )
        
        # subscription_plans indexes
        db.subscription_plans.create_index([('sortOrder', ASCENDING), ('isActive', ASCENDING)], background=True)
        
        # audit_logs indexes (if migrated)
        db.audit_logs.create_index([('adminUserId', ASCENDING), ('timestamp', DESCENDING)], background=True)
        db.audit_logs.create_index([('action', ASCENDING), ('timestamp', DESCENDING)], background=True)
        db.audit_logs.create_index([('targetType', ASCENDING), ('targetId', ASCENDING)], background=True)
        
        logger.info("✅ MongoDB indexes created successfully")
        
    except Exception as e:
        logger.warning(f"Index creation warning (may already exist): {e}")


def get_mongo_db() -> Database:
    """Get MongoDB database instance"""
    global _mongo_db
    
    if _mongo_db is None:
        init_mongodb()
    
    return _mongo_db


@contextmanager
def get_billing_collection(collection_name: str):
    """
    Context manager for billing collections
    Usage: with get_billing_collection('billing_users') as collection:
    """
    db = get_mongo_db()
    collection = db[collection_name]
    try:
        yield collection
    finally:
        pass  # No cleanup needed for reads


# Collection getters (convenience functions)
def get_billing_users() -> Collection:
    """Get billing_users collection"""
    return get_mongo_db().billing_users


def get_payments() -> Collection:
    """Get payments collection"""
    return get_mongo_db().payments


def get_usage_logs() -> Collection:
    """Get usage_logs collection"""
    return get_mongo_db().usage_logs


def get_settings() -> Collection:
    """Get settings collection"""
    return get_mongo_db().settings


def get_subscription_plans() -> Collection:
    """Get subscription_plans collection"""
    return get_mongo_db().subscription_plans


def get_audit_logs() -> Collection:
    """Get audit_logs collection"""
    return get_mongo_db().audit_logs


# Decimal conversion utilities
def decimal_to_decimal128(value) -> Decimal128:
    """Convert Python Decimal to MongoDB Decimal128"""
    if value is None:
        return Decimal128("0")
    if isinstance(value, Decimal128):
        return value
    return Decimal128(str(value))


def decimal128_to_decimal(value) -> Decimal:
    """Convert MongoDB Decimal128 to Python Decimal"""
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    if isinstance(value, Decimal128):
        return value.to_decimal()
    return Decimal(str(value))


def decimal128_to_float(value) -> float:
    """Convert MongoDB Decimal128 to float (for JSON serialization)"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    return float(value)


# Transaction support (MongoDB 4.0+)
@contextmanager
def mongo_transaction():
    """
    Context manager for MongoDB transactions
    Usage:
        with mongo_transaction() as session:
            # perform operations with session
            collection.update_one({...}, {...}, session=session)
    """
    client = _mongo_client
    if client is None:
        raise RuntimeError("MongoDB not initialized")
    
    session = client.start_session()
    try:
        with session.start_transaction():
            yield session
            # Transaction commits automatically if no exception
    except Exception as e:
        logger.error(f"Transaction failed: {e}")
        # Transaction rolls back automatically on exception
        raise
    finally:
        session.end_session()


# Health check
def check_mongodb_health() -> dict:
    """Check MongoDB connection health"""
    try:
        db = get_mongo_db()
        server_info = _mongo_client.server_info()
        
        return {
            "status": "healthy",
            "version": server_info.get('version'),
            "collections": db.list_collection_names()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


# Cleanup
def close_mongodb():
    """Close MongoDB connection"""
    global _mongo_client, _mongo_db
    
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB connection closed")


# For backward compatibility with PostgreSQL code
# This allows gradual migration
def get_db_session():
    """
    Compatibility wrapper - returns MongoDB database instance
    This is a NO-OP context manager for MongoDB (no sessions needed for reads)
    """
    @contextmanager
    def _db_context():
        yield get_mongo_db()
    
    return _db_context()
