#!/usr/bin/env python3
"""
Simple HTTP proxy/logger that captures exactly what IBM Bob IDE sends to the MCP server.
Uses only stdlib. Run this on port 8001, then temporarily change mcp_settings.json to
point to http://localhost:8001/mcp
"""
import json
import http.server
import http.client
import threading
import urllib.parse

request_count = 0

class LoggingProxy(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def do_DELETE(self):
        self._handle_request("DELETE")

    def do_OPTIONS(self):
        self._handle_request("OPTIONS")

    def _handle_request(self, method):
        global request_count
        request_count += 1

        # Read body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        print(f"\n{'='*80}")
        print(f"REQUEST #{request_count}: {method} {self.path}")
        print(f"Headers:")
        for k, v in self.headers.items():
            print(f"  {k}: {v}")

        if body:
            try:
                parsed = json.loads(body)
                print(f"Body (JSON):\n{json.dumps(parsed, indent=2)}")
            except Exception:
                print(f"Body (raw): {body[:500]}")
        else:
            print("Body: (empty)")

        # Forward to real server at port 8000
        try:
            conn = http.client.HTTPConnection("localhost", 8000, timeout=30)
            
            # Forward headers (excluding host)
            forward_headers = {}
            for k, v in self.headers.items():
                if k.lower() not in ('host', 'content-length'):
                    forward_headers[k] = v
            if body:
                forward_headers['Content-Length'] = str(len(body))

            conn.request(method, self.path, body=body, headers=forward_headers)
            resp = conn.getresponse()
            resp_body = resp.read()

            print(f"\nRESPONSE: {resp.status} {resp.reason}")
            print(f"Response Headers:")
            for k, v in resp.getheaders():
                print(f"  {k}: {v}")

            if resp_body:
                try:
                    parsed_resp = json.loads(resp_body)
                    print(f"Response Body (JSON):\n{json.dumps(parsed_resp, indent=2)[:3000]}")
                except Exception:
                    print(f"Response Body (raw): {resp_body[:500]}")

            # Send response back to client
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in ('transfer-encoding',):
                    self.send_header(k, v)
            self.end_headers()
            if resp_body:
                self.wfile.write(resp_body)

        except Exception as e:
            print(f"ERROR forwarding to real server: {e}")
            self.send_response(502)
            self.end_headers()
            self.wfile.write(str(e).encode())

if __name__ == '__main__':
    server = http.server.HTTPServer(('127.0.0.1', 8001), LoggingProxy)
    print("="*80)
    print("Proxy started on http://localhost:8001 -> forwarding to http://localhost:8000")
    print("Change mcp_settings.json openpages-remote url to: http://localhost:8001/mcp")
    print("Then reload IBM Bob IDE window to trigger reconnection")
    print("="*80)
    server.serve_forever()