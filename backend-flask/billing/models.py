"""
SQLAlchemy Models for Billing System
Tables auto-created on startup via Base.metadata.create_all()
PostgreSQL only - no SQLite support
"""
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Index, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()


def generate_uuid():
    """Generate a UUID string for cross-database compatibility"""
    return str(uuid.uuid4())


class User(Base):
    """User table - links to MongoDB auth via mongo_user_id"""
    __tablename__ = 'billing_users'
    
    # Use String(36) instead of UUID for SQLite compatibility
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    plan = Column(String(50), default='free')
    mongo_user_id = Column(String(50), unique=True, index=True)  # Links to MongoDB auth
    is_suspended = Column(Boolean, default=False)  # User management
    low_credit_notified = Column(Boolean, default=False)  # Track if low credit email sent
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email}>"


class Wallet(Base):
    """Wallet for storing user credits"""
    __tablename__ = 'wallets'
    
    user_id = Column(String(36), ForeignKey('billing_users.id', ondelete='CASCADE'), primary_key=True)
    credits_remaining = Column(Numeric(12, 4), nullable=False, default=0)
    total_credits_purchased = Column(Numeric(12, 4), default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="wallet")
    
    def __repr__(self):
        return f"<Wallet user={self.user_id} credits={self.credits_remaining}>"


class UsageLog(Base):
    """Log of token/credit usage per query"""
    __tablename__ = 'usage_logs'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('billing_users.id', ondelete='CASCADE'), nullable=False)
    chatbot_id = Column(String(100), index=True)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    credits_used = Column(Numeric(10, 4), nullable=False, default=0)
    session_id = Column(String(100))
    query_text = Column(Text)  # Optional: store truncated query for debugging
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    user = relationship("User", back_populates="usage_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_usage_user_date', 'user_id', 'created_at'),
        Index('idx_usage_chatbot', 'chatbot_id', 'created_at'),
    )
    
    def __repr__(self):
        return f"<UsageLog tokens={self.total_tokens} credits={self.credits_used}>"


class Payment(Base):
    """Payment records for Razorpay transactions"""
    __tablename__ = 'payments'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('billing_users.id', ondelete='CASCADE'), nullable=False)
    razorpay_order_id = Column(String(100), index=True)
    razorpay_payment_id = Column(String(100), index=True)
    razorpay_signature = Column(String(255))
    amount_inr = Column(Integer, nullable=False)  # Amount in paise (100 paise = ₹1)
    credits_added = Column(Numeric(10, 4), nullable=False)
    plan_id = Column(String(50))  # starter, pro, business
    status = Column(String(20), default='pending', index=True)  # pending, completed, failed, refunded
    idempotency_key = Column(String(100), unique=True)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationship
    user = relationship("User", back_populates="payments")
    
    # Indexes
    __table_args__ = (
        Index('idx_payments_user', 'user_id'),
        Index('idx_payments_order', 'razorpay_order_id'),
        Index('idx_payments_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Payment {self.razorpay_order_id} status={self.status}>"


class BillingSetting(Base):
    """Admin-configurable billing settings"""
    __tablename__ = 'billing_settings'
    
    key = Column(String(50), primary_key=True)
    value = Column(Text, nullable=False)  # JSON-encoded value
    description = Column(String(255))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100))  # Admin email/ID who changed it
    
    def __repr__(self):
        return f"<BillingSetting {self.key}={self.value}>"


class SubscriptionPlan(Base):
    """Dynamic subscription plans (admin-configurable)"""
    __tablename__ = 'subscription_plans'
    
    id = Column(String(50), primary_key=True)  # e.g., 'starter', 'pro'
    name = Column(String(100), nullable=False)  # Display name
    description = Column(String(255))
    amount_paise = Column(Integer, nullable=False)  # Price in paise
    credits = Column(Numeric(12, 4), nullable=False)  # Credits granted
    bonus_credits = Column(Numeric(12, 4), default=0)  # Bonus included
    is_active = Column(Boolean, default=True)  # Available for purchase
    sort_order = Column(Integer, default=0)  # Display order
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<SubscriptionPlan {self.id} ₹{self.amount_paise/100}>"


class AuditLog(Base):
    """Audit log for tracking admin actions"""
    __tablename__ = 'audit_logs'
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    admin_user_id = Column(String(50), nullable=False, index=True)  # MongoDB user ID
    admin_email = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False, index=True)  # 'ADD_CREDITS', 'UPDATE_SETTING', etc.
    target_type = Column(String(50))  # 'user', 'setting', 'plan', etc.
    target_id = Column(String(100), index=True)
    details = Column(Text)  # JSON-encoded details
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_admin_date', 'admin_user_id', 'timestamp'),
        Index('idx_audit_action_date', 'action', 'timestamp'),
        Index('idx_audit_target', 'target_type', 'target_id'),
    )
    
    def __repr__(self):
        return f"<AuditLog {self.action} by {self.admin_email}>"
