# OpenPages Query Agent Sample

This directory contains a **sample** Langflow agent component for querying OpenPages data through the MCP server.

> **⚠️ Important**: This is a sample implementation provided for demonstration and learning purposes only. It illustrates key concepts like schema caching and conversation-aware behavior.

## Files

### OpenPagesQueryAgent.py
A sample OpenPages Query Agent demonstrating:
- **Active schema caching** - Caches schemas at both session and class levels
- **Custom tools** - `read_openpages_schema` and `validate_openpages_query` tools
- **Conversation-aware** - Reuses schema information from chat history
- **Configurable** - Enable/disable caching, adjustable TTL
- **Langflow integration** - Standard agent features included

**Note**: This is a sample implementation for reference and learning purposes.

### SCHEMA_CACHING_IMPLEMENTATION.md
Complete documentation of the schema caching implementation:
- How caching works
- Performance benefits
- Configuration options
- Implementation details
- Troubleshooting guide

## Key Features

### Schema Caching
The agent implements two-level caching:

1. **Session Cache**: Instance-specific, fastest access
2. **Class Cache**: Shared across instances, TTL-based expiration

**Performance Impact:**
- Cache Hit: ~1-5ms (20-200x faster)
- Cache Miss: ~100-200ms (first fetch only)

### Conversation-Aware
The agent is instructed to:
- Check conversation history for previously fetched schemas
- Only fetch schemas for new object types
- Reuse information from earlier in the conversation

This reduces unnecessary tool calls even when cache is available.

## Usage in Langflow

> **Note**: This is a sample implementation for demonstration and learning purposes.

1. Copy `OpenPagesQueryAgent.py` into your Langflow custom components directory
2. Review the code and customize as needed for your environment
3. Restart Langflow or reload components
4. Add the agent to your flow
5. Configure the settings:
   - Connect a language model
   - Set schema cache TTL (default: 3600 seconds)
   - Enable/disable caching as needed

## Integration with MCP Server

The agent works with the OpenPages MCP server to:
- Fetch object type schemas via `openpages://schema/{type_id}` resources
- Execute queries via the `openpages_query` tool
- Access the query grammar resource for syntax guidance

## Configuration

### Enable/Disable Caching
```python
enable_schema_caching = True  # Default
```

### Adjust Cache TTL
```python
schema_cache_ttl = 3600  # 1 hour (default)
schema_cache_ttl = 7200  # 2 hours
schema_cache_ttl = 0     # Disable caching
```

## Example Queries

The agent can handle queries like:
- "Show me all active controls"
- "List risks with their associated controls"
- "Find issues created in the last 30 days"
- "Show me business entities and their child risks"

## Troubleshooting

### Agent keeps fetching same schema
- Check that conversation history is being maintained
- Verify the system prompt includes conversation-aware instructions
- Review agent logs for cache hit/miss information

### Coroutine serialization errors
- Ensure tool functions are synchronous (`def` not `async def`)
- Check that no async operations are being returned unwrapped

### Cache not working
- Verify `enable_schema_caching` is True
- Check `schema_cache_ttl` is greater than 0
- Look for cache hit/miss logs in debug output

## Related Documentation

- [MCP Server Prompt](../src/docs/MCP_SERVER_PROMPT.md) - Instructions for AI agents
- [Query Tool Instructions](../docs/QUERY_TOOL_INSTRUCTIONS_ENHANCEMENT.md) - Query syntax guide
- [Schema Caching Implementation](./SCHEMA_CACHING_IMPLEMENTATION.md) - Detailed caching docs

## Disclaimer

This is a **sample implementation** provided for demonstration, reference, and educational purposes only. It illustrates concepts and patterns for building Langflow agents that interact with the OpenPages MCP server.

**This sample is intended to:**
- Demonstrate schema caching techniques
- Show conversation-aware agent behavior
- Illustrate custom tool creation
- Provide a starting point for learning and experimentation

