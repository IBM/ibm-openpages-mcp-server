import sys
import logging

print("=== Initial state ===", file=sys.stderr)
print(f"Root logger handlers: {logging.getLogger().handlers}", file=sys.stderr)

# Simulate what stdio_runner does
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

print("\n=== After basicConfig with stderr ===", file=sys.stderr)
handlers = logging.getLogger().handlers
print(f"Root logger handlers: {handlers}", file=sys.stderr)
for h in handlers:
    stream = getattr(h, 'stream', None)
    print(f"  Handler: {h}", file=sys.stderr)
    if stream:
        print(f"    Stream is stdout: {stream == sys.stdout}", file=sys.stderr)
        print(f"    Stream is stderr: {stream == sys.stderr}", file=sys.stderr)

# Now import and create server
print("\n=== Importing MCP server ===", file=sys.stderr)
from src.app.mcp.mcp_server import MCPServer
from src.app.config.settings import settings

print("\n=== Creating MCP server instance ===", file=sys.stderr)
try:
    server = MCPServer(custom_settings=settings)
    print("Server created successfully", file=sys.stderr)
except Exception as e:
    print(f"Error creating server: {e}", file=sys.stderr)

print("\n=== Final handler state ===", file=sys.stderr)
handlers = logging.getLogger().handlers
print(f"Root logger handlers: {handlers}", file=sys.stderr)
for h in handlers:
    stream = getattr(h, 'stream', None)
    print(f"  Handler: {h}", file=sys.stderr)
    if stream:
        print(f"    Stream is stdout: {stream == sys.stdout}", file=sys.stderr)
        print(f"    Stream is stderr: {stream == sys.stderr}", file=sys.stderr)

# Test logging
print("\n=== Testing log output ===", file=sys.stderr)
logger = logging.getLogger(__name__)
logger.info("This should go to stderr only")
print("This goes to stdout")

# Made with Bob
