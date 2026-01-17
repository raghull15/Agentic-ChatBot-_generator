"""
MongoDB-based Settings Service
Manages admin-configurable billing settings and subscription plans
"""
import logging
from datetime import datetime
from typing import Any, Optional, Dict, List
from decimal import Decimal

from pymongo.database import Database
from bson import ObjectId, Decimal128

from billing.mongodb import get_mongo_db, decimal_to_decimal128, decimal128_to_float

logger = logging.getLogger(__name__)


# Default settings configuration
DEFAULT_SETTINGS = {
    'tokens_per_credit': {'value': 1000, 'description': 'Tokens per 1 credit'},
    'daily_credit_cap': {'value': 100, 'description': 'Max credits per user per day'},
    'free_credits': {'value': 10, 'description': 'Credits for new users'},
    'max_tokens_per_query': {'value': 4000, 'description': 'Hard limit per query'},
    'low_credit_threshold': {'value': 50, 'description': 'Threshold for low credit notification'},
    'bot_creation_cost': {'value': 0, 'description': 'Credits required to create a new bot'},
    'demo_bot_time_limit_hours': {'value': 24, 'description': 'Demo bot expiry time in hours'},
    'demo_bot_credit_limit': {'value': 10, 'description': 'Max credits for demo bot queries'},
}


class SettingsServiceMongo:
    """MongoDB-based settings management service"""
    
    # Keep simple default values for convenience methods
    DEFAULT_SETTINGS = {
        'tokens_per_credit': 1000,
        'free_credits': 10,
        'bot_creation_cost': 0,
        'daily_credit_cap': 100,
        'max_tokens_per_query': 4000,
        'low_credit_threshold': 5,
        'low_credit_email_enabled': True,
        'payment_enabled': True
    }
    
    @staticmethod
    def get_setting(db: Database, key: str, default: Any = None) -> Any:
        """
        Get a single setting value
        
        Args:
            db: MongoDB database
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value or default
        """
        setting = db.settings.find_one({'_id': key})
        
        if not setting:
            # Return default from DEFAULT_SETTINGS or provided default
            return SettingsServiceMongo.DEFAULT_SETTINGS.get(key, default)
        
        return setting.get('value', default)
    
    @staticmethod
    def update_setting(db: Database, key: str, value: Any, updated_by: str = None) -> bool:
        """
        Update or create a setting
        
        Args:
            db: MongoDB database
            key: Setting key
            value: New value
            updated_by: Admin email who updated
            
        Returns:
            Success boolean
        """
        result = db.settings.update_one(
            {'_id': key},
            {
                '$set': {
                    'value': value,
                    'updatedAt': datetime.utcnow(),
                    'updatedBy': updated_by
                },
                '$setOnInsert': {
                    'description': SettingsServiceMongo._get_description(key)
                }
            },
            upsert=True
        )
        
        logger.info(f"Updated setting '{key}' = {value} by {updated_by}")
        return result.acknowledged
    
    @staticmethod
    def get_all_settings(db: Database) -> Dict[str, Any]:
        """
        Get all settings in the format expected by the admin panel frontend.
        Returns dict of {key: {value, description, updated_at, updated_by}}
        
        Args:
            db: MongoDB database
            
        Returns:
            Dict of settings with metadata
        """
        result = {}
        
        # Start with defaults
        for key, info in DEFAULT_SETTINGS.items():
            result[key] = {
                'value': info['value'],
                'description': info['description'],
                'updated_at': None,
                'updated_by': None
            }
        
        # Override with database values
        for setting in db.settings.find():
            key = setting['_id']
            result[key] = {
                'value': setting.get('value'),
                'description': setting.get('description', DEFAULT_SETTINGS.get(key, {}).get('description', '')),
                'updated_at': setting.get('updatedAt').isoformat() if setting.get('updatedAt') else None,
                'updated_by': setting.get('updatedBy')
            }
        
        return result
    
    @staticmethod
    def get_all_settings_detailed(db: Database) -> List[Dict]:
        """
        Get all settings with metadata as a list
        
        Args:
            db: MongoDB database
            
        Returns:
            List of setting dicts with metadata
        """
        settings = list(db.settings.find())
        
        # Add any missing defaults
        existing_keys = {s['_id'] for s in settings}
        for key, info in DEFAULT_SETTINGS.items():
            if key not in existing_keys:
                settings.append({
                    '_id': key,
                    'value': info['value'],
                    'description': info['description'],
                    'updatedAt': None,
                    'updatedBy': None
                })
        
        # Convert to dict format
        return [
            {
                'key': s['_id'],
                'value': s['value'],
                'description': s.get('description', ''),
                'updated_at': s.get('updatedAt'),
                'updated_by': s.get('updatedBy')
            }
            for s in settings
        ]
    
    # Convenience methods for specific settings
    @staticmethod
    def get_tokens_per_credit(db: Database) -> int:
        """Get tokens per credit conversion rate"""
        return int(SettingsServiceMongo.get_setting(db, 'tokens_per_credit', 1000))
    
    @staticmethod
    def get_free_credits(db: Database) -> int:
        """Get free credits for new users"""
        return int(SettingsServiceMongo.get_setting(db, 'free_credits', 10))
    
    @staticmethod
    def get_bot_creation_cost(db: Database) -> int:
        """Get cost in credits to create a bot"""
        return int(SettingsServiceMongo.get_setting(db, 'bot_creation_cost', 0))
    
    @staticmethod
    def get_daily_credit_cap(db: Database) -> int:
        """Get daily credit usage cap"""
        return int(SettingsServiceMongo.get_setting(db, 'daily_credit_cap', 100))
    
    @staticmethod
    def get_max_tokens_per_query(db: Database) -> int:
        """Get maximum tokens per query limit"""
        return int(SettingsServiceMongo.get_setting(db, 'max_tokens_per_query', 4000))
    
    @staticmethod
    def _get_description(key: str) -> str:
        """Get description for a setting key"""
        return DEFAULT_SETTINGS.get(key, {}).get('description', '')


class PlanServiceMongo:
    """MongoDB-based subscription plans service"""
    
    # Default plans if none in database
    DEFAULT_PLANS = [
        {'id': 'starter', 'name': 'Starter', 'description': 'Perfect for individuals', 
         'amount_paise': 49900, 'credits': 500, 'bonus_credits': 0, 'sort_order': 1},
        {'id': 'pro', 'name': 'Pro', 'description': 'For small teams and projects', 
         'amount_paise': 99900, 'credits': 1000, 'bonus_credits': 200, 'sort_order': 2},
        {'id': 'business', 'name': 'Business', 'description': 'For large-scale operations', 
         'amount_paise': 199900, 'credits': 2000, 'bonus_credits': 500, 'sort_order': 3},
    ]
    
    @staticmethod
    def get_all_plans(db: Database, active_only: bool = False) -> List[Dict]:
        """
        Get all subscription plans
        
        Args:
            db: MongoDB database
            active_only: If True, only return active plans
            
        Returns:
            List of plan dicts
        """
        query = {'isActive': True} if active_only else {}
        plans = list(db.subscription_plans.find(query).sort('sortOrder', 1))
        
        # If no plans, seed defaults
        if not plans:
            PlanServiceMongo.seed_default_plans(db)
            plans = list(db.subscription_plans.find(query).sort('sortOrder', 1))
        
        return [PlanServiceMongo._plan_to_dict(p) for p in plans]
    
    @staticmethod
    def get_plan(db: Database, plan_id: str) -> Optional[Dict]:
        """Get a single plan by ID"""
        plan = db.subscription_plans.find_one({'_id': plan_id})
        return PlanServiceMongo._plan_to_dict(plan) if plan else None
    
    @staticmethod
    def create_plan(db: Database, plan_data: dict) -> Dict:
        """
        Create a new subscription plan
        
        Args:
            db: MongoDB database
            plan_data: Plan details (id, name, amount_paise, credits, etc.)
            
        Returns:
            Created plan dict
        """
        plan = {
            '_id': plan_data['id'],
            'name': plan_data['name'],
            'description': plan_data.get('description', ''),
            'amountPaise': plan_data['amount_paise'],
            'credits': Decimal128(str(plan_data['credits'])),
            'bonusCredits': Decimal128(str(plan_data.get('bonus_credits', 0))),
            'isActive': plan_data.get('is_active', True),
            'sortOrder': plan_data.get('sort_order', 0),
            'createdAt': datetime.utcnow(),
            'updatedAt': datetime.utcnow()
        }
        
        db.subscription_plans.insert_one(plan)
        logger.info(f"Created plan: {plan['_id']}")
        return PlanServiceMongo._plan_to_dict(plan)
    
    @staticmethod
    def update_plan(db: Database, plan_id: str, plan_data: dict) -> Optional[Dict]:
        """
        Update an existing plan
        
        Args:
            db: MongoDB database
            plan_id: Plan ID to update
            plan_data: Fields to update
            
        Returns:
            Updated plan dict or None if not found
        """
        update_fields = {'updatedAt': datetime.utcnow()}
        
        if 'name' in plan_data:
            update_fields['name'] = plan_data['name']
        if 'description' in plan_data:
            update_fields['description'] = plan_data['description']
        if 'amount_paise' in plan_data:
            update_fields['amountPaise'] = plan_data['amount_paise']
        if 'credits' in plan_data:
            update_fields['credits'] = Decimal128(str(plan_data['credits']))
        if 'bonus_credits' in plan_data:
            update_fields['bonusCredits'] = Decimal128(str(plan_data['bonus_credits']))
        if 'is_active' in plan_data:
            update_fields['isActive'] = plan_data['is_active']
        if 'sort_order' in plan_data:
            update_fields['sortOrder'] = plan_data['sort_order']
        
        result = db.subscription_plans.find_one_and_update(
            {'_id': plan_id},
            {'$set': update_fields},
            return_document=True
        )
        
        if result:
            logger.info(f"Updated plan: {plan_id}")
            return PlanServiceMongo._plan_to_dict(result)
        return None
    
    @staticmethod
    def delete_plan(db: Database, plan_id: str, soft_delete: bool = True) -> bool:
        """
        Delete or deactivate a plan
        
        Args:
            db: MongoDB database
            plan_id: Plan ID to delete
            soft_delete: If True, just mark as inactive. If False, actually delete.
            
        Returns:
            Success boolean
        """
        if soft_delete:
            result = db.subscription_plans.update_one(
                {'_id': plan_id},
                {'$set': {'isActive': False, 'updatedAt': datetime.utcnow()}}
            )
            success = result.modified_count > 0
            if success:
                logger.info(f"Deactivated plan: {plan_id}")
        else:
            result = db.subscription_plans.delete_one({'_id': plan_id})
            success = result.deleted_count > 0
            if success:
                logger.info(f"Deleted plan: {plan_id}")
        
        return success
    
    @staticmethod
    def seed_default_plans(db: Database):
        """Seed default plans if none exist"""
        for plan_data in PlanServiceMongo.DEFAULT_PLANS:
            existing = db.subscription_plans.find_one({'_id': plan_data['id']})
            if not existing:
                plan = {
                    '_id': plan_data['id'],
                    'name': plan_data['name'],
                    'description': plan_data['description'],
                    'amountPaise': plan_data['amount_paise'],
                    'credits': Decimal128(str(plan_data['credits'])),
                    'bonusCredits': Decimal128(str(plan_data['bonus_credits'])),
                    'isActive': True,
                    'sortOrder': plan_data['sort_order'],
                    'createdAt': datetime.utcnow(),
                    'updatedAt': datetime.utcnow()
                }
                db.subscription_plans.insert_one(plan)
        logger.info("Seeded default subscription plans")
    
    @staticmethod
    def _plan_to_dict(plan: dict) -> Dict:
        """Convert MongoDB plan document to dict for API responses"""
        if not plan:
            return None
        
        credits = plan.get('credits')
        bonus_credits = plan.get('bonusCredits')
        
        # Handle Decimal128 conversion
        if isinstance(credits, Decimal128):
            credits = float(credits.to_decimal())
        else:
            credits = float(credits or 0)
            
        if isinstance(bonus_credits, Decimal128):
            bonus_credits = float(bonus_credits.to_decimal())
        else:
            bonus_credits = float(bonus_credits or 0)
        
        return {
            'id': plan['_id'],
            'name': plan.get('name'),
            'description': plan.get('description', ''),
            'amount_paise': plan.get('amountPaise'),
            'amount_inr': plan.get('amountPaise', 0) / 100,
            'credits': credits,
            'bonus_credits': bonus_credits,
            'total_credits': credits + bonus_credits,
            'is_active': plan.get('isActive', True),
            'sort_order': plan.get('sortOrder', 0),
            'created_at': plan.get('createdAt').isoformat() if plan.get('createdAt') else None,
            'updated_at': plan.get('updatedAt').isoformat() if plan.get('updatedAt') else None
        }


class UserManagementServiceMongo:
    """MongoDB-based user management service"""
    
    @staticmethod
    def suspend_user(db: Database, mongo_user_id: str) -> bool:
        """Suspend a user"""
        result = db.billing_users.update_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'$set': {'isSuspended': True}}
        )
        if result.modified_count > 0:
            logger.info(f"Suspended user: {mongo_user_id}")
            return True
        return False
    
    @staticmethod
    def unsuspend_user(db: Database, mongo_user_id: str) -> bool:
        """Unsuspend a user"""
        result = db.billing_users.update_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'$set': {'isSuspended': False}}
        )
        if result.modified_count > 0:
            logger.info(f"Unsuspended user: {mongo_user_id}")
            return True
        return False
    
    @staticmethod
    def is_user_suspended(db: Database, mongo_user_id: str) -> bool:
        """Check if user is suspended"""
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'isSuspended': 1}
        )
        return user.get('isSuspended', False) if user else False

