"""
Database Migration - Add description and source_document_id to candidate_job_titles

Run this once to update the database schema.
"""
from sqlalchemy import text
from backend.database import SessionLocal, engine


def migrate():
    """Add new columns to candidate_job_titles table"""
    db = SessionLocal()
    
    try:
        # Check if columns already exist
        result = db.execute(text("PRAGMA table_info(candidate_job_titles)"))
        columns = [row[1] for row in result.fetchall()]
        
        if 'description' in columns:
            print("ℹ️  Column 'description' already exists")
        else:
            # Add description column
            db.execute(text(
                "ALTER TABLE candidate_job_titles ADD COLUMN description TEXT"
            ))
            print("✅ Added 'description' column")
        
        if 'source_document_id' in columns:
            print("ℹ️  Column 'source_document_id' already exists")
        else:
            # Add source_document_id column
            db.execute(text(
                "ALTER TABLE candidate_job_titles ADD COLUMN source_document_id INTEGER"
            ))
            print("✅ Added 'source_document_id' column")
        
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
