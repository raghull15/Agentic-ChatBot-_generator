"""
MongoDB-based Usage Service
Tracks token usage and credit consumption
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from decimal import Decimal

from pymongo.database import Database
from bson import ObjectId, Decimal128

from billing.mongodb import get_mongo_db, decimal_to_decimal128, decimal128_to_decimal

logger = logging.getLogger(__name__)


class UsageServiceMongo:
    """MongoDB-based usage tracking service"""
    
    @staticmethod
    def log_usage(db: Database, mongo_user_id: str, agent_name: str, 
                  input_tokens: int, output_tokens: int, 
                  session_id: str = None, query_text: str = None):
        """
        Log token usage for a query
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            agent_name: Name of the chatbot/agent
            input_tokens: Input/prompt tokens
            output_tokens: Output/completion tokens
            session_id: Optional session ID
            query_text: Optional query text (truncated)
        """
        # Get billing user ID
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'_id': 1}
        )
        
        if not user:
            logger.warning(f"Billing user not found for {mongo_user_id}")
            return
        
        # Calculate credits used
        from billing.settings_service_mongo import SettingsServiceMongo
        tokens_per_credit = SettingsServiceMongo.get_tokens_per_credit(db)
        total_tokens = input_tokens + output_tokens
        credits_used = Decimal(str(total_tokens)) / Decimal(str(tokens_per_credit))
        
        # Create usage log
        usage_log = {
            'userId': user['_id'],
            'agentId': None,  # Can be populated if agent stored in MongoDB
            'agentName': agent_name,
            'inputTokens': input_tokens,
            'outputTokens': output_tokens,
            'totalTokens': total_tokens,
            'creditsUsed': decimal_to_decimal128(credits_used),
            'sessionId': session_id,
            'queryText': query_text[:100] if query_text else None,  # Truncate
            'createdAt': datetime.utcnow()
        }
        
        db.usage_logs.insert_one(usage_log)
        logger.debug(f"Logged usage: {total_tokens} tokens, {credits_used:.4f} credits for {mongo_user_id}")
    
    @staticmethod
    def get_user_usage(db: Database, mongo_user_id: str, days: int = 30, limit: int = 100) -> List[Dict]:
        """
        Get user's usage history
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            days: Number of days to look back
            limit: Maximum results
            
        Returns:
            List of usage log dicts
        """
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'_id': 1}
        )
        
        if not user:
            return []
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        logs = list(db.usage_logs.find(
            {
                'userId': user['_id'],
                'createdAt': {'$gte': cutoff}
            },
            {'queryText': 0}  # Exclude query text
        ).sort('createdAt', -1).limit(limit))
        
        # Convert Decimal128 to float for JSON
        for log in logs:
            log['creditsUsed'] = float(log['creditsUsed'].to_decimal()) if log.get('creditsUsed') else 0
            log['_id'] = str(log['_id'])
            log['userId'] = str(log['userId'])
        
        return logs
    
    @staticmethod
    def get_usage_stats(db: Database, mongo_user_id: str, days: int = 30) -> Dict:
        """
        Get aggregated usage statistics
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            days: Number of days
            
        Returns:
            Stats dict
        """
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'_id': 1}
        )
        
        if not user:
            return {
                'total_queries': 0,
                'total_tokens': 0,
                'total_credits_used': 0.0,
                'average_tokens_per_query': 0
            }
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {
                '$match': {
                    'userId': user['_id'],
                    'createdAt': {'$gte': cutoff}
                }
            },
            {
                '$group': {
                    '_id': None,
                    'totalQueries': {'$sum': 1},
                    'totalTokens': {'$sum': '$totalTokens'},
                    'totalCreditsUsed': {'$sum': '$creditsUsed'},
                    'avgTokens': {'$avg': '$totalTokens'}
                }
            }
        ]
        
        result = list(db.usage_logs.aggregate(pipeline))
        
        if not result:
            return {
                'total_queries': 0,
                'total_tokens': 0,
                'total_credits_used': 0.0,
                'average_tokens_per_query': 0
            }
        
        stats = result[0]
        return {
            'total_queries': stats.get('totalQueries', 0),
            'total_tokens': stats.get('totalTokens', 0),
            'total_credits_used': float(stats.get('totalCreditsUsed', Decimal128("0")).to_decimal()),
            'average_tokens_per_query': int(stats.get('avgTokens', 0))
        }
    
    @staticmethod
    def get_top_agents(db: Database, limit: int = 10, days: int = 30) -> List[Dict]:
        """
        Get most used agents across all users
        
        Args:
            db: MongoDB database
            limit: Number of results
            days: Time period
            
        Returns:
            List of {agent_name, query_count, total_tokens}
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {'$match': {'createdAt': {'$gte': cutoff}}},
            {
                '$group': {
                    '_id': '$agentName',
                    'queryCount': {'$sum': 1},
                    'totalTokens': {'$sum': '$totalTokens'}
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
                'total_tokens': r['totalTokens']
            }
            for r in results
        ]
    
    @staticmethod
    def get_top_users(db: Database, limit: int = 10, days: int = 30) -> List[Dict]:
        """
        Get most active users by token usage
        
        Args:
            db: MongoDB database
            limit: Number of results
            days: Time period
            
        Returns:
            List of {user_id, email, query_count, total_tokens}
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {'$match': {'createdAt': {'$gte': cutoff}}},
            {
                '$group': {
                    '_id': '$userId',
                    'queryCount': {'$sum': 1},
                    'totalTokens': {'$sum': '$totalTokens'}
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
                'total_tokens': r['totalTokens']
            }
            for r in results
        ]
    
    @staticmethod
    def get_usage_history(db: Database, mongo_user_id: str, limit: int = 50, chatbot_id: str = None) -> List[Dict]:
        """
        Get user's usage history - API compatible method
        
        Args:
            db: MongoDB database
            mongo_user_id: User ID
            limit: Maximum results
            chatbot_id: Optional filter by chatbot/agent
            
        Returns:
            List of usage log dicts
        """
        user = db.billing_users.find_one(
            {'mongoUserId': ObjectId(mongo_user_id)},
            {'_id': 1}
        )
        
        if not user:
            return []
        
        query = {'userId': user['_id']}
        if chatbot_id:
            query['agentName'] = chatbot_id
        
        logs = list(db.usage_logs.find(
            query,
            {'queryText': 0}  # Exclude query text
        ).sort('createdAt', -1).limit(limit))
        
        # Convert for JSON response
        result = []
        for log in logs:
            credits_used = log.get('creditsUsed')
            if hasattr(credits_used, 'to_decimal'):
                credits_used = float(credits_used.to_decimal())
            else:
                credits_used = float(credits_used or 0)
            
            result.append({
                'id': str(log['_id']),
                'chatbot_id': log.get('agentName'),
                'input_tokens': log.get('inputTokens', 0),
                'output_tokens': log.get('outputTokens', 0),
                'total_tokens': log.get('totalTokens', 0),
                'credits_used': credits_used,
                'session_id': log.get('sessionId'),
                'created_at': log.get('createdAt').isoformat() if log.get('createdAt') else None
            })
        
        return result
    
    @staticmethod
    def get_usage_summary(db: Database, mongo_user_id: str, days: int = 30) -> Dict:
        """
        Get usage summary for a user - API compatible method
        Alias for get_usage_stats with frontend-expected field names
        """
        stats = UsageServiceMongo.get_usage_stats(db, mongo_user_id, days)
        return stats

