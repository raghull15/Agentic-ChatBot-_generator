"""
PostgreSQL to MongoDB Migration Script
Migrates all billing data from PostgreSQL to MongoDB

Usage:
    # Dry run (no changes)
    python migrate_postgres_to_mongodb.py --dry-run
    
    # Actual migration
    python migrate_postgres_to_mongodb.py
"""

import sys
import argparse
from datetime import datetime
from decimal import Decimal
from typing import Dict, List
import logging

from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import BulkWriteError
from bson import ObjectId, Decimal128
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()


class PostgresToMongoMigrator:
    """Migrates billing data from PostgreSQL to MongoDB"""
    
    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        
        # PostgreSQL connection
        pg_url = os.getenv('POSTGRES_URL', 'postgresql://postgres:postgres@localhost/billing_db')
        self.pg_engine = create_engine(pg_url)
        self.pg_session = sessionmaker(bind=self.pg_engine)()
        
        # MongoDB connection
        mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        mongo_db_name = os.getenv('MONGO_DB_NAME', 'agentic_bot')
        self.mongo_client = MongoClient(mongo_url)
        self.mongo_db = self.mongo_client[mongo_db_name]
        
        # Statistics
        self.stats = {
            'users_migrated': 0,
            'payments_migrated': 0,
            'usage_logs_migrated': 0,
            'settings_migrated': 0,
            'plans_migrated': 0,
            'audit_logs_migrated': 0,
            'errors': []
        }
    
    def decimal_to_decimal128(self, value):
        """Convert Python Decimal to MongoDB Decimal128"""
        if value is None:
            return Decimal128("0")
        return Decimal128(str(value))
    
    def migrate_billing_users(self):
        """Migrate billing_users + wallets (embedded)"""
        logger.info("=" * 60)
        logger.info("Migrating billing_users with embedded wallets...")
        
        # Fetch all users with wallets (JOIN)
        query = text("""
            SELECT 
                u.id, u.email, u.mongo_user_id, u.is_suspended, 
                u.low_credit_notified, u.created_at,
                w.credits_remaining, w.total_credits_purchased, w.updated_at as wallet_updated
            FROM billing_users u
            LEFT JOIN wallets w ON u.id = w.user_id
        """)
        
        result = self.pg_session.execute(query)
        users = result.fetchall()
        
        logger.info(f"Found {len(users)} users to migrate")
        
        # Prepare MongoDB documents
        mongo_users = []
        mongo_user_id_map = {}  # PG UUID -> Mongo ObjectId
        
        for user in users:
            mongo_id = ObjectId()
            mongo_user_id_map[user[0]] = mongo_id  # Store for reference
            
            doc = {
                '_id': mongo_id,
                'mongoUserId': ObjectId(user[2]) if user[2] else None,
                'email': user[1],
                'isSuspended': user[3] or False,
                'lowCreditNotified': user[4] or False,
                'wallet': {
                    'creditsRemaining': self.decimal_to_decimal128(user[6]),
                    'totalCreditsPurchased': self.decimal_to_decimal128(user[7]),
                    'updatedAt': user[8] or datetime.utcnow()
                },
                'createdAt': user[5] or datetime.utcnow()
            }
            mongo_users.append(doc)
        
        # Insert into MongoDB
        if not self.dry_run:
            try:
                if mongo_users:
                    self.mongo_db.billing_users.insert_many(mongo_users, ordered=False)
                logger.info(f"✅ Inserted {len(mongo_users)} users")
            except BulkWriteError as e:
                logger.error(f"❌ Bulk write error: {e.details}")
                self.stats['errors'].append(('billing_users', str(e)))
        else:
            logger.info(f"[DRY RUN] Would insert {len(mongo_users)} users")
        
        self.stats['users_migrated'] = len(mongo_users)
        
        # Save mapping for other migrations
        self.pg_to_mongo_user_map = mongo_user_id_map
        
        return mongo_user_id_map
    
    def migrate_payments(self, user_map: Dict[str, ObjectId]):
        """Migrate payments table"""
        logger.info("=" * 60)
        logger.info("Migrating payments...")
        
        query = text("SELECT * FROM payments ORDER BY created_at")
        result = self.pg_session.execute(query)
        payments = result.fetchall()
        
        logger.info(f"Found {len(payments)} payments to migrate")
        
        mongo_payments = []
        for payment in payments:
            user_mongo_id = user_map.get(payment[1])  # user_id
            if not user_mongo_id:
                logger.warning(f"User {payment[1]} not found in map, skipping payment")
                continue
            
            doc = {
                '_id': ObjectId(),
                'userId': user_mongo_id,
                'razorpayOrderId': payment[2],
                'razorpayPaymentId': payment[3],
                'razorpaySignature': payment[4],
                'amountPaise': payment[5],
                'creditsAdded': self.decimal_to_decimal128(payment[6]),
                'planId': payment[7],
                'status': payment[8],
                'idempotencyKey': payment[9],
                'errorMessage': payment[10],
                'createdAt': payment[11] or datetime.utcnow(),
                'completedAt': payment[12]
            }
            mongo_payments.append(doc)
        
        if not self.dry_run and mongo_payments:
            try:
                self.mongo_db.payments.insert_many(mongo_payments, ordered=False)
                logger.info(f"✅ Inserted {len(mongo_payments)} payments")
            except BulkWriteError as e:
                logger.error(f"❌ Bulk write error: {e.details}")
                self.stats['errors'].append(('payments', str(e)))
        else:
            logger.info(f"[DRY RUN] Would insert {len(mongo_payments)} payments")
        
        self.stats['payments_migrated'] = len(mongo_payments)
    
    def migrate_usage_logs(self, user_map: Dict[str, ObjectId]):
        """Migrate usage_logs (in batches)"""
        logger.info("=" * 60)
        logger.info("Migrating usage_logs...")
        
        # Count total
        count_query = text("SELECT COUNT(*) FROM usage_logs")
        total = self.pg_session.execute(count_query).scalar()
        logger.info(f"Found {total} usage logs to migrate")
        
        if total == 0:
            logger.info("No usage logs to migrate")
            return
        
        batch_size = 5000
        offset = 0
        migrated = 0
        
        while offset < total:
            query = text(f"""
                SELECT * FROM usage_logs 
                ORDER BY created_at 
                LIMIT {batch_size} OFFSET {offset}
            """)
            result = self.pg_session.execute(query)
            logs = result.fetchall()
            
            if not logs:
                break
            
            mongo_logs = []
            for log in logs:
                user_mongo_id = user_map.get(log[1])
                if not user_mongo_id:
                    continue
                
                doc = {
                    '_id': ObjectId(),
                    'userId': user_mongo_id,
                    'agentId': None,
                    'agentName': log[2],
                    'inputTokens': log[3],
                    'outputTokens': log[4],
                    'totalTokens': log[5],
                    'creditsUsed': self.decimal_to_decimal128(log[6]),
                    'sessionId': log[7],
                    'queryText': log[8],
                    'createdAt': log[9] or datetime.utcnow()
                }
                mongo_logs.append(doc)
            
            if not self.dry_run and mongo_logs:
                try:
                    self.mongo_db.usage_logs.insert_many(mongo_logs, ordered=False)
                    migrated += len(mongo_logs)
                    logger.info(f"✅ Batch {offset//batch_size + 1}: {len(mongo_logs)} logs (Total: {migrated}/{total})")
                except BulkWriteError as e:
                    logger.error(f"❌ Bulk write error: {e.details}")
                    self.stats['errors'].append(('usage_logs', str(e)))
            else:
                logger.info(f"[DRY RUN] Batch {len(mongo_logs)} logs")
                migrated += len(mongo_logs)
            
            offset += batch_size
        
        self.stats['usage_logs_migrated'] = migrated
    
    def migrate_settings(self):
        """Migrate billing_settings"""
        logger.info("=" * 60)
        logger.info("Migrating settings...")
        
        query = text("SELECT * FROM billing_settings")
        result = self.pg_session.execute(query)
        settings = result.fetchall()
        
        logger.info(f"Found {len(settings)} settings to migrate")
        
        mongo_settings = []
        for setting in settings:
            import json
            
            # Parse JSON value
            try:
                value = json.loads(setting[1])
            except:
                value = setting[1]
            
            doc = {
                '_id': setting[0],  # Use key as _id
                'value': value,
                'description': setting[2],
                'updatedAt': setting[3] or datetime.utcnow(),
                'updatedBy': setting[4]
            }
            mongo_settings.append(doc)
        
        if not self.dry_run and mongo_settings:
            try:
                self.mongo_db.settings.insert_many(mongo_settings, ordered=False)
                logger.info(f"✅ Inserted {len(mongo_settings)} settings")
            except BulkWriteError as e:
                logger.error(f"❌ Bulk write error: {e.details}")
                self.stats['errors'].append(('settings', str(e)))
        else:
            logger.info(f"[DRY RUN] Would insert {len(mongo_settings)} settings")
        
        self.stats['settings_migrated'] = len(mongo_settings)
    
    def migrate_subscription_plans(self):
        """Migrate subscription_plans"""
        logger.info("=" * 60)
        logger.info("Migrating subscription plans...")
        
        query = text("SELECT * FROM subscription_plans")
        result = self.pg_session.execute(query)
        plans = result.fetchall()
        
        logger.info(f"Found {len(plans)} plans to migrate")
        
        mongo_plans = []
        for plan in plans:
            doc = {
                '_id': plan[0],  # Use plan ID as _id
                'name': plan[1],
                'description': plan[2],
                'amountPaise': plan[3],
                'credits': self.decimal_to_decimal128(plan[4]),
                'bonusCredits': self.decimal_to_decimal128(plan[5]),
                'isActive': plan[6],
                'sortOrder': plan[7],
                'createdAt': plan[8] or datetime.utcnow(),
                'updatedAt': plan[9] or datetime.utcnow()
            }
            mongo_plans.append(doc)
        
        if not self.dry_run and mongo_plans:
            try:
                self.mongo_db.subscription_plans.insert_many(mongo_plans, ordered=False)
                logger.info(f"✅ Inserted {len(mongo_plans)} plans")
            except BulkWriteError as e:
                logger.error(f"❌ Bulk write error: {e.details}")
                self.stats['errors'].append(('plans', str(e)))
        else:
            logger.info(f"[DRY RUN] Would insert {len(mongo_plans)} plans")
        
        self.stats['subscription_plans_migrated'] = len(mongo_plans)
    
    def migrate_audit_logs(self, user_map: Dict[str, ObjectId]):
        """Migrate audit_logs"""
        logger.info("=" * 60)
        logger.info("Migrating audit logs...")
        
        query = text("SELECT * FROM audit_logs ORDER BY timestamp")
        result = self.pg_session.execute(query)
        logs = result.fetchall()
        
        logger.info(f"Found {len(logs)} audit logs to migrate")
        
        mongo_logs = []
        for log in logs:
            import json
            details = None
            if log[6]:
                try:
                    details = json.loads(log[6])
                except:
                    details = log[6]
            
            doc = {
                '_id': ObjectId(),
                'adminUserId': ObjectId(log[1]) if log[1] else None,
                'adminEmail': log[2],
                'action': log[3],
                'targetType': log[4],
                'targetId': log[5],
                'details': details,
                'ipAddress': log[7],
                'userAgent': log[8],
                'timestamp': log[9] or datetime.utcnow()
            }
            mongo_logs.append(doc)
        
        if not self.dry_run and mongo_logs:
            try:
                self.mongo_db.audit_logs.insert_many(mongo_logs, ordered=False)
                logger.info(f"✅ Inserted {len(mongo_logs)} audit logs")
            except BulkWriteError as e:
                logger.error(f"❌ Bulk write error: {e.details}")
                self.stats['errors'].append(('audit_logs', str(e)))
        else:
            logger.info(f"[DRY RUN] Would insert {len(mongo_logs)} audit logs")
        
        self.stats['audit_logs_migrated'] = len(mongo_logs)
    
    def create_indexes(self):
        """Create all MongoDB indexes"""
        logger.info("=" * 60)
        logger.info("Creating MongoDB indexes...")
        
        if self.dry_run:
            logger.info("[DRY RUN] Would create indexes")
            return
        
        # billing_users indexes
        self.mongo_db.billing_users.create_index([('mongoUserId', ASCENDING)], unique=True, sparse=True)
        self.mongo_db.billing_users.create_index([('email', ASCENDING)], unique=True)
        self.mongo_db.billing_users.create_index([('wallet.creditsRemaining', ASCENDING)])
        logger.info("✅ billing_users indexes created")
        
        # payments indexes
        self.mongo_db.payments.create_index([('userId', ASCENDING), ('createdAt', DESCENDING)])
        self.mongo_db.payments.create_index([('razorpayOrderId', ASCENDING)], unique=True, sparse=True)
        self.mongo_db.payments.create_index([('status', ASCENDING), ('createdAt', DESCENDING)])
        self.mongo_db.payments.create_index([('idempotencyKey', ASCENDING)], unique=True, sparse=True)
        logger.info("✅ payments indexes created")
        
        # usage_logs indexes
        self.mongo_db.usage_logs.create_index([('userId', ASCENDING), ('createdAt', DESCENDING)])
        self.mongo_db.usage_logs.create_index([('agentName', ASCENDING), ('createdAt', DESCENDING)])
        # TTL index (90 days)
        self.mongo_db.usage_logs.create_index(
            [('createdAt', ASCENDING)],
            expireAfterSeconds=7776000
        )
        logger.info("✅ usage_logs indexes created (with TTL)")
        
        # subscription_plans indexes
        self.mongo_db.subscription_plans.create_index([('sortOrder', ASCENDING), ('isActive', ASCENDING)])
        logger.info("✅ subscription_plans indexes created")
        
        # audit_logs indexes
        self.mongo_db.audit_logs.create_index([('adminUserId', ASCENDING), ('timestamp', DESCENDING)])
        self.mongo_db.audit_logs.create_index([('action', ASCENDING), ('timestamp', DESCENDING)])
        self.mongo_db.audit_logs.create_index([('targetType', ASCENDING), ('targetId', ASCENDING)])
        self.mongo_db.audit_logs.create_index([('timestamp', DESCENDING)])
        logger.info("✅ audit_logs indexes created")
    
    def validate_migration(self):
        """Validate data integrity"""
        logger.info("=" * 60)
        logger.info("Validating migration...")
        
        if self.dry_run:
            logger.info("[DRY RUN] Skipping validation")
            return
        
        # Count documents
        pg_users = self.pg_session.execute(text("SELECT COUNT(*) FROM billing_users")).scalar()
        mongo_users = self.mongo_db.billing_users.count_documents({})
        
        pg_payments = self.pg_session.execute(text("SELECT COUNT(*) FROM payments")).scalar()
        mongo_payments = self.mongo_db.payments.count_documents({})
        
        logger.info(f"Users: PG={pg_users}, Mongo={mongo_users} {'✅' if pg_users == mongo_users else '❌'}")
        logger.info(f"Payments: PG={pg_payments}, Mongo={mongo_payments} {'✅' if pg_payments == mongo_payments else '❌'}")
        
        # Sample validation
        sample_user = self.pg_session.execute(text("""
            SELECT u.email, w.credits_remaining 
            FROM billing_users u 
            JOIN wallets w ON u.id = w.user_id 
            LIMIT 1
        """)).fetchone()
        
        if sample_user:
            mongo_user = self.mongo_db.billing_users.find_one({'email': sample_user[0]})
            if mongo_user:
                pg_credits = float(sample_user[1])
                mongo_credits = float(mongo_user['wallet']['creditsRemaining'].to_decimal())
                logger.info(f"Sample user credits: PG={pg_credits}, Mongo={mongo_credits} {'✅' if abs(pg_credits - mongo_credits) < 0.0001 else '❌'}")
    
    def run(self):
        """Run complete migration"""
        logger.info("\n" + "=" * 60)
        logger.info("POSTGRESQL TO MONGODB MIGRATION")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE MIGRATION'}")
        logger.info("=" * 60 + "\n")
        
        try:
            user_map = self.migrate_billing_users()
            self.migrate_payments(user_map)
            self.migrate_usage_logs(user_map)
            self.migrate_settings()
            self.migrate_subscription_plans()
            self.migrate_audit_logs(user_map)
            self.create_indexes()
            self.validate_migration()
            
            logger.info("\n" + "=" * 60)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Users migrated: {self.stats['users_migrated']}")
            logger.info(f"Payments migrated: {self.stats['payments_migrated']}")
            logger.info(f"Usage logs migrated: {self.stats['usage_logs_migrated']}")
            logger.info(f"Settings migrated: {self.stats['settings_migrated']}")
            logger.info(f"Plans migrated: {self.stats['subscription_plans_migrated']}")
            logger.info(f"Audit logs migrated: {self.stats['audit_logs_migrated']}")
            
            if self.stats['errors']:
                logger.error(f"\n❌ Errors: {len(self.stats['errors'])}")
                for collection, error in self.stats['errors']:
                    logger.error(f"  - {collection}: {error}")
            else:
                logger.info("\n✅ Migration completed successfully!")
            
            logger.info("=" * 60 + "\n")
        
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            self.pg_session.close()
            self.mongo_client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Migrate PostgreSQL billing data to MongoDB')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without making changes')
    args = parser.parse_args()
    
    migrator = PostgresToMongoMigrator(dry_run=args.dry_run)
    migrator.run()
