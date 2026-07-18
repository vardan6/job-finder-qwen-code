#!/usr/bin/env python3
"""
Migration Script - Add is_enabled and source_document_id to candidate_skills

Run this script once to update your existing database schema.
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
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(candidate_skills)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Add is_enabled column if missing
    if "is_enabled" not in columns:
        print("➕ Adding is_enabled column...")
        cursor.execute("ALTER TABLE candidate_skills ADD COLUMN is_enabled BOOLEAN DEFAULT 1")
        print("   ✅ is_enabled column added")
    else:
        print("   ℹ️  is_enabled column already exists")
    
    # Add source_document_id column if missing
    if "source_document_id" not in columns:
        print("➕ Adding source_document_id column...")
        cursor.execute("ALTER TABLE candidate_skills ADD COLUMN source_document_id INTEGER REFERENCES candidate_documents(id) ON DELETE SET NULL")
        print("   ✅ source_document_id column added")
    else:
        print("   ℹ️  source_document_id column already exists")
    
    conn.commit()
    print("\n✅ Migration completed successfully!")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Migration failed: {e}")
    exit(1)
finally:
    conn.close()
