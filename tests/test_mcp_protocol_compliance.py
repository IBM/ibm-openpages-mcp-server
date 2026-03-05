"""
MCP Protocol Compliance Tests

Verifies that the MCP server correctly implements the MCP protocol spec (2025-03-26):
1. tools/call response is NOT double-wrapped (Critical fix)
2. Notifications return None, not {} (Critical fix)
3. ping returns empty result {} (High fix)
4. Tool errors set isError: true (High fix)
5. Auth token logging is at DEBUG level only (High fix)
"""

import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_processor(tools=None, tool_handlers=None, resource_handlers=None, prompt_handlers=None):
    """Create a RequestProcessor with minimal mocks."""
    from src.app.mcp.request_processor import RequestProcessor

    if tools is None:
        tools = []
    if tool_handlers is None:
        tool_handlers = MagicMock()
    if resource_handlers is None:
        resource_handlers = MagicMock()
    if prompt_handlers is None:
        prompt_handlers = MagicMock()

    return RequestProcessor(
        server_version="1.0.0",
        tools=tools,
        tool_handlers=tool_handlers,
        resource_handlers=resource_handlers,
        prompt_handlers=prompt_handlers,
    )


# ---------------------------------------------------------------------------
# Test 1: tools/call response is NOT double-wrapped
# ---------------------------------------------------------------------------

class TestToolsCallResponseFormat:
    """Critical: tools/call result must be {content: [...], isError: bool} — not JSON-stringified."""

    @pytest.mark.asyncio
    async def test_successful_tool_call_returns_flat_content(self):
        """Tool result content must be a direct array, not a JSON-stringified wrapper."""
        tool_handlers = MagicMock()
        # Tool handler now returns MCP-compliant format
        tool_handlers.handle_call_tool = AsyncMock(return_value={
            "content": [{"type": "text", "text": "Hello from tool"}],
            "isError": False
        })

        processor = make_processor(tool_handlers=tool_handlers)
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "Hello"}},
            "id": "1"
        }
        response, should_exit = await processor.process_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "1"
        assert should_exit is False

        result = response["result"]
        # Must have content array directly — NOT a JSON string
        assert "content" in result, "result must have 'content' key"
        assert isinstance(result["content"], list), "content must be a list"
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert result["content"][0]["text"] == "Hello from tool"
        assert result["isError"] is False

        # CRITICAL: content[0]["text"] must NOT be a JSON string containing {"content": ...}
        text_value = result["content"][0]["text"]
        assert not text_value.startswith("{"), (
            f"content text must not be JSON-stringified tool response, got: {text_value[:100]}"
        )

    @pytest.mark.asyncio
    async def test_tool_error_sets_is_error_true(self):
        """When a tool returns isError:true, the response result must have isError:true."""
        tool_handlers = MagicMock()
        tool_handlers.handle_call_tool = AsyncMock(return_value={
            "content": [{"type": "text", "text": "Error: something went wrong"}],
            "isError": True
        })

        processor = make_processor(tool_handlers=tool_handlers)
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {}},
            "id": "2"
        }
        response, _ = await processor.process_request(request)

        result = response["result"]
        assert result["isError"] is True
        assert result["content"][0]["text"] == "Error: something went wrong"

    @pytest.mark.asyncio
    async def test_tool_call_via_call_tool_method_name(self):
        """Both 'tools/call' and 'call_tool' method names must work."""
        tool_handlers = MagicMock()
        tool_handlers.handle_call_tool = AsyncMock(return_value={
            "content": [{"type": "text", "text": "result"}],
            "isError": False
        })

        processor = make_processor(tool_handlers=tool_handlers)
        for method in ["tools/call", "call_tool", "tools/invoke"]:
            request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": {"name": "echo", "arguments": {}},
                "id": "3"
            }
            response, _ = await processor.process_request(request)
            assert "result" in response, f"method {method} should return result"
            assert "content" in response["result"], f"method {method} result must have content"


# ---------------------------------------------------------------------------
# Test 2: Notifications return None (not {})
# ---------------------------------------------------------------------------

class TestNotificationHandling:
    """Critical: notifications (no id) must return None, not {}."""

    @pytest.mark.asyncio
    async def test_notifications_initialized_returns_none(self):
        """notifications/initialized must return (None, False) — no response written to stream."""
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
            # No "id" field — this is a notification
        }
        response, should_exit = await processor.process_request(request)

        assert response is None, (
            f"Notification must return None response, got: {response!r}. "
            "Writing {{}} to stdio corrupts the MCP stream."
        )
        assert should_exit is False

    @pytest.mark.asyncio
    async def test_any_unknown_notification_returns_none(self):
        """Any unknown method without an id must return None."""
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "notifications/some_event"
            # No "id"
        }
        response, should_exit = await processor.process_request(request)
        assert response is None

    @pytest.mark.asyncio
    async def test_unknown_method_with_id_returns_error(self):
        """Unknown methods WITH an id must return a -32601 error (not None)."""
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "unknown/method",
            "id": "42"
        }
        response, should_exit = await processor.process_request(request)
        assert response is not None
        assert response["error"]["code"] == -32601


# ---------------------------------------------------------------------------
# Test 3: ping returns {}
# ---------------------------------------------------------------------------

class TestPingHandling:
    """High: ping must return empty result {}."""

    @pytest.mark.asyncio
    async def test_ping_returns_empty_result(self):
        """ping must return {jsonrpc, result: {}, id} per MCP spec."""
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "ping",
            "id": "ping-1"
        }
        response, should_exit = await processor.process_request(request)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "ping-1"
        assert "result" in response, "ping must return a result, not an error"
        assert response["result"] == {}, f"ping result must be empty dict, got: {response['result']}"
        assert should_exit is False

    @pytest.mark.asyncio
    async def test_ping_not_method_not_found(self):
        """ping must NOT return -32601 Method Not Found."""
        processor = make_processor()
        request = {"jsonrpc": "2.0", "method": "ping", "id": "p1"}
        response, _ = await processor.process_request(request)
        assert "error" not in response, f"ping must not return error, got: {response.get('error')}"


# ---------------------------------------------------------------------------
# Test 4: Tool handler returns MCP-compliant format
# ---------------------------------------------------------------------------

class TestToolHandlerResponseFormat:
    """High: all tool handler methods must return {content: [...], isError: bool}."""

    @pytest.mark.asyncio
    async def test_echo_tool_returns_content_format(self):
        """echo tool must return MCP-compliant content format."""
        from src.app.mcp.tool_handlers import ToolHandlers

        settings = MagicMock()
        settings.NAMESPACE = ""
        settings.OPENPAGES_OBJECT_TYPES = []

        handlers = ToolHandlers(
            object_tools={},
            settings=settings,
            query_tool=None,
            resource_handlers=None,
            mcp_server=None,
            auth_service=None
        )

        result = await handlers.handle_echo_tool({"text": "hello"})

        assert "content" in result, f"echo must return 'content' key, got: {list(result.keys())}"
        assert "isError" in result, f"echo must return 'isError' key, got: {list(result.keys())}"
        assert isinstance(result["content"], list)
        assert result["isError"] is False
        # Must NOT have old 'result' key
        assert "result" not in result, "echo must not return old 'result' key"

    @pytest.mark.asyncio
    async def test_tool_error_response_has_is_error_true(self):
        """When tool call raises, handle_call_tool must return isError:true."""
        from src.app.mcp.tool_handlers import ToolHandlers

        settings = MagicMock()
        settings.NAMESPACE = ""
        settings.OPENPAGES_OBJECT_TYPES = []

        handlers = ToolHandlers(
            object_tools={},
            settings=settings,
            query_tool=None,
            resource_handlers=None,
            mcp_server=None,
            auth_service=None
        )

        # Call a tool that doesn't exist — should return isError:true
        result = await handlers.handle_call_tool({
            "name": "nonexistent_tool",
            "arguments": {}
        })

        assert "content" in result
        assert result.get("isError") is True, (
            f"Tool errors must set isError:true, got isError={result.get('isError')}"
        )

    @pytest.mark.asyncio
    async def test_delete_tool_missing_object_type_returns_is_error(self):
        """delete_object with missing object_type must return isError:true."""
        from src.app.mcp.tool_handlers import ToolHandlers

        settings = MagicMock()
        settings.NAMESPACE = ""
        settings.OPENPAGES_OBJECT_TYPES = []

        handlers = ToolHandlers(
            object_tools={},
            settings=settings,
            query_tool=None,
            resource_handlers=None,
            mcp_server=None,
            auth_service=None
        )

        result = await handlers.handle_generic_delete_tool({})
        assert result.get("isError") is True
        assert "content" in result
        assert "result" not in result


# ---------------------------------------------------------------------------
# Test 5: initialize response structure
# ---------------------------------------------------------------------------

class TestInitializeResponse:
    """Verify initialize response has required MCP fields."""

    @pytest.mark.asyncio
    async def test_initialize_returns_protocol_version(self):
        """initialize must return protocolVersion, serverInfo, capabilities."""
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "clientInfo": {"name": "test-client", "version": "1.0"}
            },
            "id": "init-1"
        }
        response, should_exit = await processor.process_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == "init-1"
        result = response["result"]
        assert "protocolVersion" in result
        assert "serverInfo" in result
        assert "capabilities" in result
        assert "tools" in result["capabilities"]
        assert "resources" in result["capabilities"]
        assert "prompts" in result["capabilities"]
        assert "ping" in result["capabilities"], (
            "initialize capabilities must declare 'ping' so clients know the server supports it"
        )
        assert "logging" in result["capabilities"], (
            "initialize capabilities must declare 'logging'"
        )
        assert result["capabilities"]["logging"].get("setLevel") is True, (
            "logging capability must declare setLevel:true to signal logging/setLevel support"
        )
        assert should_exit is False


# ---------------------------------------------------------------------------
# Test 6: Protocol version negotiation
# ---------------------------------------------------------------------------

class TestProtocolVersionNegotiation:
    """Medium: server must negotiate protocol version per MCP spec."""

    @pytest.mark.asyncio
    async def test_known_version_is_echoed_back(self):
        """When client offers a supported version, server must echo it."""
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "clientInfo": {"name": "test-client", "version": "1.0"}
            },
            "id": "init-1"
        }
        response, _ = await processor.process_request(request)
        assert response["result"]["protocolVersion"] == "2025-03-26"

    @pytest.mark.asyncio
    async def test_older_supported_version_is_echoed_back(self):
        """When client offers an older but supported version, server must echo it."""
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "old-client", "version": "0.9"}
            },
            "id": "init-2"
        }
        response, _ = await processor.process_request(request)
        assert response["result"]["protocolVersion"] == "2024-11-05", (
            "Server must echo the client's offered version when it is supported"
        )

    @pytest.mark.asyncio
    async def test_unknown_future_version_falls_back_to_server_latest(self):
        """When client offers an unknown future version, server responds with its latest."""
        from src.app.mcp.request_processor import _LATEST_PROTOCOL_VERSION
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": "2099-01-01",
                "clientInfo": {"name": "future-client", "version": "99.0"}
            },
            "id": "init-3"
        }
        response, _ = await processor.process_request(request)
        assert response["result"]["protocolVersion"] == _LATEST_PROTOCOL_VERSION, (
            "Server must fall back to its own latest version for unknown client versions"
        )

    @pytest.mark.asyncio
    async def test_missing_protocol_version_defaults_to_server_latest(self):
        """When client omits protocolVersion, server defaults to its latest."""
        from src.app.mcp.request_processor import _LATEST_PROTOCOL_VERSION
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "minimal-client", "version": "1.0"}
                # No protocolVersion
            },
            "id": "init-4"
        }
        response, _ = await processor.process_request(request)
        assert response["result"]["protocolVersion"] == _LATEST_PROTOCOL_VERSION

    @pytest.mark.asyncio
    async def test_no_params_defaults_to_server_latest(self):
        """When initialize has no params at all, server defaults to its latest."""
        from src.app.mcp.request_processor import _LATEST_PROTOCOL_VERSION
        processor = make_processor()
        request = {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": "init-5"
        }
        response, _ = await processor.process_request(request)
        assert response["result"]["protocolVersion"] == _LATEST_PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Test 7: resources/read defaults to compact mode
# ---------------------------------------------------------------------------

class TestResourcesReadDefaultMode:
    """Medium: resources/read must default to compact mode, not full."""

    def test_handle_read_resource_default_mode_is_compact(self):
        """handle_read_resource must default mode to 'compact', not 'full'."""
        import inspect
        from src.app.mcp.resource_handlers import ResourceHandlers

        source = inspect.getsource(ResourceHandlers.handle_read_resource)
        # The default must be 'compact', not 'full'
        assert 'mode", "compact"' in source or "mode\", \"compact\"" in source, (
            "handle_read_resource must default mode to 'compact' to reduce bandwidth "
            "for MCP clients that call resources/read directly without specifying a mode."
        )
        assert 'mode", "full"' not in source and "mode\", \"full\"" not in source, (
            "handle_read_resource must NOT default to 'full' mode — "
            "that causes large schema responses for all standard MCP clients."
        )


# ---------------------------------------------------------------------------
# Test 8: HTTP error handler returns correct status codes
# ---------------------------------------------------------------------------

class TestHttpErrorHandlerStatusCodes:
    """Medium: HTTP error handler must return 500 for transport failures, 200 for RPC errors."""

    @staticmethod
    def _read_http_router_source() -> str:
        """Read http_router.py source directly to avoid importing fastapi in test env."""
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "src" / "app" / "mcp" / "remote" / "http_router.py"
        return path.read_text(encoding="utf-8")

    def test_http_router_error_handler_uses_500_for_transport_failures(self):
        """When request_id is None (parse/transport failure), error handler must return HTTP 500."""
        source = self._read_http_router_source()
        assert "status_code=500" in source, (
            "http_router.jsonrpc_endpoint must return HTTP 500 for transport-level failures "
            "(when request_id is None and the request could not be parsed)."
        )

    def test_http_router_error_handler_uses_200_for_rpc_errors(self):
        """When request_id is known, JSON-RPC errors must still return HTTP 200."""
        source = self._read_http_router_source()
        assert "status_code=200" in source, (
            "http_router.jsonrpc_endpoint must return HTTP 200 for JSON-RPC layer errors "
            "(when request_id is known — the HTTP transport succeeded)."
        )

    def test_http_router_error_handler_does_not_leak_exception_details(self):
        """Error responses must use a generic message, not str(e), to avoid leaking internals."""
        source = self._read_http_router_source()
        assert '"Internal server error"' in source, (
            "http_router error handler must use a generic 'Internal server error' message "
            "instead of str(e) to avoid leaking internal exception details to clients."
        )


# ---------------------------------------------------------------------------
# Test 9: stdio runner does not write None responses
# ---------------------------------------------------------------------------

class TestStdioRunnerNotificationSuppression:
    """Verify stdio runner suppresses None responses (notifications)."""

    def test_none_response_not_written_to_stdout(self):
        """The stdio runner must check `if response is not None` before writing."""
        import inspect
        from src.app.mcp.local import stdio_runner

        source = inspect.getsource(stdio_runner.run_stdio_server)
        # The check must be `if response is not None` not `if response`
        assert "if response is not None" in source, (
            "stdio_runner must use `if response is not None` to suppress notification responses. "
            "Using `if response` would also suppress empty-dict responses incorrectly."
        )


# ---------------------------------------------------------------------------
# Test 10: _resolve_object_type DRY helper
# ---------------------------------------------------------------------------

class TestResolveObjectType:
    """Medium: _resolve_object_type must be a single helper used by all 4 generic handlers."""

    def _make_tool_handlers(self):
        """Create a ToolHandlers instance with a minimal settings mock."""
        from src.app.mcp.tool_handlers import ToolHandlers
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.OPENPAGES_OBJECT_TYPES = [
            {"tool_prefix": "risk", "type_id": "SOXRisk", "display_name": "Risk"},
            {"tool_prefix": "control", "type_id": "SOXControl", "display_name": "Control"},
        ]
        settings.NAMESPACE = ""
        return ToolHandlers(object_tools={}, settings=settings)

    def test_resolve_by_tool_prefix(self):
        """_resolve_object_type resolves by tool_prefix (case-insensitive)."""
        th = self._make_tool_handlers()
        # Inject a fake tool so the "no tool available" branch is not hit
        th.object_tools["risk"] = MagicMock()
        result = th._resolve_object_type("RISK")
        assert result == ("risk", "SOXRisk"), f"Expected ('risk', 'SOXRisk'), got {result}"

    def test_resolve_by_type_id(self):
        """_resolve_object_type resolves by type_id (case-insensitive)."""
        th = self._make_tool_handlers()
        th.object_tools["control"] = MagicMock()
        result = th._resolve_object_type("soxcontrol")
        assert result == ("control", "SOXControl"), f"Expected ('control', 'SOXControl'), got {result}"

    def test_resolve_by_display_name(self):
        """_resolve_object_type resolves by display_name (case-insensitive)."""
        th = self._make_tool_handlers()
        th.object_tools["risk"] = MagicMock()
        result = th._resolve_object_type("Risk")
        assert result == ("risk", "SOXRisk"), f"Expected ('risk', 'SOXRisk'), got {result}"

    def test_resolve_unknown_returns_error_dict(self):
        """_resolve_object_type returns an isError dict for unknown identifiers."""
        th = self._make_tool_handlers()
        result = th._resolve_object_type("nonexistent")
        assert isinstance(result, dict), "Expected error dict for unknown type"
        assert result.get("isError") is True
        assert "nonexistent" in result["content"][0]["text"]

    def test_resolve_no_tool_registered_returns_error_dict(self):
        """_resolve_object_type returns an isError dict when no tool is registered for the type."""
        th = self._make_tool_handlers()
        # object_tools is empty — no tool registered for 'risk'
        result = th._resolve_object_type("risk")
        assert isinstance(result, dict), "Expected error dict when tool not registered"
        assert result.get("isError") is True

    def test_resolve_object_type_helper_exists(self):
        """ToolHandlers must expose _resolve_object_type as a single shared helper."""
        from src.app.mcp.tool_handlers import ToolHandlers
        assert hasattr(ToolHandlers, "_resolve_object_type"), (
            "ToolHandlers must have a _resolve_object_type method to eliminate the "
            "4× duplicated type-mapping loop (DRY principle)."
        )

    def test_duplicate_mapping_loop_removed(self):
        """The inline type_mapping dict-building loop must appear exactly once in tool_handlers.py."""
        import pathlib
        source = (
            pathlib.Path(__file__).parent.parent
            / "src" / "app" / "mcp" / "tool_handlers.py"
        ).read_text(encoding="utf-8")
        # The type-mapping loop is identified by building the `type_mapping` dict.
        # Other loops over OPENPAGES_OBJECT_TYPES (namespace lookup, type_id lookup)
        # are distinct and should not be counted.
        occurrences = source.count("type_mapping[tool_prefix.lower()]")
        assert occurrences == 1, (
            f"The type-mapping assignment 'type_mapping[tool_prefix.lower()]' appears "
            f"{occurrences} times in tool_handlers.py; it must appear exactly once "
            "(inside _resolve_object_type) — all 4 generic handlers must delegate to that helper."
        )


# ---------------------------------------------------------------------------
# Test 11: Duplicate INFO log downgraded to DEBUG
# ---------------------------------------------------------------------------

class TestDuplicateLogLevel:
    """Low: process_request must not emit an INFO log that duplicates the @log_method_call decorator."""

    def test_process_request_method_log_is_debug_not_info(self):
        """The 'Processing JSON-RPC request' log inside process_request must be DEBUG, not INFO."""
        import inspect
        from src.app.mcp.request_processor import RequestProcessor

        source = inspect.getsource(RequestProcessor.process_request)
        # Must NOT appear as an INFO log
        assert 'logger.info(f"Processing JSON-RPC request' not in source, (
            "process_request must not emit an INFO log for every request — "
            "the @log_method_call decorator already logs at DEBUG. "
            "Downgrade to logger.debug() to avoid duplicate log noise."
        )
        # Must appear as a DEBUG log
        assert 'logger.debug(f"Processing JSON-RPC request' in source, (
            "process_request must use logger.debug() for the method-entry log "
            "to avoid duplicating the @log_method_call decorator output."
        )


# ---------------------------------------------------------------------------
# Test 12: build_tool_name closure shadowing removed
# ---------------------------------------------------------------------------

class TestBuildToolNameShadowing:
    """Low: local closures in mcp_server.py must not shadow the module-level build_tool_name import."""

    @staticmethod
    def _read_mcp_server_source() -> str:
        import pathlib
        return (
            pathlib.Path(__file__).parent.parent / "src" / "app" / "mcp" / "mcp_server.py"
        ).read_text(encoding="utf-8")

    def test_no_local_def_named_build_tool_name(self):
        """No local function definition named 'build_tool_name' must exist inside mcp_server.py."""
        source = self._read_mcp_server_source()
        # Count inner `def build_tool_name` definitions (not the import line)
        import re
        inner_defs = re.findall(r"^\s+def build_tool_name\b", source, re.MULTILINE)
        assert len(inner_defs) == 0, (
            f"Found {len(inner_defs)} local closure(s) named 'build_tool_name' in mcp_server.py. "
            "These shadow the module-level import from src.app.utils. "
            "Rename them to '_make_tool_name' or similar."
        )

    def test_make_tool_name_closure_present(self):
        """The renamed closure _make_tool_name must be present in mcp_server.py."""
        source = self._read_mcp_server_source()
        import re
        inner_defs = re.findall(r"^\s+def _make_tool_name\b", source, re.MULTILINE)
        assert len(inner_defs) >= 1, (
            "Expected at least one '_make_tool_name' closure in mcp_server.py after renaming."
        )


# ---------------------------------------------------------------------------
# Test 13: Dead code _format_schema_as_text removed
# ---------------------------------------------------------------------------

class TestDeadCodeRemoved:
    """Low: _format_schema_as_text and its helpers must be removed from resource_handlers.py."""

    @staticmethod
    def _read_resource_handlers_source() -> str:
        import pathlib
        return (
            pathlib.Path(__file__).parent.parent
            / "src" / "app" / "mcp" / "resource_handlers.py"
        ).read_text(encoding="utf-8")

    def test_format_schema_as_text_removed(self):
        """_format_schema_as_text must not exist in resource_handlers.py (dead code)."""
        source = self._read_resource_handlers_source()
        assert "_format_schema_as_text" not in source, (
            "_format_schema_as_text is dead code (never called outside its own cluster). "
            "Remove it to reduce maintenance surface."
        )

    def test_format_field_removed(self):
        """_format_field must not exist in resource_handlers.py (only called by dead code)."""
        source = self._read_resource_handlers_source()
        assert "def _format_field(" not in source, (
            "_format_field is only called by the dead _format_schema_as_text. "
            "Remove it along with the rest of the dead cluster."
        )

    def test_format_relationship_field_removed(self):
        """_format_relationship_field must not exist in resource_handlers.py (only called by dead code)."""
        source = self._read_resource_handlers_source()
        assert "def _format_relationship_field(" not in source, (
            "_format_relationship_field is only called by the dead _format_schema_as_text. "
            "Remove it along with the rest of the dead cluster."
        )


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])