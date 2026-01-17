"""
Migration Script: JSON to MongoDB
Run this once to migrate existing agent data from JSON file to MongoDB.

Usage:
    python migrate_to_mongodb.py

Requirements:
    - MongoDB must be running
    - Set MONGODB_URI environment variable (optional, defaults to localhost)
"""

import os
import json
from pymongo import MongoClient
from datetime import datetime

# Configuration
MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/chatbot-generator')
JSON_FILE = './faiss_db/agents_metadata.json'


def migrate():
    print("=" * 50)
    print("🔄 Agent Data Migration: JSON → MongoDB")
    print("=" * 50)
    
    # Check if JSON file exists
    if not os.path.exists(JSON_FILE):
        print(f"❌ JSON file not found: {JSON_FILE}")
        print("   No data to migrate.")
        return
    
    # Load existing data from JSON
    print(f"\n📂 Loading data from: {JSON_FILE}")
    with open(JSON_FILE, 'r') as f:
        agents = json.load(f)
    
    if not agents:
        print("⚠️  No agents found in JSON file.")
        return
    
    print(f"   Found {len(agents)} agents to migrate")
    
    # Connect to MongoDB
    print(f"\n🔌 Connecting to MongoDB: {MONGODB_URI}")
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # Test connection
        client.admin.command('ping')
        print("   ✅ Connected successfully!")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        print("\n   Make sure MongoDB is running and MONGODB_URI is correct.")
        return
    
    # Get database and collection
    db_name = MONGODB_URI.split('/')[-1].split('?')[0] or 'agentic-chatbot'
    db = client[db_name]
    collection = db['agents']
    
    print(f"\n📦 Target database: {db_name}")
    print(f"   Target collection: agents")
    
    # Migration
    print(f"\n🚀 Starting migration...")
    migrated = 0
    skipped = 0
    errors = 0
    
    for agent_key, agent_data in agents.items():
        try:
            # Prepare document
            doc = {
                '_id': agent_key,
                **agent_data,
                'migrated_at': datetime.now().isoformat()
            }
            
            # Check if already exists
            existing = collection.find_one({'_id': agent_key})
            if existing:
                print(f"   ⏭️  Skipping '{agent_key}' (already exists)")
                skipped += 1
                continue
            
            # Insert document
            collection.insert_one(doc)
            print(f"   ✅ Migrated: {agent_key}")
            migrated += 1
            
        except Exception as e:
            print(f"   ❌ Error migrating '{agent_key}': {e}")
            errors += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Migration Summary")
    print("=" * 50)
    print(f"   ✅ Migrated: {migrated}")
    print(f"   ⏭️  Skipped:  {skipped}")
    print(f"   ❌ Errors:   {errors}")
    print(f"   📄 Total:    {len(agents)}")
    
    # Backup recommendation
    if migrated > 0:
        print("\n💡 Tip: Keep your JSON file as backup:")
        print(f"   Original: {JSON_FILE}")
        backup_name = JSON_FILE.replace('.json', '_backup.json')
        print(f"   Backup:   {backup_name}")
    
    print("\n✨ Migration complete!")
    client.close()


if __name__ == '__main__':
    migrate()
