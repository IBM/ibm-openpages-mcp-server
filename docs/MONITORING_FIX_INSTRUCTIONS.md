# Monitoring Fix Instructions

## Summary of Changes

### Issues Found
1. **Prometheus**: ✅ Already working correctly
2. **Jaeger Tracing**: ❌ FastAPI not instrumented + missing `insecure=True` parameter

### Fixes Applied
1. Added FastAPI instrumentation to automatically create spans for HTTP requests
2. Added `insecure=True` parameter to OTLP exporter for localhost connections
3. Updated main.py to call `instrument_fastapi_app(app)` during startup

## Files Modified
- `src/app/observability/tracing.py` - Added FastAPI instrumentation and insecure flag
- `main.py` - Added call to instrument FastAPI app

## Steps to Apply the Fix

### 1. Stop the Current Server
```bash
# Find the process
lsof -i :8000 | grep LISTEN

# Kill it (replace PID with actual process ID)
kill 99889
```

### 2. Restart the Server
```bash
# Start the server
python main.py
```

### 3. Verify the Fix

#### Check Startup Logs
Look for these messages in the logs:
```bash
tail -20 logs/grc-mcp.log | grep -E "(FastAPI|Tracing|Starting GRC)"
```

You should see:
- "Tracing initialized: service=grc-mcp-server"
- "FastAPI application instrumented for tracing"
- "Distributed tracing enabled"

#### Test Tracing
```bash
# Make a test request
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Wait for export (3 seconds)
sleep 3

# Check Jaeger services
curl -s http://localhost:16686/api/services | python3 -m json.tool
```

**Expected output**: You should see `"grc-mcp-server"` in the services list!

#### Check Jaeger UI
1. Open http://localhost:16686 in your browser
2. Select "grc-mcp-server" from the Service dropdown
3. Click "Find Traces"
4. You should see traces for your HTTP requests!

#### Verify Prometheus (Already Working)
```bash
# Check metrics endpoint
curl -s http://localhost:8000/metrics | head -20

# Check Prometheus targets
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep -A 10 "grc-mcp-server"

# Query a metric
curl -s 'http://localhost:9090/api/v1/query?query=grc_mcp_server_info' | python3 -m json.tool
```

## Troubleshooting

### If Jaeger Still Shows No Traces

1. **Check if spans are being created**:
   ```bash
   # Look for console span output in logs
   tail -50 logs/grc-mcp.log | grep -i "span"
   ```

2. **Verify OTLP connection**:
   ```bash
   nc -zv localhost 4317
   ```

3. **Check Jaeger logs**:
   ```bash
   docker logs grc-mcp-jaeger | tail -20
   ```

4. **Run the test script**:
   ```bash
   python test_tracing.py
   # Then check: curl -s http://localhost:16686/api/services | python3 -m json.tool
   # Should show "test-service"
   ```

### If Server Won't Start

1. **Check for port conflicts**:
   ```bash
   lsof -i :8000
   ```

2. **Check logs for errors**:
   ```bash
   tail -50 logs/grc-mcp.log
   ```

3. **Verify OpenTelemetry packages**:
   ```bash
   pip list | grep opentelemetry
   ```

## What's Working

✅ **Prometheus Metrics**
- Endpoint: http://localhost:8000/metrics
- Prometheus UI: http://localhost:9090
- Scraping every 15 seconds
- All metrics being collected

✅ **Tracing Setup**
- OpenTelemetry configured
- OTLP endpoint: http://localhost:4317
- Console tracing enabled
- FastAPI instrumentation added

✅ **Monitoring Stack**
- Jaeger UI: http://localhost:16686
- Prometheus UI: http://localhost:9090
- All services running in Docker

## Next Steps After Verification

Once you confirm traces are appearing in Jaeger:

1. **Explore Jaeger UI**:
   - View trace timelines
   - Analyze request latency
   - Identify bottlenecks

2. **Set up Grafana** (optional):
   ```bash
   docker-compose --profile full -f monitoring/docker-compose.yml up -d
   ```
   - Grafana UI: http://localhost:3000
   - Default credentials: admin/admin

3. **Create Dashboards**:
   - Import pre-built dashboards
   - Create custom visualizations
   - Set up alerts

## Clean Up Test Files

After verification, you can remove the test script:
```bash
rm test_tracing.py