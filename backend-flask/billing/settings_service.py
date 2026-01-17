"""
Settings Service - Admin-configurable billing settings
Manages system settings and subscription plans
"""
import json
import logging
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from billing.models import BillingSetting, SubscriptionPlan, User

logger = logging.getLogger(__name__)

# Default settings if not in database
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

# Default plans if none in database
DEFAULT_PLANS = [
    {'id': 'starter', 'name': 'Starter', 'description': 'Perfect for individuals', 'amount_paise': 49900, 'credits': 500, 'bonus_credits': 0, 'sort_order': 1},
    {'id': 'pro', 'name': 'Pro', 'description': 'For small teams and projects', 'amount_paise': 99900, 'credits': 1000, 'bonus_credits': 200, 'sort_order': 2},
    {'id': 'business', 'name': 'Business', 'description': 'For large-scale operations', 'amount_paise': 199900, 'credits': 2000, 'bonus_credits': 500, 'sort_order': 3},
]


class SettingsService:
    """Service for managing billing settings"""
    
    @staticmethod
    def get_setting(db: Session, key: str) -> Any:
        """Get a single setting value"""
        setting = db.query(BillingSetting).filter(BillingSetting.key == key).first()
        
        if setting:
            try:
                return json.loads(setting.value)
            except json.JSONDecodeError:
                return setting.value
        
        # Return default if exists
        if key in DEFAULT_SETTINGS:
            return DEFAULT_SETTINGS[key]['value']
        
        return None
    
    @staticmethod
    def get_all_settings(db: Session) -> Dict[str, Any]:
        """Get all settings as a dict"""
        settings = db.query(BillingSetting).all()
        
        result = {}
        # Start with defaults
        for key, info in DEFAULT_SETTINGS.items():
            result[key] = {
                'value': info['value'],
                'description': info['description'],
                'updated_at': None,
                'updated_by': None
            }
        
        # Override with DB values
        for s in settings:
            try:
                value = json.loads(s.value)
            except json.JSONDecodeError:
                value = s.value
            
            result[s.key] = {
                'value': value,
                'description': s.description or DEFAULT_SETTINGS.get(s.key, {}).get('description', ''),
                'updated_at': s.updated_at.isoformat() if s.updated_at else None,
                'updated_by': s.updated_by
            }
        
        return result
    
    @staticmethod
    def update_setting(db: Session, key: str, value: Any, updated_by: str = None) -> bool:
        """Update a setting"""
        setting = db.query(BillingSetting).filter(BillingSetting.key == key).first()
        
        json_value = json.dumps(value)
        
        if setting:
            setting.value = json_value
            setting.updated_by = updated_by
            setting.updated_at = datetime.utcnow()
        else:
            setting = BillingSetting(
                key=key,
                value=json_value,
                description=DEFAULT_SETTINGS.get(key, {}).get('description', ''),
                updated_by=updated_by
            )
            db.add(setting)
        
        db.commit()
        logger.info(f"Setting {key} updated to {value} by {updated_by}")
        return True
    
    @staticmethod
    def get_tokens_per_credit(db: Session) -> int:
        """Get current tokens per credit ratio"""
        return SettingsService.get_setting(db, 'tokens_per_credit') or 1000
    
    @staticmethod
    def get_daily_credit_cap(db: Session) -> int:
        """Get daily credit cap"""
        return SettingsService.get_setting(db, 'daily_credit_cap') or 100
    
    @staticmethod
    def get_free_credits(db: Session) -> int:
        """Get free credits for new users"""
        return SettingsService.get_setting(db, 'free_credits') or 10
    
    @staticmethod
    def get_max_tokens_per_query(db: Session) -> int:
        """Get maximum tokens per query limit"""
        return SettingsService.get_setting(db, 'max_tokens_per_query') or 4000



class PlanService:
    """Service for managing subscription plans"""
    
    @staticmethod
    def get_all_plans(db: Session, active_only: bool = False) -> List[dict]:
        """Get all subscription plans"""
        query = db.query(SubscriptionPlan).order_by(SubscriptionPlan.sort_order)
        
        if active_only:
            query = query.filter(SubscriptionPlan.is_active == True)
        
        plans = query.all()
        
        # If no plans in DB, seed defaults
        if not plans:
            PlanService.seed_default_plans(db)
            plans = query.all()
        
        return [PlanService._plan_to_dict(p) for p in plans]
    
    @staticmethod
    def get_plan(db: Session, plan_id: str) -> Optional[dict]:
        """Get a single plan by ID"""
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        return PlanService._plan_to_dict(plan) if plan else None
    
    @staticmethod
    def create_plan(db: Session, plan_data: dict) -> dict:
        """Create a new subscription plan"""
        plan = SubscriptionPlan(
            id=plan_data['id'],
            name=plan_data['name'],
            description=plan_data.get('description', ''),
            amount_paise=plan_data['amount_paise'],
            credits=Decimal(str(plan_data['credits'])),
            bonus_credits=Decimal(str(plan_data.get('bonus_credits', 0))),
            is_active=plan_data.get('is_active', True),
            sort_order=plan_data.get('sort_order', 0)
        )
        db.add(plan)
        db.commit()
        
        logger.info(f"Created plan: {plan.id}")
        return PlanService._plan_to_dict(plan)
    
    @staticmethod
    def update_plan(db: Session, plan_id: str, plan_data: dict) -> Optional[dict]:
        """Update an existing plan"""
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        
        if not plan:
            return None
        
        if 'name' in plan_data:
            plan.name = plan_data['name']
        if 'description' in plan_data:
            plan.description = plan_data['description']
        if 'amount_paise' in plan_data:
            plan.amount_paise = plan_data['amount_paise']
        if 'credits' in plan_data:
            plan.credits = Decimal(str(plan_data['credits']))
        if 'bonus_credits' in plan_data:
            plan.bonus_credits = Decimal(str(plan_data['bonus_credits']))
        if 'is_active' in plan_data:
            plan.is_active = plan_data['is_active']
        if 'sort_order' in plan_data:
            plan.sort_order = plan_data['sort_order']
        
        plan.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Updated plan: {plan.id}")
        return PlanService._plan_to_dict(plan)
    
    @staticmethod
    def delete_plan(db: Session, plan_id: str, soft_delete: bool = True) -> bool:
        """Delete or deactivate a plan"""
        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        
        if not plan:
            return False
        
        if soft_delete:
            plan.is_active = False
            db.commit()
            logger.info(f"Deactivated plan: {plan.id}")
        else:
            db.delete(plan)
            db.commit()
            logger.info(f"Deleted plan: {plan.id}")
        
        return True
    
    @staticmethod
    def seed_default_plans(db: Session):
        """Seed default plans if none exist"""
        for plan_data in DEFAULT_PLANS:
            existing = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_data['id']).first()
            if not existing:
                plan = SubscriptionPlan(**plan_data)
                db.add(plan)
        db.commit()
        logger.info("Seeded default subscription plans")
    
    @staticmethod
    def _plan_to_dict(plan: SubscriptionPlan) -> dict:
        """Convert plan to dict"""
        return {
            'id': plan.id,
            'name': plan.name,
            'description': plan.description,
            'amount_paise': plan.amount_paise,
            'amount_inr': plan.amount_paise / 100,
            'credits': float(plan.credits),
            'bonus_credits': float(plan.bonus_credits),
            'total_credits': float(plan.credits + plan.bonus_credits),
            'is_active': plan.is_active,
            'sort_order': plan.sort_order,
            'created_at': plan.created_at.isoformat() if plan.created_at else None,
            'updated_at': plan.updated_at.isoformat() if plan.updated_at else None
        }


class UserManagementService:
    """Service for admin user management"""
    
    @staticmethod
    def suspend_user(db: Session, mongo_user_id: str) -> bool:
        """Suspend a user"""
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        if user:
            user.is_suspended = True
            db.commit()
            logger.info(f"Suspended user: {mongo_user_id}")
            return True
        return False
    
    @staticmethod
    def unsuspend_user(db: Session, mongo_user_id: str) -> bool:
        """Unsuspend a user"""
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        if user:
            user.is_suspended = False
            db.commit()
            logger.info(f"Unsuspended user: {mongo_user_id}")
            return True
        return False
    
    @staticmethod
    def is_user_suspended(db: Session, mongo_user_id: str) -> bool:
        """Check if user is suspended"""
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        return user.is_suspended if user else False
