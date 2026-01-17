"""
Database Migration - Add missing columns to billing_users table
Run this script to add is_suspended and low_credit_notified columns if they don't exist
"""
import sqlite3
import os

# Path to billing database
DB_PATH = "./billing.db"

def migrate_billing_db():
    """Add missing columns to billing_users table"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check current schema
        cursor.execute("PRAGMA table_info(billing_users)")
        columns = {row[1] for row in cursor.fetchall()}
        print(f"Current columns in billing_users: {columns}")
        
        # Add is_suspended if missing
        if 'is_suspended' not in columns:
            print("Adding is_suspended column...")
            cursor.execute("""
                ALTER TABLE billing_users 
                ADD COLUMN is_suspended INTEGER DEFAULT 0
            """)
            print("[OK] Added is_suspended column")
        else:
            print("[OK] is_suspended column already exists")
        
        # Add low_credit_notified if missing
        if 'low_credit_notified' not in columns:
            print("Adding low_credit_notified column...")
            cursor.execute("""
                ALTER TABLE billing_users 
                ADD COLUMN low_credit_notified INTEGER DEFAULT 0
            """)
            print("[OK] Added low_credit_notified column")
        else:
            print("[OK] low_credit_notified column already exists")
        
        conn.commit()
        print("\n[SUCCESS] Database migration completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_billing_db()
