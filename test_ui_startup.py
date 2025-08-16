#!/usr/bin/env python3
"""
Test script to start FastAPI server for UI testing without requiring real Gemini API key.
This bypasses the Gemini API key validation for UI testing purposes only.
"""

import os
import sys
import asyncio
import uvicorn
from pathlib import Path

# Add the project directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "fastapi_server"))

# Set test environment variable
os.environ["GEMINI_API_KEY"] = "test_key_for_ui_testing"

# Monkey patch the Gemini API key validation for testing
def mock_validate_gemini_api_key(cls, v, info):
    """Mock validator that accepts test keys."""
    return v or "test_key_for_ui_testing"

# Apply the monkey patch
from fastapi_server.config import FastAPIServerConfig
FastAPIServerConfig.validate_gemini_api_key = classmethod(mock_validate_gemini_api_key)

# Now import the main app
from fastapi_server.main import app

if __name__ == "__main__":
    print("Starting FastAPI server for UI testing...")
    print("Note: This uses a mock Gemini API key for UI testing only.")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        reload=False
    )