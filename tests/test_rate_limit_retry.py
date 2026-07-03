"""
Test rate limit (429) retry logic in OpenPages client
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from src.app.core.openpages_client import OpenPagesClient, MAX_RATE_LIMIT_RETRIES, INITIAL_BACKOFF_SECONDS


@pytest.mark.asyncio
async def test_429_retry_success_on_second_attempt():
    """Test that 429 error is retried and succeeds on second attempt"""
    
    # Create mock client
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    # Mock the HTTP client
    mock_http_client = AsyncMock()
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "1"}
    mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=mock_response_429
    )
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"id": "test-type"}
    mock_response_success.content = b'{"id": "test-type"}'
    mock_response_success.text = '{"id": "test-type"}'
    
    # First call returns 429, second call succeeds
    mock_http_client.request.side_effect = [
        mock_response_429,  # First attempt fails with 429
        mock_response_success  # Retry succeeds
    ]
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            # Call get_type_definition which uses _request_with_auth_retry
            result = await client.get_type_definition("TestType")
            
            # Verify the result
            assert result == {"id": "test-type"}
            
            # Verify request was called twice (initial + 1 retry)
            assert mock_http_client.request.call_count == 2


@pytest.mark.asyncio
async def test_429_retry_exhausted():
    """Test that 429 error is retried MAX_RATE_LIMIT_RETRIES times before failing"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    # Mock the HTTP client to always return 429
    mock_http_client = AsyncMock()
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "0.1"}  # Short retry for testing
    mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=mock_response_429
    )
    
    # Always return 429
    mock_http_client.request.return_value = mock_response_429
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            # Should raise HTTPStatusError after exhausting retries
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.get_type_definition("TestType")
            
            assert exc_info.value.response.status_code == 429
            
            # Verify request was called initial + MAX_RATE_LIMIT_RETRIES times
            assert mock_http_client.request.call_count == 1 + MAX_RATE_LIMIT_RETRIES


@pytest.mark.asyncio
async def test_429_exponential_backoff():
    """Test that exponential backoff is applied correctly"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    # Track sleep calls to verify exponential backoff
    sleep_times = []
    
    async def mock_sleep(seconds):
        sleep_times.append(seconds)
    
    mock_http_client = AsyncMock()
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {}  # No Retry-After header
    mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=mock_response_429
    )
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"id": "test-type"}
    mock_response_success.content = b'{"id": "test-type"}'
    mock_response_success.text = '{"id": "test-type"}'
    
    # Fail twice with 429, then succeed
    mock_http_client.request.side_effect = [
        mock_response_429,
        mock_response_429,
        mock_response_success
    ]
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            with patch('asyncio.sleep', side_effect=mock_sleep):
                result = await client.get_type_definition("TestType")
                
                # Verify result
                assert result == {"id": "test-type"}
                
                # Verify exponential backoff: 1s, 2s
                assert len(sleep_times) == 2
                assert sleep_times[0] == INITIAL_BACKOFF_SECONDS  # 1.0s
                assert sleep_times[1] == INITIAL_BACKOFF_SECONDS * 2  # 2.0s


@pytest.mark.asyncio
async def test_429_respects_retry_after_header():
    """Test that Retry-After header is respected"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    sleep_times = []
    
    async def mock_sleep(seconds):
        sleep_times.append(seconds)
    
    mock_http_client = AsyncMock()
    mock_response_429 = MagicMock()
    mock_response_429.status_code = 429
    mock_response_429.headers = {"Retry-After": "3"}  # Server says wait 3 seconds
    mock_response_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=mock_response_429
    )
    
    mock_response_success = MagicMock()
    mock_response_success.status_code = 200
    mock_response_success.json.return_value = {"id": "test-type"}
    mock_response_success.content = b'{"id": "test-type"}'
    mock_response_success.text = '{"id": "test-type"}'
    
    mock_http_client.request.side_effect = [
        mock_response_429,
        mock_response_success
    ]
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            with patch('asyncio.sleep', side_effect=mock_sleep):
                result = await client.get_type_definition("TestType")
                
                # Verify result
                assert result == {"id": "test-type"}
                
                # Verify it used the Retry-After value (3 seconds)
                assert len(sleep_times) == 1
                assert sleep_times[0] == 3.0


@pytest.mark.asyncio
async def test_other_http_errors_not_retried():
    """Test that non-429 HTTP errors are not retried"""
    
    client = OpenPagesClient(
        base_url="https://test.example.com",
        username="test_user",
        password="test_pass",
        auth_type="basic"
    )
    
    mock_http_client = AsyncMock()
    mock_response_500 = MagicMock()
    mock_response_500.status_code = 500
    mock_response_500.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Internal Server Error",
        request=MagicMock(),
        response=mock_response_500
    )
    
    mock_http_client.request.return_value = mock_response_500
    
    with patch.object(client, '_get_http_client', return_value=mock_http_client):
        with patch.object(client, '_get_request_headers', return_value={"Authorization": "Basic test"}):
            # Should raise immediately without retries
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await client.get_type_definition("TestType")
            
            assert exc_info.value.response.status_code == 500
            
            # Verify request was only called once (no retries)
            assert mock_http_client.request.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
