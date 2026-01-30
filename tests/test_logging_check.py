import sys
import logging

print("=== Before any imports ===")
print(f"Root logger handlers: {logging.getLogger().handlers}")
print(f"Root logger level: {logging.getLogger().level}")

print("\n=== After importing mcp_server ===")
from src.app.mcp.mcp_server import MCPServer

handlers = logging.getLogger().handlers
print(f"Root logger handlers: {handlers}")
for h in handlers:
    stream = getattr(h, 'stream', None)
    print(f"  Handler: {h}, Stream: {stream}")
    if stream:
        print(f"    Stream is stdout: {stream == sys.stdout}")
        print(f"    Stream is stderr: {stream == sys.stderr}")

# Made with Bob
