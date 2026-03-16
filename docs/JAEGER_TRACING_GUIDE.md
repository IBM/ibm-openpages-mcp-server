# Jaeger Tracing Guide for GRC MCP Server

## Quick Start - How to Check Traces in Jaeger

### 1. Access Jaeger UI
Open your browser and go to: **http://localhost:16686/**

### 2. Understanding What You See

When you first open Jaeger, you'll see the **Search** page with several dropdowns and filters.

---

## Step-by-Step: Finding Your Traces

### Step 1: Select Your Service

1. In the **"Service"** dropdown (top left), select: **`grc-mcp-server`**
2. This filters to show only traces from your MCP server

### Step 2: Choose an Operation (Optional)

The **"Operation"** dropdown shows the different operations your server performs:

**Your actual operations** (what you should see):
- `POST /mcp` - Main MCP protocol endpoint
- `GET /health` - Health check endpoint
- `GET /metrics` - Metrics endpoint
- `ObservabilityMiddleware.dispatch` - Request middleware
- `process_tool_request` - Tool execution
- `query_openpages` - OpenPages API calls
- Various tool names like `query_recent_risks`, `create_risk`, etc.

**Note**: If you see operations like `/api/services` or `/api/traces`, those are Jaeger's own internal operations, not your server's traces!

### Step 3: Set Time Range

- Use the **"Lookback"** dropdown to select a time range
- Options: Last hour, Last 2 hours, Last 24 hours, Custom
- Start with "Last 1 hour" to see recent activity

### Step 4: Click "Find Traces"

This will search for all traces matching your criteria.

---

## Understanding the Results

### Trace List View

After clicking "Find Traces", you'll see a list of traces with:

```
┌─────────────────────────────────────────────────────────────┐
│ grc-mcp-server: POST /mcp                    Duration: 234ms │
│ ├─ 5 Spans                                   Time: 12:30:45  │
│ └─ Trace ID: abc123...                                       │
└─────────────────────────────────────────────────────────────┘
```

**Key Information:**
- **Service Name**: `grc-mcp-server`
- **Operation**: What the request was doing (e.g., `POST /mcp`)
- **Duration**: Total time the request took
- **Spans**: Number of operations within this trace
- **Timestamp**: When the request occurred
- **Trace ID**: Unique identifier for this request

### Sorting and Filtering

**Sort by:**
- **Most Recent** - Latest traces first (default)
- **Longest First** - Slowest requests first (useful for finding bottlenecks!)
- **Shortest First** - Fastest requests first
- **Most Spans** - Most complex requests first

**Filter by:**
- **Min Duration**: Only show traces slower than X ms
- **Max Duration**: Only show traces faster than X ms
- **Tags**: Filter by specific attributes (see below)


### Understanding Span Counts

**Why "5 Spans" but only 4 child entries?**

When you see a trace with "5 Spans" and expand it to see 4 child entries, here's what's happening:

```
POST /mcp (Root Span - #1)
├─ POST /mcp http receive (#2)
├─ POST /mcp http send (#3)
├─ POST /mcp http send (#4)
└─ POST /mcp http send (#5)
```

**The count includes:**
1. **The root span itself** (POST /mcp) - This is span #1
2. **All child spans** (the 4 entries you see) - These are spans #2-5

**Total: 5 spans**

### What Are These HTTP Spans?

The `http receive` and `http send` spans are created by **FastAPI's automatic instrumentation**:

#### `POST /mcp http receive`
- **What**: Receiving the HTTP request from the client
- **When**: Start of request processing
- **Duration**: Time to read request headers and body
- **Purpose**: Tracks network I/O for incoming data

#### `POST /mcp http send` (multiple entries)
- **What**: Sending HTTP response chunks back to the client
- **When**: During and after request processing
- **Duration**: Time to write response data
- **Purpose**: Tracks network I/O for outgoing data
- **Why Multiple**: 
  - First send: Response headers
  - Second send: Response body (may be chunked)
  - Third send: Final response completion

### Why This Matters

These HTTP-level spans help you understand:

1. **Network Performance**: How much time is spent on I/O vs processing
2. **Streaming Behavior**: If responses are sent in chunks
3. **Complete Picture**: Full request lifecycle from receive to send

### Example Breakdown

```
Trace: POST /mcp (Total: 234ms, 5 spans)
│
├─ POST /mcp (Root)                    [234ms] ████████████████████
│  │
│  ├─ http receive                     [2ms]   █
│  │  └─ Reading request body
│  │
│  ├─ [Your application logic here]    [220ms] ██████████████████
│  │  └─ Tool execution, DB calls, etc.
│  │
│  ├─ http send (headers)              [5ms]   ██
│  │  └─ Sending response headers
│  │
│  ├─ http send (body)                 [5ms]   ██
│  │  └─ Sending response body
│  │
│  └─ http send (complete)             [2ms]   █
│     └─ Finalizing response
```

### What You Should Focus On

When analyzing traces:

✅ **Focus on:**
- Application logic spans (your actual code)
- Database/API call spans
- Tool execution spans
- Spans with long durations

⚠️ **Less important:**
- HTTP receive/send spans (usually very fast)
- These are infrastructure overhead
- Only investigate if they're unusually slow (>50ms)

### Finding Your Application Spans

To see your actual application logic, look for spans like:
- `ObservabilityMiddleware.dispatch`
- `process_tool_request`
- `openpages_upsert_control` (your tool name)
- `query_openpages`
- Database operations
- External API calls

These will be nested inside the HTTP spans and show your actual business logic execution.

---

## Analyzing a Single Trace

### Click on Any Trace

This opens the **Trace Detail View** showing the complete request flow.

### What You'll See

```
Trace Timeline (Waterfall View)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

POST /mcp                                          [234ms] ████████████████████
├─ ObservabilityMiddleware.dispatch               [230ms] ███████████████████
│  ├─ handle_request                              [220ms] ██████████████████
│  │  ├─ process_tool_request                     [210ms] █████████████████
│  │  │  ├─ query_recent_risks                    [200ms] ████████████████
│  │  │  │  └─ query_openpages                    [190ms] ███████████████
│  │  │  │     └─ HTTP GET /grc/api/risks         [180ms] ██████████████
```

### Understanding the Waterfall

**Each row shows:**
- **Span Name**: What operation was performed
- **Duration**: How long it took (in milliseconds)
- **Bar Length**: Visual representation of time
- **Indentation**: Parent-child relationships

**Colors:**
- **Blue**: Normal operation
- **Red**: Error occurred
- **Yellow**: Warning or slow operation

### Span Details

Click on any span to see:

#### 1. **Tags** (Attributes)
```
http.method: POST
http.url: /mcp
http.status_code: 200
tool.name: query_recent_risks
user.id: user-123
request.id: 550e8400-e29b-41d4-a716-446655440000
duration_ms: 234.56
```

#### 2. **Process** (Service Info)
```
service.name: grc-mcp-server
service.version: 1.0.0
```

#### 3. **Logs** (Events)

---

## Why You Might Only See HTTP Spans

### The Problem

If you're only seeing these spans:
- `POST /mcp http receive`
- `POST /mcp http send` (multiple)

But **NOT** seeing application logic spans like:
- `process_tool_request`
- `openpages_upsert_control`
- `query_openpages`

**This means application-level tracing is not instrumented in the code.**

### The Root Cause

Your code currently has:
- ✅ **FastAPI automatic instrumentation** - Creates HTTP-level spans
- ✅ **Logging decorators** (`@log_method_call`) - Creates log entries
- ❌ **Tracing decorators** (`@trace_operation`) - **MISSING!**

### What's Happening

```python
# Current code (in tool_handlers.py, request_processor.py, etc.)
@log_method_call(log_args=True, level=logging.DEBUG)  # ✅ Logging only
async def handle_call_tool(self, params):
    # Your application logic
    pass
```

**Result**: You get logs, but no trace spans for this function.

### What Should Be There

```python
# What the code should have
from src.app.observability.tracing import trace_operation

@trace_operation("process_tool_request")  # ✅ Tracing decorator
@log_method_call(log_args=True, level=logging.DEBUG)  # ✅ Logging decorator
async def handle_call_tool(self, params):
    # Your application logic
    pass
```

**Result**: You get both logs AND trace spans showing the execution flow.

### How to Fix This

You need to add `@trace_operation` decorators to key methods in:

1. **`src/app/mcp/tool_handlers.py`**:
   ```python
   from src.app.observability.tracing import trace_operation
   
   @trace_operation("handle_call_tool")
   @log_method_call(log_args=True, level=logging.DEBUG)
   async def handle_call_tool(self, params):
       # ...
   ```

2. **`src/app/mcp/request_processor.py`**:
   ```python
   @trace_operation("process_request")
   @log_method_call(log_args=True, level=logging.DEBUG)
   async def process_request(self, request_data):
       # ...
   ```

3. **`src/app/tools/generic_object_tools.py`**:
   ```python
   @trace_operation("upsert_object")
   async def upsert(self, ...):
       # ...
   ```

4. **`src/app/core/openpages_client.py`**:
   ```python
   @trace_operation("openpages_api_call")
   async def make_request(self, ...):
       # ...
   ```

### Current State vs Desired State

**Current (What you see now):**
```
POST /mcp (234ms)
├─ http receive (2ms)
├─ http send (5ms)
├─ http send (5ms)
└─ http send (2ms)
```

**Desired (What you should see):**
```
POST /mcp (234ms)
├─ http receive (2ms)
├─ ObservabilityMiddleware.dispatch (220ms)
│  ├─ process_request (215ms)
│  │  ├─ handle_call_tool (210ms)
│  │  │  ├─ openpages_upsert_control (200ms)
│  │  │  │  ├─ upsert (195ms)
│  │  │  │  │  └─ openpages_api_call (190ms)
│  │  │  │  │     └─ HTTP POST /grc/api/controls (185ms)
├─ http send (5ms)
├─ http send (5ms)
└─ http send (2ms)
```

### Temporary Workaround

Until the code is updated with tracing decorators, you can:

1. **Check logs** for detailed execution information
2. **Use metrics** to see aggregate performance data
3. **Monitor HTTP span durations** - If they're slow, your application logic is slow

### Verifying the Fix

After adding `@trace_operation` decorators:

1. Restart your server
2. Make a tool call (like `openpages_upsert_control`)
3. Refresh Jaeger UI

---

## What Should Be Traced? (Best Practices)

### Why Trace Low-Level Details?

**Current situation**: You only see generic HTTP operations
```
POST /mcp - 234ms
```

**Problem**: You can't answer:
- Which tool was called? (`query_tool` vs `upsert_tool`)
- What object type? (`risk` vs `control`)
- Which OpenPages API endpoint was hit?
- Where did the time go?

### The Value of Detailed Tracing

**With proper tracing**, you can answer:
- ✅ "Which tool is slowest?" → Sort by tool name
- ✅ "Is `upsert_control` slower than `upsert_risk`?" → Compare spans
- ✅ "Where is the bottleneck?" → See nested spans
- ✅ "Did the OpenPages API fail?" → Check span errors
- ✅ "How long did the database query take?" → See query span

### What to Trace: The Golden Rule

**Trace any operation that:**
1. **Takes time** (>10ms typically)
2. **Can fail** (external calls, database, API)
3. **Is important for debugging** (business logic)
4. **You want to monitor** (performance tracking)

### Recommended Tracing Strategy

#### Level 1: Request Entry Points (CRITICAL)
```python
@trace_operation("handle_mcp_request")
async def handle_request(request):
    # Entry point for all MCP requests
    pass
```

**Why**: Shows overall request flow and duration

#### Level 2: Tool Execution (CRITICAL)
```python
@trace_operation("execute_tool")
async def handle_call_tool(params):
    tool_name = params.get("name")
    add_span_attribute("tool.name", tool_name)  # ← Add tool name!
    # Execute tool
    pass
```

**Why**: Shows which tool was called and how long it took

#### Level 3: Specific Tool Operations (IMPORTANT)
```python
@trace_operation("openpages_upsert_control")
async def upsert_control(name, description):
    add_span_attribute("object.type", "control")
    add_span_attribute("object.name", name)
    add_span_attribute("operation", "upsert")
    # Upsert logic
    pass
```

**Why**: Shows specific business operations with context

#### Level 4: External API Calls (CRITICAL)
```python
@trace_operation("openpages_api_call")
async def make_request(method, endpoint, data):
    add_span_attribute("http.method", method)
    add_span_attribute("http.url", endpoint)
    add_span_attribute("api.service", "openpages")
    # Make API call
    pass
```

**Why**: Shows external dependencies and their performance

#### Level 5: Database Operations (IMPORTANT)
```python
@trace_operation("database_query")
async def execute_query(query):
    add_span_attribute("db.statement", query[:100])  # Truncate for safety
    add_span_attribute("db.system", "openpages")
    # Execute query
    pass
```

**Why**: Shows database performance bottlenecks

### Example: Fully Instrumented Request

```python
# 1. Entry point
@trace_operation("handle_mcp_request")
async def handle_request(request):
    add_span_attribute("request.method", request.method)
    
    # 2. Tool execution
    @trace_operation("execute_tool")
    async def handle_call_tool(params):
        tool_name = params["name"]
        add_span_attribute("tool.name", tool_name)
        
        # 3. Specific operation
        @trace_operation(f"tool.{tool_name}")
        async def execute_specific_tool():
            add_span_attribute("object.type", "control")
            add_span_attribute("operation", "upsert")
            
            # 4. API call
            @trace_operation("openpages_api_call")
            async def call_api():
                add_span_attribute("http.method", "POST")
                add_span_attribute("http.url", "/grc/api/controls")
                # Make request
                pass
```

**Result in Jaeger:**
```
POST /mcp (234ms)
├─ handle_mcp_request (230ms)
│  └─ execute_tool (225ms)
│     └─ tool.openpages_upsert_control (220ms)
│        └─ openpages_api_call (200ms)
│           [Attributes]
│           - tool.name: openpages_upsert_control
│           - object.type: control
│           - operation: upsert
│           - http.method: POST
│           - http.url: /grc/api/controls
```

### What NOT to Trace

❌ **Don't trace:**
- Very fast operations (<1ms)
- Pure data transformations (unless complex)
- Simple getters/setters
- Logging operations
- Validation logic (unless slow)

**Why**: Creates noise and overhead without value

### Span Attributes: The Secret Sauce

**Attributes make traces searchable and meaningful!**

#### Essential Attributes to Add

```python
# Tool information
add_span_attribute("tool.name", "openpages_upsert_control")
add_span_attribute("tool.operation", "upsert")

# Object information
add_span_attribute("object.type", "control")
add_span_attribute("object.id", "CTRL-123")
add_span_attribute("object.name", "Access Control")

# User information
add_span_attribute("user.id", "user-456")
add_span_attribute("user.action", "create")

# API information
add_span_attribute("api.endpoint", "/grc/api/controls")
add_span_attribute("api.method", "POST")
add_span_attribute("api.status_code", 200)

# Performance information
add_span_attribute("db.query_count", 3)
add_span_attribute("cache.hit", True)

# Business context
add_span_attribute("tenant.id", "tenant-789")
add_span_attribute("environment", "production")
```

#### Using Attributes for Filtering

In Jaeger, you can then search:
```
tool.name=openpages_upsert_control
object.type=control
api.status_code=500
user.id=user-456
```

### Practical Example: Before vs After

#### Before (Current State)
```
POST /mcp (234ms)
├─ http receive (2ms)
└─ http send (5ms)
```

**Questions you CAN'T answer:**
- Which tool was called?
- What object type?
- Where did 227ms go?
- Did it succeed?

#### After (With Proper Tracing)
```
POST /mcp (234ms)
├─ http receive (2ms)
├─ handle_mcp_request (220ms)
│  ├─ execute_tool (215ms) [tool.name=openpages_upsert_control]
│  │  ├─ validate_input (5ms)
│  │  ├─ upsert_control (205ms) [object.type=control, operation=upsert]
│  │  │  ├─ check_existing (10ms) [db.query=SELECT...]
│  │  │  ├─ prepare_payload (5ms)
│  │  │  └─ openpages_api_call (190ms) [http.method=POST, http.url=/grc/api/controls]
│  │  │     └─ HTTP POST (185ms) [http.status_code=200]
│  │  └─ format_response (5ms)
└─ http send (5ms)
```

**Questions you CAN answer:**
- ✅ Tool: `openpages_upsert_control`
- ✅ Object: `control`
- ✅ Operation: `upsert`
- ✅ Bottleneck: OpenPages API (190ms)
- ✅ Status: Success (200)

### Implementation Priority

**Phase 1: Critical (Do First)**
1. Request entry points
2. Tool execution with tool name
3. External API calls with endpoints
4. Error tracking

**Phase 2: Important (Do Next)**
1. Specific tool operations
2. Database queries
3. Authentication/authorization
4. Business logic operations

**Phase 3: Nice to Have (Do Later)**
1. Cache operations
2. Data transformations
3. Validation logic
4. Helper functions

### Code Example: Minimal Instrumentation

```python
from src.app.observability.tracing import trace_operation, add_span_attribute

# In tool_handlers.py
@trace_operation("handle_call_tool")
async def handle_call_tool(self, params):
    tool_name = params.get("name", "unknown")
    add_span_attribute("tool.name", tool_name)
    
    # Execute tool
    result = await self._execute_tool(tool_name, params)
    
    add_span_attribute("tool.status", "success")
    return result

# In generic_object_tools.py
@trace_operation("upsert_object")
async def upsert(self, operation, **kwargs):
    add_span_attribute("object.type", self.object_type)
    add_span_attribute("operation", operation)
    
    # Upsert logic
    result = await self.client.make_request(...)
    
    add_span_attribute("object.id", result.get("id"))
    return result

# In openpages_client.py
@trace_operation("openpages_api_call")
async def make_request(self, method, endpoint, data=None):
    add_span_attribute("http.method", method)
    add_span_attribute("http.url", endpoint)
    
    try:
        response = await self._http_client.request(method, endpoint, json=data)
        add_span_attribute("http.status_code", response.status_code)
        return response
    except Exception as e:
        add_span_attribute("error", True)
        add_span_attribute("error.type", type(e).__name__)
        raise
```

### Benefits of Detailed Tracing

1. **Performance Optimization**
   - Identify slow operations
   - Compare tool performance
   - Find bottlenecks

2. **Debugging**
   - See exact execution flow
   - Identify where errors occur
   - Understand timing issues

3. **Monitoring**
   - Track tool usage patterns
   - Monitor API performance
   - Alert on slow operations

4. **Business Insights**
   - Which tools are used most?
   - Which object types are slowest?
   - User behavior patterns

### Summary

**YES, you should trace low-level details!**

The whole point of distributed tracing is to see:
- **What** happened (tool names, operations)
- **Where** it happened (which service, which function)
- **How long** it took (performance)
- **Why** it failed (errors, context)

Without these details, tracing is just expensive logging.

4. You should now see nested spans showing your application logic

```
[12:30:45.123] Request started
[12:30:45.234] Tool execution began
[12:30:45.456] OpenPages API called
[12:30:45.678] Response received
```

#### 4. **Errors** (If Any)
```
exception.type: ValueError
exception.message: Invalid risk ID
exception.stacktrace: ...
```

---

## Common Use Cases

### 1. Finding Slow Requests

**Goal**: Identify performance bottlenecks

**Steps:**
1. Select service: `grc-mcp-server`
2. Sort by: **"Longest First"**
3. Click on the slowest trace
4. Look for the longest span in the waterfall
5. That's your bottleneck!

**Example:**
```
Total: 5000ms
├─ Middleware: 10ms
├─ Process Request: 20ms
└─ Query OpenPages: 4970ms  ← BOTTLENECK!
```

### 2. Finding Errors

**Goal**: Debug failed requests

**Steps:**
1. Select service: `grc-mcp-server`
2. In "Tags" field, enter: `error=true`
3. Click "Find Traces"
4. Click on any red trace
5. Look for red spans (errors)
6. Click on red span to see error details

**What to look for:**
- `exception.type`: Type of error
- `exception.message`: Error message
- `exception.stacktrace`: Where it failed

### 3. Tracking a Specific Request

**Goal**: Follow a single request through the system

**Steps:**
1. Get the `request_id` from your logs
2. In Jaeger, enter in "Tags": `request.id=550e8400-...`
3. Click "Find Traces"
4. You'll see the exact trace for that request

### 4. Analyzing Tool Performance

**Goal**: See how long specific tools take

**Steps:**
1. Select service: `grc-mcp-server`
2. Select operation: `process_tool_request`
3. In "Tags", enter: `tool.name=query_recent_risks`
4. Click "Find Traces"
5. Compare durations across multiple executions

### 5. Monitoring API Calls

**Goal**: Track OpenPages API performance

**Steps:**
1. Select service: `grc-mcp-server`
2. Select operation: `query_openpages`
3. Look at duration distribution
4. Check for errors or timeouts

---

## Advanced Features

### 1. Compare Traces

- Select multiple traces using checkboxes
- Click "Compare" button
- See side-by-side comparison of request flows

### 2. Trace Graph

- Click "Trace Graph" tab
- See visual representation of service dependencies
- Useful for understanding system architecture

### 3. Deep Linking

- Copy trace URL from browser
- Share with team members
- Direct link to specific trace

### 4. JSON View

- Click "JSON" button in trace detail
- See raw trace data
- Useful for debugging or exporting

---

## Useful Tag Filters

Use these in the "Tags" field to filter traces:

```
# Filter by HTTP status
http.status_code=500

# Filter by user
user.id=user-123

# Filter by tool
tool.name=query_recent_risks

# Filter by errors
error=true

# Filter by request ID
request.id=550e8400-e29b-41d4-a716-446655440000

# Filter by duration (in Tags section)
# Note: Use Min/Max Duration fields instead

# Combine multiple tags
error=true tool.name=create_risk
```

---

## Troubleshooting

### "No traces found"

**Possible reasons:**
1. **No traffic**: Make some requests to your server first
2. **Wrong time range**: Expand the lookback period
3. **Wrong service**: Make sure you selected `grc-mcp-server`
4. **Tracing disabled**: Check your `.env` file:
   ```bash
   TRACING_ENABLED=true
   OTLP_ENDPOINT=http://localhost:4317
   ```

### "Only seeing Jaeger's own traces"

If you see operations like `/api/services`, `/api/traces`:
- These are Jaeger's internal operations
- Select `grc-mcp-server` from the service dropdown
- Your application traces will appear separately

### "Traces are incomplete"

**Possible reasons:**
1. **Spans not finishing**: Check for exceptions in your code
2. **Context not propagated**: Ensure middleware is properly configured
3. **Sampling**: Check if sampling is enabled (default is 100%)

### "Can't see span details"

- Make sure you're clicking on the span itself, not just the row
- The details panel should appear on the right side
- Try refreshing the page

---

## Generating Test Traffic

To see traces in Jaeger, you need to generate some traffic:

### Option 1: Use MCP Inspector

```bash
# Start MCP Inspector
npx @modelcontextprotocol/inspector python main.py

# Make requests through the inspector UI
```

### Option 2: Direct API Calls

```bash
# Health check (simple trace)
curl http://localhost:8000/health

# MCP request (complex trace)
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'
```

### Option 3: Run Tests

```bash
# Run test suite (generates many traces)
pytest tests/test_tracing.py -v
```

---

## Best Practices

### 1. Start Simple
- Begin with "Last 1 hour" and no filters
- Get familiar with the basic interface
- Then add filters as needed

### 2. Use Sorting
- **Longest First**: Find performance issues
- **Most Recent**: Debug current problems
- **Most Spans**: Find complex requests

### 3. Look for Patterns
- Are certain operations always slow?
- Do errors cluster at specific times?
- Which tools are used most frequently?

### 4. Correlate with Logs
- Use `request_id` to link traces and logs
- Traces show "where", logs show "why"
- Check logs for detailed error messages

### 5. Monitor Trends
- Check Jaeger regularly (daily/weekly)
- Look for degrading performance
- Identify new bottlenecks early

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    JAEGER QUICK REFERENCE                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  URL: http://localhost:16686/                               │
│                                                              │
│  SERVICE: grc-mcp-server                                    │
│                                                              │
│  COMMON OPERATIONS:                                         │
│  • POST /mcp              - Main MCP endpoint               │
│  • process_tool_request   - Tool execution                  │
│  • query_openpages        - API calls                       │
│                                                              │
│  USEFUL FILTERS:                                            │
│  • error=true             - Show only errors                │
│  • tool.name=X            - Filter by tool                  │
│  • user.id=X              - Filter by user                  │
│                                                              │
│  SORTING:                                                   │
│  • Longest First          - Find slow requests              │
│  • Most Recent            - Latest activity                 │
│                                                              │
│  SPAN COLORS:                                               │
│  • Blue                   - Normal                          │
│  • Red                    - Error                           │
│  • Yellow                 - Warning                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Generate Traffic**: Make some requests to your server
2. **Find Traces**: Select `grc-mcp-server` and click "Find Traces"
3. **Explore**: Click on a trace to see the waterfall view
4. **Analyze**: Look for slow spans or errors
5. **Optimize**: Use insights to improve performance

---

## Related Documentation

- [`OBSERVABILITY_TESTING_GUIDE.md`](./OBSERVABILITY_TESTING_GUIDE.md) - Complete testing guide
- [`OBSERVABILITY_EXPLAINED.md`](./OBSERVABILITY_EXPLAINED.md) - Logging vs Tracing vs Metrics
- [`OBSERVABILITY_ARCHITECTURE.md`](./OBSERVABILITY_ARCHITECTURE.md) - System architecture

---

**Last Updated**: 2026-02-24  
**Version**: 1.0.0