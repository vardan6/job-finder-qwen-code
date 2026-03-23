#!/usr/bin/env python3
"""
Job Finder Web App - Entry Point

Run this file to start the application.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path.parent))

from backend.app import app
from backend.config import HOST, PORT, DEBUG
import uvicorn

if __name__ == "__main__":
    print("🚀 Starting Job Finder Web App...")
    print(f"📌 Open browser: http://{HOST}:{PORT}")
    print(f"📌 Debug mode: {DEBUG}")
    print("")
    print("Press CTRL+C to stop the application")
    print("")
    
    uvicorn.run(
        "backend.app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )
