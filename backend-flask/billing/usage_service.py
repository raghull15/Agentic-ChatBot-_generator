"""
Usage Service - Logs token/credit usage per query
"""
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from billing.models import User, UsageLog
from billing.token_service import tokens_to_credits

logger = logging.getLogger(__name__)


class UsageService:
    """Service for logging and querying usage data"""
    
    @staticmethod
    def log_usage(
        db: Session,
        mongo_user_id: str,
        chatbot_id: str,
        input_tokens: int,
        output_tokens: int,
        session_id: str = None,
        query_text: str = None
    ) -> Optional[UsageLog]:
        """
        Log token usage for a query.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            chatbot_id: Agent/chatbot identifier
            input_tokens: Input (prompt) tokens
            output_tokens: Output (completion) tokens
            session_id: Optional session ID
            query_text: Optional truncated query for debugging
            
        Returns:
            UsageLog object or None if failed
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            logger.warning(f"Cannot log usage - user not found: {mongo_user_id}")
            return None
        
        total_tokens = input_tokens + output_tokens
        credits_used = tokens_to_credits(total_tokens)
        
        usage_log = UsageLog(
            user_id=user.id,
            chatbot_id=chatbot_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            credits_used=credits_used,
            session_id=session_id,
            query_text=query_text[:500] if query_text else None  # Truncate
        )
        
        db.add(usage_log)
        db.commit()
        
        logger.debug(f"Logged usage: {total_tokens} tokens, {credits_used} credits for {mongo_user_id}")
        return usage_log
    
    @staticmethod
    def get_usage_history(
        db: Session,
        mongo_user_id: str,
        limit: int = 50,
        offset: int = 0,
        chatbot_id: str = None
    ) -> List[dict]:
        """
        Get usage history for a user.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            limit: Max records to return
            offset: Pagination offset
            chatbot_id: Optional filter by chatbot
            
        Returns:
            List of usage records
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            return []
        
        query = db.query(UsageLog).filter(UsageLog.user_id == user.id)
        
        if chatbot_id:
            query = query.filter(UsageLog.chatbot_id == chatbot_id)
        
        logs = query.order_by(desc(UsageLog.created_at)).offset(offset).limit(limit).all()
        
        return [
            {
                "id": str(log.id),
                "chatbot_id": log.chatbot_id,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "total_tokens": log.total_tokens,
                "credits_used": float(log.credits_used),
                "session_id": log.session_id,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    
    @staticmethod
    def get_usage_summary(
        db: Session,
        mongo_user_id: str,
        days: int = 30
    ) -> dict:
        """
        Get usage summary for a user over a period.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            days: Number of days to look back
            
        Returns:
            Summary dict with totals
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            return {
                "total_queries": 0,
                "total_tokens": 0,
                "total_credits": 0,
                "period_days": days
            }
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        result = db.query(
            func.count(UsageLog.id).label('query_count'),
            func.sum(UsageLog.total_tokens).label('total_tokens'),
            func.sum(UsageLog.credits_used).label('total_credits')
        ).filter(
            UsageLog.user_id == user.id,
            UsageLog.created_at >= start_date
        ).first()
        
        return {
            "total_queries": result.query_count or 0,
            "total_tokens": result.total_tokens or 0,
            "total_credits": float(result.total_credits or 0),
            "period_days": days
        }
    
    @staticmethod
    def get_daily_breakdown(
        db: Session,
        mongo_user_id: str,
        days: int = 7
    ) -> List[dict]:
        """
        Get daily usage breakdown.
        
        Args:
            db: Database session
            mongo_user_id: User ID from MongoDB auth
            days: Number of days
            
        Returns:
            List of daily usage records
        """
        user = db.query(User).filter(User.mongo_user_id == mongo_user_id).first()
        
        if user is None:
            return []
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # SQLAlchemy date truncation
        results = db.query(
            func.date(UsageLog.created_at).label('date'),
            func.count(UsageLog.id).label('queries'),
            func.sum(UsageLog.total_tokens).label('tokens'),
            func.sum(UsageLog.credits_used).label('credits')
        ).filter(
            UsageLog.user_id == user.id,
            UsageLog.created_at >= start_date
        ).group_by(
            func.date(UsageLog.created_at)
        ).order_by(
            func.date(UsageLog.created_at)
        ).all()
        
        return [
            {
                "date": str(r.date),
                "queries": r.queries or 0,
                "tokens": r.tokens or 0,
                "credits": float(r.credits or 0)
            }
            for r in results
        ]
