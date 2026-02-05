"""
Tests for the API endpoints
"""

import pytest
import sys
import os
from fastapi.testclient import TestClient

# Add the project root to the path to import main
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    # Check that the response contains expected keys
    assert "status" in data
    assert data["status"] == "GRC MCP Server is running"

def test_list_tools():
    """Test the list tools endpoint"""
    # Note: This endpoint doesn't exist in the current implementation
    # The test expects a 404 Not Found response
    response = client.get("/api/tools")
    assert response.status_code == 404  # Endpoint not implemented

# Made with Bob
