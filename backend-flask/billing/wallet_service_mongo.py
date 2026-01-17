"""
MongoDB-based Wallet Service
Replaces SQLAlchemy version with native PyMongo
"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict

from pymongo.database import Database
from pymongo import ReturnDocument
from bson import ObjectId, Decimal128

from billing.mongodb import (
    get_mongo_db, 
    get_billing_users, 
    get_usage_logs,
    decimal_to_decimal128,
    decimal128_to_decimal,
    decimal128_to_float,
    mongo_transaction
)

logger = logging.getLogger(__name__)


class WalletServiceMongo:
    """MongoDB-based wallet service for credit management"""
    
    @staticmethod
    def get_or_create_user(db: Database, mongo_user_id: str, email: str = None) -> Dict:
        """
        Get existing user or create new one with wallet
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID from MongoDB auth
            email: User email (optional)
            
        Returns:
            User document
        """
        collection = db.billing_users
        
        # Try to find existing user
        user = collection.find_one({'mongoUserId': ObjectId(mongo_user_id)})
        
        if user is None:
            # Create new user with embedded wallet
            new_user = {
                'mongoUserId': ObjectId(mongo_user_id),
                'email': email or f"{mongo_user_id}@placeholder.local",
                'isSuspended': False,
                'lowCreditNotified': False,
                'wallet': {
                    'creditsRemaining': Decimal128("0"),
                    'totalCreditsPurchased': Decimal128("0"),
                    'updatedAt': datetime.utcnow()
                },
                'createdAt': datetime.utcnow()
            }
            
            result = collection.insert_one(new_user)
            new_user['_id'] = result.inserted_id
            
            logger.info(f"Created new billing user for {mongo_user_id}")
            return new_user
        
        return user
    
    @staticmethod
    def get_balance(db: Database, mongo_user_id: str) -> Decimal:
        """
        Get current credit balance for a user
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID from MongoDB auth
            
        Returns:
            Credit balance as Decimal
        """
        collection = db.billing_users
        
        user = collection.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'wallet.creditsRemaining': 1}
        )
        
        if not user or 'wallet' not in user:
            return Decimal('0')
        
        return decimal128_to_decimal(user['wallet']['creditsRemaining'])
    
    @staticmethod
    def get_daily_usage(db: Database, mongo_user_id: str) -> Decimal:
        """
        Get today's total credit usage
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID from MongoDB auth
            
        Returns:
            Today's usage as Decimal
        """
        # Get user's billing_users _id
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'_id': 1}
        )
        
        if not user:
            return Decimal('0')
        
        # Get today's start
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Aggregate usage for today
        pipeline = [
            {
                '$match': {
                    'userId': user['_id'],
                    'createdAt': {'$gte': today_start}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'total': {'$sum': '$creditsUsed'}
                }
            }
        ]
        
        result = list(db.usage_logs.aggregate(pipeline))
        
        if not result or not result[0].get('total'):
            return Decimal('0')
        
        return decimal128_to_decimal(result[0]['total'])
    
    @staticmethod
    def has_sufficient_credits(db: Database, mongo_user_id: str, required: Decimal) -> Tuple[bool, str]:
        """
        Check if user has sufficient credits (including daily cap check)
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            required: Credits required
            
        Returns:
            Tuple of (has_credits, reason_if_not)
        """
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'wallet': 1, '_id': 1}
        )
        
        if not user or 'wallet' not in user:
            return False, "No billing account found. Please add credits."
        
        balance = decimal128_to_decimal(user['wallet']['creditsRemaining'])
        
        if balance < required:
            return False, f"Insufficient credits. Balance: {float(balance):.4f}, Required: {float(required):.4f}"
        
        # Check daily cap
        from billing.settings_service_mongo import SettingsServiceMongo
        daily_usage = WalletServiceMongo.get_daily_usage(db, mongo_user_id)
        daily_cap = Decimal(str(SettingsServiceMongo.get_daily_credit_cap(db)))
        
        if daily_usage + required > daily_cap:
            remaining_today = daily_cap - daily_usage
            return False, f"Daily limit reached. Remaining today: {remaining_today:.2f} credits"
        
        return True, "OK"
    
    @staticmethod
    def deduct_credits(db: Database, mongo_user_id: str, amount: Decimal) -> Tuple[bool, str]:
        """
        Atomically deduct credits from user wallet
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            amount: Credits to deduct
            
        Returns:
            Tuple of (success, message)
        """
        if amount <= 0:
            return True, "No deduction needed"
        
        collection = db.billing_users
        
        # Check sufficient credits first
        has_credits, reason = WalletServiceMongo.has_sufficient_credits(db, mongo_user_id, amount)
        if not has_credits:
            return False, reason
        
        # Atomic decrement using $inc
        result = collection.find_one_and_update(
            {
                'mongoUserId': ObjectId(mongo_user_id),
                'wallet.creditsRemaining': {'$gte': decimal_to_decimal128(amount)}
            },
            {
                '$inc': {'wallet.creditsRemaining': decimal_to_decimal128(-amount)},
                '$set': {'wallet.updatedAt': datetime.utcnow()}
            },
            return_document=ReturnDocument.AFTER
        )
        
        if not result:
            return False, "Insufficient credits or concurrent deduction conflict"
        
        new_balance = decimal128_to_decimal(result['wallet']['creditsRemaining'])
        logger.info(f"Deducted {amount} credits from {mongo_user_id}. New balance: {new_balance}")
        
        return True, str(new_balance)
    
    @staticmethod
    def add_credits(db: Database, mongo_user_id: str, amount: Decimal, source: str = "admin") -> Tuple[bool, Decimal]:
        """
        Add credits to user wallet
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            amount: Credits to add
            source: Source of credits (payment, admin, etc.)
            
        Returns:
            Tuple of (success, new_balance)
        """
        if amount <= 0:
            return False, Decimal('0')
        
        collection = db.billing_users
        
        # Ensure user exists
        WalletServiceMongo.get_or_create_user(db, mongo_user_id)
        
        # Atomic increment
        result = collection.find_one_and_update(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {
                '$inc': {
                    'wallet.creditsRemaining': decimal_to_decimal128(amount),
                    'wallet.totalCreditsPurchased': decimal_to_decimal128(amount) if source == "payment" else Decimal128("0")
                },
                '$set': {'wallet.updatedAt': datetime.utcnow()}
            },
            return_document=ReturnDocument.AFTER
        )
        
        if not result:
            return False, Decimal('0')
        
        new_balance = decimal128_to_decimal(result['wallet']['creditsRemaining'])
        logger.info(f"Added {amount} credits to {mongo_user_id} (source: {source}). New balance: {new_balance}")
        
        return True, new_balance
    
    @staticmethod
    def get_wallet_info(db: Database, mongo_user_id: str) -> Optional[Dict]:
        """
        Get complete wallet information
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            
        Returns:
            Wallet info dict or None
        """
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'wallet': 1, 'email': 1}
        )
        
        if not user or 'wallet' not in user:
            return None
        
        wallet = user['wallet']
        
        return {
            'credits_remaining': decimal128_to_float(wallet['creditsRemaining']),
            'total_purchased': decimal128_to_float(wallet.get('totalCreditsPurchased', 0)),
            'updated_at': wallet.get('updatedAt'),
            'email': user.get('email')
        }
    
    @staticmethod
    def suspend_user(db: Database, mongo_user_id: str) -> bool:
        """Suspend a user account"""
        result = db.billing_users.update_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'$set': {'isSuspended': True}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def unsuspend_user(db: Database, mongo_user_id: str) -> bool:
        """Unsuspend a user account"""
        result = db.billing_users.update_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'$set': {'isSuspended': False}}
        )
        return result.modified_count > 0
    
    @staticmethod
    def is_suspended(db: Database, mongo_user_id: str) -> bool:
        """Check if user is suspended"""
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'isSuspended': 1}
        )
        return user.get('isSuspended', False) if user else False
