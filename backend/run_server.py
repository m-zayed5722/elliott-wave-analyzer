#!/usr/bin/env python3
"""
Simple script to run the Elliott Wave Analyzer backend server
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import app
import uvicorn

if __name__ == "__main__":
    print("Starting Elliott Wave Analyzer Backend...")
    print("Backend will be available at: http://127.0.0.1:8000")
    print("API Documentation at: http://127.0.0.1:8000/docs")
    print("Press Ctrl+C to stop the server")
    
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=8000,
        log_level="info"
    )