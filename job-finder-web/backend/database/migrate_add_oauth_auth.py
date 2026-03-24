"""
Database Migration - Add OAuth authentication fields to llm_providers

Run this once to update the database schema for Claude Code OAuth support.
"""
from sqlalchemy import text
from backend.database import SessionLocal


def migrate():
    """Add OAuth authentication columns to llm_providers table"""
    db = SessionLocal()
    
    try:
        # Check if columns already exist
        result = db.execute(text("PRAGMA table_info(llm_providers)"))
        columns = [row[1] for row in result.fetchall()]
        
        # Add auth_method column
        if 'auth_method' in columns:
            print("ℹ️  Column 'auth_method' already exists")
        else:
            db.execute(text(
                "ALTER TABLE llm_providers ADD COLUMN auth_method VARCHAR(50) DEFAULT 'api_key'"
            ))
            print("✅ Added 'auth_method' column")
        
        # Add oauth_token_encrypted column
        if 'oauth_token_encrypted' in columns:
            print("ℹ️  Column 'oauth_token_encrypted' already exists")
        else:
            db.execute(text(
                "ALTER TABLE llm_providers ADD COLUMN oauth_token_encrypted TEXT"
            ))
            print("✅ Added 'oauth_token_encrypted' column")
        
        # Add oauth_refresh_token_encrypted column
        if 'oauth_refresh_token_encrypted' in columns:
            print("ℹ️  Column 'oauth_refresh_token_encrypted' already exists")
        else:
            db.execute(text(
                "ALTER TABLE llm_providers ADD COLUMN oauth_refresh_token_encrypted TEXT"
            ))
            print("✅ Added 'oauth_refresh_token_encrypted' column")
        
        # Add oauth_expires_at column
        if 'oauth_expires_at' in columns:
            print("ℹ️  Column 'oauth_expires_at' already exists")
        else:
            db.execute(text(
                "ALTER TABLE llm_providers ADD COLUMN oauth_expires_at DATETIME"
            ))
            print("✅ Added 'oauth_expires_at' column")
        
        # Add oauth_subscription_type column
        if 'oauth_subscription_type' in columns:
            print("ℹ️  Column 'oauth_subscription_type' already exists")
        else:
            db.execute(text(
                "ALTER TABLE llm_providers ADD COLUMN oauth_subscription_type VARCHAR(50)"
            ))
            print("✅ Added 'oauth_subscription_type' column")
        
        db.commit()
        print("✅ Migration completed successfully")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
