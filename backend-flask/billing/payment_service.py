"""
Payment Service - Razorpay Integration (INR)
Handles order creation, payment verification, and webhooks
"""
import os
import hmac
import hashlib
import logging
import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from billing.models import User, Payment
from billing.wallet_service import WalletService

logger = logging.getLogger(__name__)

# Razorpay credentials from environment
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')

# Pricing plans (amount in paise, 100 paise = ₹1)
PRICING_PLANS = {
    'starter': {
        'name': 'Starter',
        'amount': 49900,  # ₹499
        'credits': Decimal('500.0000'),
        'description': '500 credits'
    },
    'pro': {
        'name': 'Pro',
        'amount': 99900,  # ₹999
        'credits': Decimal('1200.0000'),
        'description': '1,200 credits (+200 bonus)'
    },
    'business': {
        'name': 'Business',
        'amount': 199900,  # ₹1,999
        'credits': Decimal('2500.0000'),
        'description': '2,500 credits (+500 bonus)'
    }
}


def get_razorpay_client():
    """Get Razorpay client instance"""
    try:
        import razorpay
        if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
            logger.warning("Razorpay credentials not configured")
            return None
        return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except ImportError:
        logger.error("razorpay package not installed")
        return None


class PaymentService:
    """Service for handling Razorpay payments"""
    
    @staticmethod
    def get_plans() -> list:
        """Get available pricing plans"""
        return [
            {
                'id': plan_id,
                'name': plan['name'],
                'amount_inr': plan['amount'] / 100,  # Convert paise to rupees
                'credits': float(plan['credits']),
                'description': plan['description']
            }
            for plan_id, plan in PRICING_PLANS.items()
        ]
    
    @staticmethod
    def create_order(
        db: Session,
        mongo_user_id: str,
        plan_id: str,
        email: str = None
    ) -> Tuple[bool, dict]:
        """
        Create a Razorpay order for a plan.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            plan_id: Plan identifier (from database)
            email: User email
            
        Returns:
            Tuple of (success, order_data or error)
        """
        # Import here to avoid circular dependency
        from billing.settings_service import PlanService
        
        # Get plan from database (not hardcoded!)
        plan = PlanService.get_plan(db, plan_id)
        if plan is None:
            return False, {"error": f"Invalid plan: {plan_id}"}
        
        # Get or create user
        user = WalletService.get_or_create_user(db, mongo_user_id, email)
        
        client = get_razorpay_client()
        if client is None:
            return False, {"error": "Payment service not configured"}
        
        try:
            # Generate idempotency key
            idempotency_key = f"{mongo_user_id}_{plan_id}_{uuid.uuid4().hex[:8]}"
            
            # Database plan uses 'amount_paise' and 'total_credits'
            amount_paise = plan['amount_paise']
            total_credits = Decimal(str(plan['total_credits']))
            
            # Create Razorpay order
            order_data = client.order.create({
                'amount': amount_paise,
                'currency': 'INR',
                'receipt': idempotency_key,
                'notes': {
                    'user_id': mongo_user_id,
                    'plan_id': plan_id,
                    'credits': str(total_credits)
                }
            })
            
            # Store payment record
            payment = Payment(
                user_id=user.id,
                razorpay_order_id=order_data['id'],
                amount_inr=amount_paise,
                credits_added=total_credits,
                plan_id=plan_id,
                status='pending',
                idempotency_key=idempotency_key
            )
            db.add(payment)
            db.commit()
            
            logger.info(f"Created Razorpay order {order_data['id']} for plan {plan_id}")
            
            return True, {
                'order_id': order_data['id'],
                'amount': amount_paise,
                'currency': 'INR',
                'key_id': RAZORPAY_KEY_ID,
                'plan': plan['name'],
                'credits': float(total_credits)
            }
            
        except Exception as e:
            logger.error(f"Failed to create Razorpay order: {e}")
            return False, {"error": str(e)}
    
    @staticmethod
    def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
        """
        Verify Razorpay payment signature.
        
        Args:
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Signature from Razorpay
            
        Returns:
            True if signature is valid
        """
        if not RAZORPAY_KEY_SECRET:
            logger.error("Razorpay secret not configured")
            return False
        
        # Generate expected signature
        message = f"{order_id}|{payment_id}"
        expected_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    @staticmethod
    def complete_payment(
        db: Session,
        order_id: str,
        payment_id: str,
        signature: str
    ) -> Tuple[bool, dict]:
        """
        Complete a payment after client-side checkout.
        
        Args:
            db: Database session
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Razorpay signature
            
        Returns:
            Tuple of (success, result)
        """
        # Verify signature
        if not PaymentService.verify_signature(order_id, payment_id, signature):
            logger.warning(f"Invalid signature for order {order_id}")
            return False, {"error": "Invalid payment signature"}
        
        # Find payment record
        payment = db.query(Payment).filter(Payment.razorpay_order_id == order_id).first()
        
        if payment is None:
            return False, {"error": "Payment record not found"}
        
        if payment.status == 'completed':
            # Already processed (idempotent)
            return True, {
                "message": "Payment already processed",
                "credits_added": float(payment.credits_added)
            }
        
        # Update payment record
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.status = 'completed'
        payment.completed_at = datetime.utcnow()
        
        # Get user and add credits
        user = db.query(User).filter(User.id == payment.user_id).first()
        
        if user is None:
            payment.status = 'failed'
            payment.error_message = "User not found"
            db.commit()
            return False, {"error": "User not found"}
        
        # Add credits to wallet
        success, new_balance = WalletService.add_credits(
            db, 
            user.mongo_user_id, 
            payment.credits_added
        )
        
        if not success:
            payment.status = 'failed'
            payment.error_message = "Failed to add credits"
            db.commit()
            return False, {"error": "Failed to add credits"}
        
        db.commit()
        
        logger.info(f"Payment completed: {payment_id}, added {payment.credits_added} credits")
        
        return True, {
            "message": "Payment successful",
            "credits_added": float(payment.credits_added),
            "new_balance": float(new_balance),
            "plan": payment.plan_id
        }
    
    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> bool:
        """
        Verify Razorpay webhook signature.
        
        Args:
            payload: Raw request body
            signature: X-Razorpay-Signature header
            
        Returns:
            True if valid
        """
        if not RAZORPAY_WEBHOOK_SECRET:
            logger.error("Webhook secret not configured")
            return False
        
        expected = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def process_webhook(
        db: Session,
        event: str,
        payload: dict
    ) -> Tuple[bool, str]:
        """
        Process Razorpay webhook event.
        
        Args:
            db: Database session
            event: Event type (e.g., 'payment.captured')
            payload: Webhook payload
            
        Returns:
            Tuple of (success, message)
        """
        if event == 'payment.captured':
            payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment_entity.get('order_id')
            payment_id = payment_entity.get('id')
            
            if not order_id or not payment_id:
                return False, "Missing order_id or payment_id"
            
            # Find payment record
            payment = db.query(Payment).filter(
                Payment.razorpay_order_id == order_id
            ).first()
            
            if payment is None:
                return False, "Payment record not found"
            
            if payment.status == 'completed':
                return True, "Already processed"
            
            # Update and add credits
            payment.razorpay_payment_id = payment_id
            payment.status = 'completed'
            payment.completed_at = datetime.utcnow()
            
            user = db.query(User).filter(User.id == payment.user_id).first()
            if user:
                WalletService.add_credits(db, user.mongo_user_id, payment.credits_added)
            
            db.commit()
            
            logger.info(f"Webhook: Payment {payment_id} captured, added credits")
            return True, "Payment processed"
        
        elif event == 'payment.failed':
            payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment_entity.get('order_id')
            
            payment = db.query(Payment).filter(
                Payment.razorpay_order_id == order_id
            ).first()
            
            if payment:
                payment.status = 'failed'
                payment.error_message = payment_entity.get('error_description', 'Payment failed')
                db.commit()
            
            return True, "Payment failure recorded"
        
        return True, f"Event {event} ignored"
    
    @staticmethod
    def get_payment_history(
        db: Session,
        mongo_user_id: str,
        limit: int = 20
    ) -> list:
        """
        Get payment history for a user.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            limit: Max records
            
        Returns:
            List of payment records
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            return []
        
        payments = db.query(Payment).filter(
            Payment.user_id == user.id
        ).order_by(Payment.created_at.desc()).limit(limit).all()
        
        return [
            {
                'id': str(p.id),
                'order_id': p.razorpay_order_id,
                'payment_id': p.razorpay_payment_id,
                'amount_inr': p.amount_inr / 100,  # Convert to rupees
                'credits': float(p.credits_added),
                'plan': p.plan_id,
                'status': p.status,
                'created_at': p.created_at.isoformat() if p.created_at else None,
                'completed_at': p.completed_at.isoformat() if p.completed_at else None
            }
            for p in payments
        ]
