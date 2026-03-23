"""
Health Check Endpoint
"""
from fastapi import APIRouter
from sqlalchemy import text

from backend.database import SessionLocal

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify database and app status
    """
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        
        return {
            "status": "ok",
            "database": "connected",
            "message": "Job Finder Web App is running"
        }
    except Exception as e:
        return {
            "status": "error",
            "database": str(e),
            "message": "Database connection failed"
        }
