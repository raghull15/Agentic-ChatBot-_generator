"""
Wallet Service - Credit management with atomic operations
Handles balance checks, deductions, and additions
"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session

from billing.models import User, Wallet, UsageLog
from billing.database import get_db_session

logger = logging.getLogger(__name__)


class WalletService:
    """Service for managing user credit wallets"""
    
    @staticmethod
    def get_or_create_user(db: Session, mongo_user_id: str, email: str = None) -> User:
        """
        Get existing user or create new one with wallet.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            email: User email (optional, for new users)
            
        Returns:
            User object
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            # Create new user with wallet
            user = User(
                mongo_user_id=mongo_user_id,
                email=email or f"{mongo_user_id}@placeholder.local"
            )
            db.add(user)
            db.flush()  # Get the user ID
            
            # Create wallet for new user
            wallet = Wallet(user_id=user.id, credits_remaining=Decimal('0'))
            db.add(wallet)
            db.commit()
            
            logger.info(f"Created new billing user and wallet for {mongo_user_id}")
        
        return user
    
    @staticmethod
    def get_balance(db: Session, mongo_user_id: str) -> Decimal:
        """
        Get current credit balance for a user.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            
        Returns:
            Credit balance as Decimal
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None or user.wallet is None:
            return Decimal('0')
        
        return user.wallet.credits_remaining
    
    @staticmethod
    def get_daily_usage(db: Session, mongo_user_id: str) -> Decimal:
        """
        Get today's total credit usage for a user.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            
        Returns:
            Today's usage as Decimal
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            return Decimal('0')
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        result = db.query(func.sum(UsageLog.credits_used)).filter(
            UsageLog.user_id == user.id,
            UsageLog.created_at >= today_start
        ).scalar()
        
        return result or Decimal('0')
    
    @staticmethod
    def has_sufficient_credits(db: Session, mongo_user_id: str, required: Decimal) -> Tuple[bool, str]:
        """
        Check if user has sufficient credits (including daily cap check).
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            required: Credits required for the operation
            
        Returns:
            Tuple of (has_credits, reason_if_not)
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None or user.wallet is None:
            return False, "No billing account found. Please add credits."
        
        # Force refresh to get latest balance from database (bypass any caching)
        db.refresh(user.wallet)
        balance = user.wallet.credits_remaining
        
        if balance < required:
            return False, f"Insufficient credits. Balance: {float(balance):.4f}, Required: {float(required):.4f}"
        
        # Check daily cap using admin-configurable setting
        from billing.settings_service import SettingsService
        daily_usage = WalletService.get_daily_usage(db, mongo_user_id)
        daily_cap = Decimal(str(SettingsService.get_daily_credit_cap(db)))
        if daily_usage + required > daily_cap:
            remaining_today = daily_cap - daily_usage
            return False, f"Daily limit reached. Remaining today: {remaining_today:.2f} credits"
        
        return True, "OK"
    
    @staticmethod
    def deduct_credits(db: Session, mongo_user_id: str, amount: Decimal) -> Tuple[bool, str]:
        """
        Atomically deduct credits from user wallet.
        Uses database-level check to prevent negative balance.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            amount: Credits to deduct
            
        Returns:
            Tuple of (success, message)
        """
        if amount <= 0:
            return True, "No deduction needed"
        
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            # Auto-create user and wallet if they don't exist
            # This handles cases where user registered but billing account wasn't created
            logger.warning(f"User {mongo_user_id} not in billing DB, creating billing account")
            user = WalletService.get_or_create_user(db, mongo_user_id)
        
        if user.wallet is None:
            # Create wallet if missing (defensive)
            wallet = Wallet(user_id=user.id, credits_remaining=Decimal('0'))
            db.add(wallet)
            db.flush()
            return False, "Insufficient credits. Balance: 0.0000, Required: " + f"{float(amount):.4f}"
        
        # Atomic update with balance check
        result = db.query(Wallet).filter(
            Wallet.user_id == user.id,
            Wallet.credits_remaining >= amount  # Prevent negative balance
        ).update(
            {Wallet.credits_remaining: Wallet.credits_remaining - amount},
            synchronize_session=False
        )
        
        if result == 0:
            # Refresh to get current balance for error message
            db.expire(user.wallet)
            current_balance = db.query(Wallet).filter(Wallet.user_id == user.id).first().credits_remaining
            logger.warning(f"Insufficient credits for {mongo_user_id}: has {current_balance}, needs {amount}")
            # Return failure - caller's context manager will handle rollback
            return False, f"Insufficient credits. Balance: {float(current_balance):.4f}, Required: {float(amount):.4f}"
        
        # Don't commit here - let the caller's context manager handle commit
        logger.info(f"Deducted {amount} credits from user {mongo_user_id}")
        return True, "OK"
    
    @staticmethod
    def add_credits(db: Session, mongo_user_id: str, amount: Decimal, email: str = None) -> Tuple[bool, Decimal]:
        """
        Add credits to user wallet (e.g., after payment).
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            amount: Credits to add
            email: User email (for new users)
            
        Returns:
            Tuple of (success, new_balance)
        """
        if amount <= 0:
            return False, Decimal('0')
        
        # Get or create user
        user = WalletService.get_or_create_user(db, mongo_user_id, email)
        
        # Update wallet
        wallet = user.wallet
        if wallet is None:
            wallet = Wallet(user_id=user.id, credits_remaining=Decimal('0'))
            db.add(wallet)
        
        wallet.credits_remaining += amount
        wallet.total_credits_purchased += amount
        
        db.commit()
        
        logger.info(f"Added {amount} credits to user {mongo_user_id}. New balance: {wallet.credits_remaining}")
        return True, wallet.credits_remaining
    
    @staticmethod
    def get_wallet_info(db: Session, mongo_user_id: str) -> Optional[dict]:
        """
        Get full wallet information for a user.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            
        Returns:
            Dict with wallet info or None
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None or user.wallet is None:
            return None
        
        daily_usage = WalletService.get_daily_usage(db, mongo_user_id)
        
        # Get daily cap from settings
        from billing.settings_service import SettingsService
        daily_credit_cap = SettingsService.get_daily_credit_cap(db)
        
        return {
            "credits_remaining": float(user.wallet.credits_remaining),
            "total_purchased": float(user.wallet.total_credits_purchased),
            "daily_usage": float(daily_usage),
            "daily_limit": float(daily_credit_cap),
            "daily_remaining": float(daily_credit_cap - daily_usage),
            "plan": user.plan,
            "updated_at": user.wallet.updated_at.isoformat() if user.wallet.updated_at else None
        }

