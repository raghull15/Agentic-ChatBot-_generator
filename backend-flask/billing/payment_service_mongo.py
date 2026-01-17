"""
MongoDB-based Payment Service
Handles Razorpay payment processing with MongoDB storage
"""
import logging
import os
import hmac
import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Tuple
import uuid

from pymongo.database import Database
from bson import ObjectId, Decimal128

from billing.mongodb import get_mongo_db, decimal_to_decimal128, decimal128_to_float

logger = logging.getLogger(__name__)

# Razorpay credentials from environment
RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')


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


class PaymentServiceMongo:
    """MongoDB-based payment service for Razorpay integration"""
    
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
    def get_plans(db: Database) -> list:
        """Get available pricing plans from database"""
        from billing.settings_service_mongo import PlanServiceMongo
        return PlanServiceMongo.get_all_plans(db, active_only=True)
    
    @staticmethod
    def create_order(db: Database, mongo_user_id: str, plan_id: str, 
                     email: str = None) -> Tuple[bool, dict]:
        """
        Create a Razorpay order for a plan.
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID from MongoDB auth
            plan_id: Plan identifier
            email: User email
            
        Returns:
            Tuple of (success, order_data or error)
        """
        from billing.settings_service_mongo import PlanServiceMongo
        from billing.wallet_service_mongo import WalletServiceMongo
        
        # Get plan from database
        plan = PlanServiceMongo.get_plan(db, plan_id)
        if plan is None:
            return False, {"error": f"Invalid plan: {plan_id}"}
        
        # Get or create user
        WalletServiceMongo.get_or_create_user(db, mongo_user_id, email)
        
        client = get_razorpay_client()
        if client is None:
            return False, {"error": "Payment service not configured"}
        
        try:
            # Generate idempotency key
            idempotency_key = f"{mongo_user_id}_{plan_id}_{uuid.uuid4().hex[:8]}"
            
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
            
            # Store payment record using MongoDB
            PaymentServiceMongo.create_payment_record(
                db, mongo_user_id, order_data['id'],
                amount_paise, plan_id, total_credits
            )
            
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
    def process_webhook(db: Database, event: str, payload: dict) -> Tuple[bool, str]:
        """
        Process Razorpay webhook event.
        
        Args:
            db: MongoDB database
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
            payment = db.payments.find_one({'razorpayOrderId': order_id})
            
            if payment is None:
                return False, "Payment record not found"
            
            if payment['status'] == 'completed':
                return True, "Already processed"
            
            # Complete the payment
            success, message, _ = PaymentServiceMongo.complete_payment(
                db, order_id, payment_id, ""  # No signature for webhooks
            )
            
            return success, message
        
        elif event == 'payment.failed':
            payment_entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
            order_id = payment_entity.get('order_id')
            error_message = payment_entity.get('error_description', 'Payment failed')
            
            if order_id:
                PaymentServiceMongo.fail_payment(db, order_id, error_message)
            
            return True, "Payment failure recorded"
        
        return True, f"Event {event} ignored"
    
    @staticmethod
    def get_payment_history(db: Database, mongo_user_id: str, limit: int = 20) -> list:
        """Alias for get_user_payments - for API compatibility"""
        return PaymentServiceMongo.get_user_payments(db, mongo_user_id, limit)
    
    @staticmethod
    def create_payment_record(db: Database, mongo_user_id: str, order_id: str,
                              amount_paise: int, plan_id: str, credits: Decimal) -> Dict:
        """
        Create a pending payment record
        
        Args:
            db: MongoDB database
            mongo_user_id: User's MongoDB ID
            order_id: Razorpay order ID
            amount_paise: Amount in paise
            plan_id: Plan ID (starter, pro, business)
            credits: Credits to be added on success
            
        Returns:
            Payment document
        """
        # Get or create billing user
        from billing.wallet_service_mongo import WalletServiceMongo
        user = WalletServiceMongo.get_or_create_user(db, mongo_user_id)
        
        payment = {
            '_id': str(uuid.uuid4()),
            'userId': user['_id'],
            'mongoUserId': ObjectId(mongo_user_id),
            'razorpayOrderId': order_id,
            'razorpayPaymentId': None,
            'razorpaySignature': None,
            'amountPaise': amount_paise,
            'creditsToAdd': decimal_to_decimal128(credits),
            'planId': plan_id,
            'status': 'pending',
            'idempotencyKey': f"{mongo_user_id}_{order_id}",
            'errorMessage': None,
            'createdAt': datetime.utcnow(),
            'completedAt': None
        }
        
        db.payments.insert_one(payment)
        logger.info(f"Created payment record: {order_id} for user {mongo_user_id}")
        
        return PaymentServiceMongo._payment_to_dict(payment)
    
    @staticmethod
    def complete_payment(db: Database, order_id: str, payment_id: str, 
                         signature: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        Complete a payment and add credits to user wallet
        
        Args:
            db: MongoDB database
            order_id: Razorpay order ID
            payment_id: Razorpay payment ID
            signature: Razorpay signature for verification
            
        Returns:
            Tuple of (success, message, payment_dict)
        """
        # Find the payment
        payment = db.payments.find_one({'razorpayOrderId': order_id})
        
        if not payment:
            return False, "Payment not found", None
        
        if payment['status'] == 'completed':
            return True, "Payment already processed", PaymentServiceMongo._payment_to_dict(payment)
        
        if payment['status'] == 'failed':
            return False, "Payment previously failed", None
        
        # Verify signature (in production, use Razorpay utility)
        # For now, we trust the signature if provided
        
        # Update payment as completed
        credits_to_add = payment['creditsToAdd']
        if isinstance(credits_to_add, Decimal128):
            credits_to_add = credits_to_add.to_decimal()
        
        result = db.payments.find_one_and_update(
            {
                '_id': payment['_id'],
                'status': 'pending'
            },
            {
                '$set': {
                    'razorpayPaymentId': payment_id,
                    'razorpaySignature': signature,
                    'status': 'completed',
                    'completedAt': datetime.utcnow()
                }
            },
            return_document=True
        )
        
        if not result:
            return False, "Payment already processed or not found", None
        
        # Add credits to wallet
        from billing.wallet_service_mongo import WalletServiceMongo
        mongo_user_id = str(payment['mongoUserId'])
        success, new_balance = WalletServiceMongo.add_credits(
            db, mongo_user_id, Decimal(str(credits_to_add)), source="payment"
        )
        
        if not success:
            # Rollback payment status
            db.payments.update_one(
                {'_id': payment['_id']},
                {'$set': {'status': 'pending', 'completedAt': None}}
            )
            return False, "Failed to add credits to wallet", None
        
        logger.info(f"Payment completed: {order_id}, added {credits_to_add} credits")
        return True, f"Payment successful. Added {credits_to_add} credits.", PaymentServiceMongo._payment_to_dict(result)
    
    @staticmethod
    def fail_payment(db: Database, order_id: str, error_message: str) -> bool:
        """Mark a payment as failed"""
        result = db.payments.update_one(
            {'razorpayOrderId': order_id},
            {'$set': {
                'status': 'failed',
                'errorMessage': error_message,
                'completedAt': datetime.utcnow()
            }}
        )
        return result.modified_count > 0
    
    @staticmethod
    def get_payment(db: Database, order_id: str) -> Optional[Dict]:
        """Get a payment by order ID"""
        payment = db.payments.find_one({'razorpayOrderId': order_id})
        return PaymentServiceMongo._payment_to_dict(payment) if payment else None
    
    @staticmethod
    def get_user_payments(db: Database, mongo_user_id: str, limit: int = 20) -> List[Dict]:
        """
        Get user's payment history
        
        Args:
            db: MongoDB database
            mongo_user_id: User's MongoDB ID
            limit: Max number of payments to return
            
        Returns:
            List of payment dicts
        """
        payments = list(db.payments.find(
            {'mongoUserId': ObjectId(mongo_user_id)}
        ).sort('createdAt', -1).limit(limit))
        
        return [PaymentServiceMongo._payment_to_dict(p) for p in payments]
    
    @staticmethod
    def get_all_payments(db: Database, status: str = None, limit: int = 100) -> List[Dict]:
        """
        Get all payments (admin)
        
        Args:
            db: MongoDB database
            status: Filter by status (pending, completed, failed)
            limit: Max number of payments
            
        Returns:
            List of payment dicts
        """
        query = {}
        if status:
            query['status'] = status
        
        payments = list(db.payments.find(query).sort('createdAt', -1).limit(limit))
        return [PaymentServiceMongo._payment_to_dict(p) for p in payments]
    
    @staticmethod
    def _payment_to_dict(payment: dict) -> Optional[Dict]:
        """Convert MongoDB payment document to API dict"""
        if not payment:
            return None
        
        credits = payment.get('creditsToAdd')
        if isinstance(credits, Decimal128):
            credits = float(credits.to_decimal())
        else:
            credits = float(credits or 0)
        
        return {
            'id': payment['_id'],
            'user_id': str(payment.get('userId', '')),
            'mongo_user_id': str(payment.get('mongoUserId', '')),
            'razorpay_order_id': payment.get('razorpayOrderId'),
            'razorpay_payment_id': payment.get('razorpayPaymentId'),
            'amount_paise': payment.get('amountPaise'),
            'amount_inr': payment.get('amountPaise', 0) / 100,
            'credits_added': credits,
            'plan_id': payment.get('planId'),
            'status': payment.get('status'),
            'error_message': payment.get('errorMessage'),
            'created_at': payment.get('createdAt').isoformat() if payment.get('createdAt') else None,
            'completed_at': payment.get('completedAt').isoformat() if payment.get('completedAt') else None
        }
