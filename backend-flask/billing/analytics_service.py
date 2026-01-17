"""
Analytics Service - Usage statistics and charts data
"""

import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from billing.models import User, UsageLog, Payment, Wallet

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for usage and billing analytics"""

    @staticmethod
    def get_usage_stats(db: Session, days: int = 30) -> dict:
        """Get overall usage statistics"""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = (
            db.query(
                func.count(UsageLog.id).label("total_queries"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.credits_used).label("total_credits"),
            )
            .filter(UsageLog.created_at >= start_date)
            .first()
        )

        # Count active users (users who made queries)
        active_users = (
            db.query(func.count(func.distinct(UsageLog.user_id)))
            .filter(UsageLog.created_at >= start_date)
            .scalar()
        )

        return {
            "period_days": days,
            "total_queries": result.total_queries or 0,
            "total_tokens": result.total_tokens or 0,
            "total_credits": float(result.total_credits or 0),
            "active_users": active_users or 0,
            "avg_tokens_per_query": round(
                (result.total_tokens or 0) / max(result.total_queries or 1, 1), 2
            ),
        }

    @staticmethod
    def get_daily_usage(db: Session, days: int = 14) -> List[dict]:
        """Get daily usage breakdown for charts"""
        start_date = datetime.utcnow() - timedelta(days=days)

        results = (
            db.query(
                func.date(UsageLog.created_at).label("date"),
                func.count(UsageLog.id).label("queries"),
                func.sum(UsageLog.total_tokens).label("tokens"),
                func.sum(UsageLog.credits_used).label("credits"),
            )
            .filter(UsageLog.created_at >= start_date)
            .group_by(func.date(UsageLog.created_at))
            .order_by(func.date(UsageLog.created_at))
            .all()
        )

        return [
            {
                "date": str(r.date),
                "queries": r.queries or 0,
                "tokens": r.tokens or 0,
                "credits": float(r.credits or 0),
            }
            for r in results
        ]

    @staticmethod
    def get_hourly_usage(db: Session, hours: int = 24) -> List[dict]:
        """Get hourly usage for today"""
        start_time = datetime.utcnow() - timedelta(hours=hours)

        results = (
            db.query(
                func.strftime("%H", UsageLog.created_at).label("hour"),
                func.count(UsageLog.id).label("queries"),
                func.sum(UsageLog.total_tokens).label("tokens"),
            )
            .filter(UsageLog.created_at >= start_time)
            .group_by(func.strftime("%H", UsageLog.created_at))
            .all()
        )

        return [
            {"hour": r.hour, "queries": r.queries or 0, "tokens": r.tokens or 0}
            for r in results
        ]

    @staticmethod
    def get_top_users(db: Session, limit: int = 10, days: int = 30) -> List[dict]:
        """Get top users by usage with real emails from MongoDB"""
        start_date = datetime.utcnow() - timedelta(days=days)

        results = (
            db.query(
                User.email,
                User.mongo_user_id,
                func.count(UsageLog.id).label("query_count"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.credits_used).label("credits_used"),
            )
            .join(UsageLog, User.id == UsageLog.user_id)
            .filter(UsageLog.created_at >= start_date)
            .group_by(User.id)
            .order_by(
                desc(func.count(UsageLog.id))  # Sort by query count instead of credits
            )
            .limit(limit)
            .all()
        )

        # Fetch real emails from MongoDB
        try:
            from db import get_users_collection
            from bson.objectid import ObjectId

            users_collection = get_users_collection()
            logger.info(f"DEBUG: users_collection = {users_collection}")
            top_users = []

            for r in results:
                email = r.email

                # If it's a placeholder email, try to get real email from MongoDB
                logger.info(
                    f"DEBUG: Checking users_collection, is None: {users_collection is None}"
                )
                if users_collection:
                    try:
                        mongo_user = users_collection.find_one(
                            {"_id": ObjectId(r.mongo_user_id)}
                        )
                        if mongo_user and "email" in mongo_user:
                            email = mongo_user["email"]
                    except Exception as e:
                        logger.warning(
                            f"Could not fetch email for user {r.mongo_user_id}: {e}"
                        )

                top_users.append(
                    {
                        "email": email,
                        "user_id": r.mongo_user_id,
                        "query_count": r.query_count or 0,
                        "total_tokens": r.total_tokens or 0,
                        "credits_used": float(r.credits_used or 0),
                    }
                )

            return top_users

        except Exception as e:
            logger.error(f"Error fetching top users: {e}")
            # Fallback to original data
            return [
                {
                    "email": r.email,
                    "user_id": r.mongo_user_id,
                    "query_count": r.query_count or 0,
                    "total_tokens": r.total_tokens or 0,
                    "credits_used": float(r.credits_used or 0),
                }
                for r in results
            ]

    @staticmethod
    def get_top_agents(db: Session, limit: int = 10, days: int = 30) -> List[dict]:
        """Get most used agents/chatbots with names from MongoDB"""
        start_date = datetime.utcnow() - timedelta(days=days)

        results = (
            db.query(
                UsageLog.chatbot_id,
                func.count(UsageLog.id).label("query_count"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.count(func.distinct(UsageLog.user_id)).label("unique_users"),
            )
            .filter(UsageLog.created_at >= start_date, UsageLog.chatbot_id.isnot(None))
            .group_by(UsageLog.chatbot_id)
            .order_by(desc(func.count(UsageLog.id)))
            .limit(limit)
            .all()
        )

        # Fetch chatbot names from MongoDB
        try:
            from db import get_agents_collection
            from bson.objectid import ObjectId

            agents_collection = get_agents_collection()
            top_agents = []

            for r in results:
                chatbot_name = r.chatbot_id  # Default to ID

                # Try to get chatbot name from MongoDB
                if agents_collection:
                    try:
                        agent = agents_collection.find_one(
                            {"_id": ObjectId(r.chatbot_id)}
                        )
                        if agent and "name" in agent:
                            chatbot_name = agent["name"]
                    except Exception as e:
                        logger.warning(
                            f"Could not fetch name for chatbot {r.chatbot_id}: {e}"
                        )

                top_agents.append(
                    {
                        "chatbot_id": r.chatbot_id,
                        "name": chatbot_name,
                        "query_count": r.query_count or 0,
                        "total_tokens": r.total_tokens or 0,
                        "unique_users": r.unique_users or 0,
                    }
                )

            return top_agents

        except Exception as e:
            logger.error(f"Error fetching top agents: {e}")
            # Fallback to original data
            return [
                {
                    "chatbot_id": r.chatbot_id,
                    "name": r.chatbot_id,  # Use ID as name
                    "query_count": r.query_count or 0,
                    "total_tokens": r.total_tokens or 0,
                    "unique_users": r.unique_users or 0,
                }
                for r in results
            ]

    @staticmethod
    def get_revenue_stats(db: Session, days: int = 30) -> dict:
        """Get revenue statistics"""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = (
            db.query(
                func.count(Payment.id).label("total_payments"),
                func.sum(Payment.amount_inr).label("total_amount"),
                func.sum(Payment.credits_added).label("total_credits"),
            )
            .filter(Payment.status == "completed", Payment.created_at >= start_date)
            .first()
        )

        return {
            "period_days": days,
            "total_payments": result.total_payments or 0,
            "total_amount_paise": result.total_amount or 0,
            "total_amount_inr": (result.total_amount or 0) / 100,
            "total_credits_sold": float(result.total_credits or 0),
        }

    @staticmethod
    def get_daily_revenue(db: Session, days: int = 14) -> List[dict]:
        """Get daily revenue for charts"""
        start_date = datetime.utcnow() - timedelta(days=days)

        results = (
            db.query(
                func.date(Payment.created_at).label("date"),
                func.count(Payment.id).label("payments"),
                func.sum(Payment.amount_inr).label("amount"),
                func.sum(Payment.credits_added).label("credits"),
            )
            .filter(Payment.status == "completed", Payment.created_at >= start_date)
            .group_by(func.date(Payment.created_at))
            .order_by(func.date(Payment.created_at))
            .all()
        )

        return [
            {
                "date": str(r.date),
                "payments": r.payments or 0,
                "amount_inr": (r.amount or 0) / 100,
                "credits": float(r.credits or 0),
            }
            for r in results
        ]

    @staticmethod
    def get_plan_breakdown(db: Session, days: int = 30) -> List[dict]:
        """Get revenue breakdown by plan"""
        start_date = datetime.utcnow() - timedelta(days=days)

        results = (
            db.query(
                Payment.plan_id,
                func.count(Payment.id).label("count"),
                func.sum(Payment.amount_inr).label("amount"),
                func.sum(Payment.credits_added).label("credits"),
            )
            .filter(Payment.status == "completed", Payment.created_at >= start_date)
            .group_by(Payment.plan_id)
            .all()
        )

        return [
            {
                "plan_id": r.plan_id or "unknown",
                "count": r.count or 0,
                "amount_inr": (r.amount or 0) / 100,
                "credits": float(r.credits or 0),
            }
            for r in results
        ]

    @staticmethod
    def get_user_summary(db: Session) -> dict:
        """Get user summary stats"""
        total_users = db.query(func.count(User.id)).scalar() or 0
        suspended_users = (
            db.query(func.count(User.id)).filter(User.is_suspended).scalar() or 0
        )

        # Users with credits
        users_with_credits = (
            db.query(func.count(Wallet.user_id))
            .filter(Wallet.credits_remaining > 0)
            .scalar()
            or 0
        )

        # Total credits in system
        total_credits = db.query(func.sum(Wallet.credits_remaining)).scalar() or 0

        return {
            "total_users": total_users,
            "suspended_users": suspended_users,
            "active_users": total_users - suspended_users,
            "users_with_credits": users_with_credits,
            "total_credits_in_wallets": float(total_credits),
        }
