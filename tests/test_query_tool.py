"""
Tests for the OpenPages Query Tool
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.app.tools.query_tool import QueryTool
from src.app.core.openpages_client import OpenPagesClient


@pytest.fixture
def mock_client():
    """Create a mock OpenPages client"""
    client = MagicMock(spec=OpenPagesClient)
    client.base_url = "https://test.openpages.com"
    return client


@pytest.fixture
def query_tool(mock_client):
    """Create a QueryTool instance with mock client"""
    return QueryTool(mock_client)


@pytest.mark.asyncio
async def test_execute_query_missing_query(query_tool):
    """Test that execute_query returns error when query is missing"""
    result = await query_tool.execute_query({})
    
    assert len(result) == 1
    assert "Error: Query statement is required" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_invalid_offset(query_tool):
    """Test that execute_query validates offset parameter"""
    result = await query_tool.execute_query({
        "query": "SELECT [Name] FROM [SOXIssue]",
        "offset": -1
    })
    
    assert len(result) == 1
    assert "Error: Offset must be a non-negative integer" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_invalid_limit(query_tool):
    """Test that execute_query validates limit parameter"""
    result = await query_tool.execute_query({
        "query": "SELECT [Name] FROM [SOXIssue]",
        "limit": 1000
    })
    
    assert len(result) == 1
    assert "Error: Limit must be an integer between 1 and 500" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_invalid_format(query_tool):
    """Test that execute_query validates format parameter"""
    result = await query_tool.execute_query({
        "query": "SELECT [Name] FROM [SOXIssue]",
        "format": "invalid"
    })
    
    assert len(result) == 1
    assert "Error: Format must be 'table', 'json', or 'list'" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_success_table_format(query_tool, mock_client):
    """Test successful query execution with table format"""
    # Mock the query response
    mock_client.query = AsyncMock(return_value={
        "rows": [
            {
                "fields": [
                    {"name": "Resource ID", "value": "12345"},
                    {"name": "Name", "value": "Test Issue"}
                ]
            }
        ]
    })
    
    result = await query_tool.execute_query({
        "query": "SELECT [Resource ID], [Name] FROM [SOXIssue]",
        "format": "table"
    })
    
    assert len(result) == 1
    assert "Query Results (1 row)" in result[0].text
    assert "Resource ID | Name" in result[0].text
    assert "12345 | Test Issue" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_success_json_format(query_tool, mock_client):
    """Test successful query execution with JSON format"""
    # Mock the query response
    mock_client.query = AsyncMock(return_value={
        "rows": [
            {
                "fields": [
                    {"name": "Resource ID", "value": "12345"},
                    {"name": "Name", "value": "Test Issue"}
                ]
            }
        ]
    })
    
    result = await query_tool.execute_query({
        "query": "SELECT [Resource ID], [Name] FROM [SOXIssue]",
        "format": "json"
    })
    
    assert len(result) == 1
    assert '"query"' in result[0].text
    assert '"row_count": 1' in result[0].text
    assert '"Resource ID": "12345"' in result[0].text


@pytest.mark.asyncio
async def test_execute_query_success_list_format(query_tool, mock_client):
    """Test successful query execution with list format"""
    # Mock the query response
    mock_client.query = AsyncMock(return_value={
        "rows": [
            {
                "fields": [
                    {"name": "Resource ID", "value": "12345"},
                    {"name": "Name", "value": "Test Issue"}
                ]
            }
        ]
    })
    
    result = await query_tool.execute_query({
        "query": "SELECT [Resource ID], [Name] FROM [SOXIssue]",
        "format": "list"
    })
    
    assert len(result) == 1
    assert "Query Results (1 row)" in result[0].text
    assert "## Row 1" in result[0].text
    assert "**Resource ID**: 12345" in result[0].text
    assert "**Name**: Test Issue" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_no_results(query_tool, mock_client):
    """Test query execution with no results"""
    # Mock the query response with no rows
    mock_client.query = AsyncMock(return_value={"rows": []})
    
    result = await query_tool.execute_query({
        "query": "SELECT [Name] FROM [SOXIssue] WHERE [Status] = 'NonExistent'"
    })
    
    assert len(result) == 1
    assert "No results found" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_handles_enum_values(query_tool, mock_client):
    """Test that query tool handles enum field values correctly"""
    # Mock the query response with enum value
    mock_client.query = AsyncMock(return_value={
        "rows": [
            {
                "fields": [
                    {"name": "Name", "value": "Test Issue"},
                    {"name": "Priority", "value": {"name": "High"}}
                ]
            }
        ]
    })
    
    result = await query_tool.execute_query({
        "query": "SELECT [Name], [Priority] FROM [SOXIssue]",
        "format": "table"
    })
    
    assert len(result) == 1
    assert "High" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_handles_null_values(query_tool, mock_client):
    """Test that query tool handles NULL values correctly"""
    # Mock the query response with NULL value
    mock_client.query = AsyncMock(return_value={
        "rows": [
            {
                "fields": [
                    {"name": "Name", "value": "Test Issue"},
                    {"name": "Description", "value": None}
                ]
            }
        ]
    })
    
    result = await query_tool.execute_query({
        "query": "SELECT [Name], [Description] FROM [SOXIssue]",
        "format": "table"
    })
    
    assert len(result) == 1
    assert "NULL" in result[0].text


@pytest.mark.asyncio
async def test_execute_query_error_handling(query_tool, mock_client):
    """Test that query tool handles errors gracefully"""
    # Mock the query to raise an exception
    mock_client.query = AsyncMock(side_effect=Exception("Database connection error"))
    
    result = await query_tool.execute_query({
        "query": "SELECT [Name] FROM [SOXIssue]"
    })
    
    assert len(result) == 1
    assert "Error executing query" in result[0].text
    assert "Database connection error" in result[0].text


# Made with Bob