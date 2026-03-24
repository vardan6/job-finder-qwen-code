#!/usr/bin/env python3
"""
Migration Script - Create platform_accounts table

Run this script once to add platform accounts support.
"""
import sqlite3
from pathlib import Path

# Find the database
DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "jobs.db"

if not DB_PATH.exists():
    print(f"❌ Database not found at {DB_PATH}")
    print("Please run the application first to create the database.")
    exit(1)

print(f"📌 Migrating database: {DB_PATH}")

# Connect to database
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='platform_accounts'
    """)
    table_exists = cursor.fetchone() is not None
    
    if not table_exists:
        print("➕ Creating platform_accounts table...")
        cursor.execute("""
            CREATE TABLE platform_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                email_encrypted TEXT,
                cookies_encrypted TEXT,
                status TEXT DEFAULT 'inactive',
                last_used_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
            )
        """)
        print("   ✅ platform_accounts table created")
    else:
        print("   ℹ️  platform_accounts table already exists")
    
    conn.commit()
    print("\n✅ Migration completed successfully!")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Migration failed: {e}")
    exit(1)
finally:
    conn.close()
