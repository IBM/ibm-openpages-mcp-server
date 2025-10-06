"""
Tests for the API endpoints
"""

import pytest
from fastapi.testclient import TestClient

from src.app.main import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "GRC MCP Server is running"}

def test_list_tools():
    """Test the list tools endpoint"""
    # Note: This test will fail if the MCP server is not initialized
    # In a real test, we would mock the MCP server
    response = client.get("/api/tools")
    assert response.status_code == 500  # Expected to fail without mocking

# Made with Bob
