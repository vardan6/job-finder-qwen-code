#!/usr/bin/env python3
"""
Job Finder Web App - Entry Point

Run this file to start the application.
"""
import sys
import socket
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path.parent))

from backend.app import app
from backend.config import HOST, PORT, DEBUG
import uvicorn


def find_available_port(start_port: int, host: str, max_attempts: int = 10) -> int:
    """
    Find an available port starting from start_port.
    Checks sequentially: start_port, start_port+1, start_port+2, etc.
    Returns the first available port found.
    """
    for port_offset in range(max_attempts):
        port = start_port + port_offset
        try:
            # Try to bind to the port to check if it's available
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                return port
        except OSError:
            # Port is in use, try next one
            continue
    
    # If no port found in range, raise error
    raise RuntimeError(
        f"Could not find an available port in range {start_port}-{start_port + max_attempts - 1}. "
        f"All ports are in use."
    )


if __name__ == "__main__":
    print("🚀 Starting Job Finder Web App...")
    
    # Find available port
    actual_port = find_available_port(PORT, HOST)
    
    if actual_port != PORT:
        print(f"⚠️  Port {PORT} is in use, using port {actual_port} instead")
    else:
        print(f"📌 Using port {actual_port}")
    
    print(f"📌 Open browser: http://{HOST}:{actual_port}")
    print(f"📌 Debug mode: {DEBUG}")
    print("")
    print("Press CTRL+C to stop the application")
    print("")

    uvicorn.run(
        "backend.app:app",
        host=HOST,
        port=actual_port,
        reload=DEBUG
    )
