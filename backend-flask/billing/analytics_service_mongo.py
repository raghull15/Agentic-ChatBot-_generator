"""
MongoDB-based Analytics Service
Provides usage analytics and reporting using MongoDB aggregation pipelines
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from decimal import Decimal

from pymongo.database import Database
from bson import ObjectId, Decimal128

from billing.mongodb import get_mongo_db, decimal128_to_float

logger = logging.getLogger(__name__)


class AnalyticsServiceMongo:
    """MongoDB-based analytics service"""
    
    @staticmethod
    def get_usage_summary(db: Database, days: int = 30) -> Dict:
        """
        Get overall usage summary for the past N days
        
        Args:
            db: MongoDB database
            days: Number of days to analyze
            
        Returns:
            Summary dict with totals
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {'$match': {'createdAt': {'$gte': cutoff}}},
            {
                '$group': {
                    '_id': None,
                    'totalQueries': {'$sum': 1},
                    'totalTokens': {'$sum': '$totalTokens'},
                    'totalInputTokens': {'$sum': '$inputTokens'},
                    'totalOutputTokens': {'$sum': '$outputTokens'},
                    'totalCreditsUsed': {'$sum': '$creditsUsed'},
                    'uniqueUsers': {'$addToSet': '$userId'},
                    'uniqueAgents': {'$addToSet': '$agentName'}
                }
            }
        ]
        
        result = list(db.usage_logs.aggregate(pipeline))
        
        if not result:
            return {
                'total_queries': 0,
                'total_tokens': 0,
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_credits_used': 0.0,
                'unique_users': 0,
                'unique_agents': 0,
                'period_days': days
            }
        
        data = result[0]
        credits_used = data.get('totalCreditsUsed')
        if isinstance(credits_used, Decimal128):
            credits_used = float(credits_used.to_decimal())
        else:
            credits_used = float(credits_used or 0)
        
        return {
            'total_queries': data.get('totalQueries', 0),
            'total_tokens': data.get('totalTokens', 0),
            'total_input_tokens': data.get('totalInputTokens', 0),
            'total_output_tokens': data.get('totalOutputTokens', 0),
            'total_credits_used': credits_used,
            'unique_users': len(data.get('uniqueUsers', [])),
            'unique_agents': len(data.get('uniqueAgents', [])),
            'period_days': days
        }
    
    @staticmethod
    def get_daily_usage(db: Database, days: int = 30) -> List[Dict]:
        """
        Get daily usage breakdown
        
        Args:
            db: MongoDB database
            days: Number of days
            
        Returns:
            List of daily usage dicts
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {'$match': {'createdAt': {'$gte': cutoff}}},
            {
                '$group': {
                    '_id': {
                        'year': {'$year': '$createdAt'},
                        'month': {'$month': '$createdAt'},
                        'day': {'$dayOfMonth': '$createdAt'}
                    },
                    'queries': {'$sum': 1},
                    'tokens': {'$sum': '$totalTokens'},
                    'credits': {'$sum': '$creditsUsed'}
                }
            },
            {'$sort': {'_id.year': 1, '_id.month': 1, '_id.day': 1}}
        ]
        
        results = list(db.usage_logs.aggregate(pipeline))
        
        return [
            {
                'date': f"{r['_id']['year']}-{r['_id']['month']:02d}-{r['_id']['day']:02d}",
                'queries': r['queries'],
                'tokens': r['tokens'],
                'credits': decimal128_to_float(r['credits'])
            }
            for r in results
        ]
    
    @staticmethod
    def get_top_users(db: Database, limit: int = 10, days: int = 30) -> List[Dict]:
        """
        Get top users by token usage
        
        Args:
            db: MongoDB database
            limit: Number of users to return
            days: Time period
            
        Returns:
            List of user usage dicts
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {'$match': {'createdAt': {'$gte': cutoff}}},
            {
                '$group': {
                    '_id': '$userId',
                    'queryCount': {'$sum': 1},
                    'totalTokens': {'$sum': '$totalTokens'},
                    'totalCredits': {'$sum': '$creditsUsed'}
                }
            },
            {'$sort': {'totalTokens': -1}},
            {'$limit': limit},
            {
                '$lookup': {
                    'from': 'billing_users',
                    'localField': '_id',
                    'foreignField': '_id',
                    'as': 'user'
                }
            },
            {'$unwind': {'path': '$user', 'preserveNullAndEmptyArrays': True}}
        ]
        
        results = list(db.usage_logs.aggregate(pipeline))
        
        return [
            {
                'user_id': str(r['_id']),
                'email': r.get('user', {}).get('email', 'Unknown'),
                'query_count': r['queryCount'],
                'total_tokens': r['totalTokens'],
                'total_credits': decimal128_to_float(r['totalCredits'])
            }
            for r in results
        ]
    
    @staticmethod
    def get_top_agents(db: Database, limit: int = 10, days: int = 30) -> List[Dict]:
        """
        Get most used agents
        
        Args:
            db: MongoDB database
            limit: Number of agents to return
            days: Time period
            
        Returns:
            List of agent usage dicts
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {'$match': {'createdAt': {'$gte': cutoff}}},
            {
                '$group': {
                    '_id': '$agentName',
                    'queryCount': {'$sum': 1},
                    'totalTokens': {'$sum': '$totalTokens'},
                    'uniqueUsers': {'$addToSet': '$userId'}
                }
            },
            {'$sort': {'queryCount': -1}},
            {'$limit': limit}
        ]
        
        results = list(db.usage_logs.aggregate(pipeline))
        
        return [
            {
                'agent_name': r['_id'],
                'query_count': r['queryCount'],
                'total_tokens': r['totalTokens'],
                'unique_users': len(r['uniqueUsers'])
            }
            for r in results
        ]
    
    @staticmethod
    def get_revenue_summary(db: Database, days: int = 30) -> Dict:
        """
        Get revenue summary from payments
        
        Args:
            db: MongoDB database
            days: Number of days
            
        Returns:
            Revenue summary dict
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {
                '$match': {
                    'status': 'completed',
                    'completedAt': {'$gte': cutoff}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'totalPayments': {'$sum': 1},
                    'totalRevenuePaise': {'$sum': '$amountPaise'},
                    'totalCreditsAdded': {'$sum': '$creditsToAdd'},
                    'uniqueCustomers': {'$addToSet': '$mongoUserId'}
                }
            }
        ]
        
        result = list(db.payments.aggregate(pipeline))
        
        if not result:
            return {
                'total_payments': 0,
                'total_revenue_inr': 0.0,
                'total_credits_sold': 0.0,
                'unique_customers': 0,
                'period_days': days
            }
        
        data = result[0]
        credits = data.get('totalCreditsAdded')
        if isinstance(credits, Decimal128):
            credits = float(credits.to_decimal())
        else:
            credits = float(credits or 0)
        
        return {
            'total_payments': data.get('totalPayments', 0),
            'total_revenue_inr': data.get('totalRevenuePaise', 0) / 100,
            'total_credits_sold': credits,
            'unique_customers': len(data.get('uniqueCustomers', [])),
            'period_days': days
        }
    
    @staticmethod
    def get_user_summary(db: Database) -> Dict:
        """Get user summary statistics"""
        total_users = db.billing_users.count_documents({})
        suspended_users = db.billing_users.count_documents({'isSuspended': True})
        
        # Get users with positive balance
        pipeline = [
            {'$match': {'wallet.creditsRemaining': {'$gt': Decimal128('0')}}},
            {'$count': 'count'}
        ]
        result = list(db.billing_users.aggregate(pipeline))
        users_with_credits = result[0]['count'] if result else 0
        
        return {
            'total_users': total_users,
            'suspended_users': suspended_users,
            'active_users': total_users - suspended_users,
            'users_with_credits': users_with_credits
        }
    
    @staticmethod
    def get_usage_stats(db: Database, days: int = 30) -> Dict:
        """
        Alias for get_usage_summary - for API compatibility
        """
        return AnalyticsServiceMongo.get_usage_summary(db, days)
