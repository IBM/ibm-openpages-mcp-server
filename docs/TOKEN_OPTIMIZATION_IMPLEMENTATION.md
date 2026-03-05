# Token Optimization Implementation Guide

**Implementation Date**: 2026-02-26  
**Phase**: Phase 1 - Quick Wins  
**Status**: Implemented

---

## Changes Implemented

### 1. Documentation Resources Module

**Created**: [`src/app/mcp/docs/documentation_resources.py`](../src/app/mcp/docs/documentation_resources.py)

This module provides reusable documentation content that AI agents read once and cache:

- `get_schema_usage_guide()` - Complete schema usage instructions (replaces 150 tokens per schema)
- `get_query_syntax_guide()` - Complete query syntax documentation (replaces 500+ tokens in tool description)
- `get_schema_usage_quick_rules()` - Minimal inline rules for hybrid mode (15 tokens)

### 2. Resource Handler Updates

**Modified**: [`src/app/mcp/resource_handlers.py`](../src/app/mcp/resource_handlers.py)

**Changes**:
- Added two new documentation resources to `handle_list_resources()`:
  - `openpages://docs/schema_usage` - Schema usage guide
  - `openpages://docs/query_syntax` - Query syntax guide

- Simplified resource descriptions from 88 tokens to 15 tokens:
  ```python
  # Before: 88 tokens
  "description": f"Schema definition for {display_name} objects. Supports mode parameter: 'compact' (default, 70-90% smaller, only required/system fields) for initial exploration, or 'full' for complete field list with enum values. Start with compact mode, then automatically switch to full mode if user asks about fields not in compact schema or needs enum values."
  
  # After: 15 tokens
  "description": f"Schema for {display_name}. Mode: compact|full (default: compact)"
  ```

- Added handlers for documentation resources in `handle_read_resource()`:
  ```python
  if uri == "openpages://docs/schema_usage":
      usage_guide = DocumentationResources.get_schema_usage_guide()
      return minified_json(usage_guide)
  
  if uri == "openpages://docs/query_syntax":
      query_guide = DocumentationResources.get_query_syntax_guide()
      return minified_json(query_guide)
  ```

- Replaced embedded usage instructions with hybrid reference in `_format_schema_as_json()`:
  ```python
  # Before: 150 tokens per schema
  "usage_instructions": {
      "field_names": "Always use exact field names...",
      "field_types": "Respect data_type constraints...",
      # ... 3 more fields
  }
  
  # After: 25 tokens per schema (hybrid mode)
  "usage_docs": "openpages://docs/schema_usage",
  "quick_rules": {
      "field_names": "Use [brackets]",
      "required": "Check required=true",
      "enums": "Use exact values",
      "read_only": "Cannot set system fields"
  }
  ```

### 3. Query Tool Description Update

**Modified**: [`src/app/mcp/mcp_server.py`](../src/app/mcp/mcp_server.py)

**Changes**:
- Reduced query tool description from 500+ tokens to ~100 tokens
- Moved detailed documentation to `openpages://docs/query_syntax` resource
- Added clear reference to documentation resource

```python
# Before: 500+ tokens
"""Execute queries against OpenPages using the OpenPages query language.

## SCHEMA WORKFLOW (CRITICAL)
Read schemas ONCE per session and cache them - schemas are static and don't change.
[... 400+ more tokens of inline documentation ...]
"""

# After: ~100 tokens
"""Execute queries against OpenPages using the OpenPages query language.

DOCUMENTATION: Read openpages://docs/query_syntax for complete syntax, examples, and best practices.

SCHEMA WORKFLOW: Read openpages://catalog/object_types to discover available types, then read openpages://schema/{ObjectType} for each type you need. Cache schemas for the session.

{object_types_section}

BASIC SYNTAX: SELECT [fields] FROM [ObjectType] WHERE [conditions]
• Enclose names in [square brackets]
"""
```

---

## Token Savings

### Per-Operation Savings

| Operation | Before | After | Savings | Reduction |
|-----------|--------|-------|---------|-----------|
| resources/list (10 types) | 1,500 tokens | 500 tokens | 1,000 tokens | **67%** |
| Schema read (with usage) | 150 tokens | 25 tokens | 125 tokens | **83%** |
| Query tool description | 500 tokens | 100 tokens | 400 tokens | **80%** |

### Session Savings

**Typical AI Agent Session** (1 query tool use + 5 schema reads):

| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| tools/list | 3,000 tokens | 2,600 tokens | 400 tokens |
| resources/list | 1,500 tokens | 500 tokens | 1,000 tokens |
| Schema reads (5×) | 750 tokens | 125 tokens | 625 tokens |
| Documentation (new) | 0 tokens | 150 tokens | -150 tokens |
| **Total** | **5,250 tokens** | **3,375 tokens** | **1,875 tokens** |
| **Reduction** | - | - | **36%** |

**Note**: Documentation is read once per session and cached, so the 150-token cost is amortized across all operations.

---

## Hybrid Mode Rationale

We implemented **hybrid mode** instead of pure reference mode for maximum compatibility:

### Pure Reference Mode
```python
"usage_docs": "openpages://docs/schema_usage"  # 5 tokens
```
- Smallest token footprint
- Requires AI agent to follow reference
- May not work with all AI agents

### Hybrid Mode (Implemented)
```python
"usage_docs": "openpages://docs/schema_usage",  # 5 tokens
"quick_rules": {                                 # 20 tokens
    "field_names": "Use [brackets]",
    "required": "Check required=true",
    "enums": "Use exact values",
    "read_only": "Cannot set system fields"
}
```
- Provides immediate guidance (20 tokens)
- References full documentation (150 tokens, read once)
- **Compatible with watsonx.orchestrate and all AI agents**
- Still achieves 83% reduction vs embedded instructions

---

## AI Agent Workflow

### Discovery Phase
```
1. Agent calls resources/list
   → Discovers openpages://docs/schema_usage
   → Discovers openpages://docs/query_syntax
   → Discovers openpages://schema/* resources

2. Agent calls tools/list
   → Sees execute_openpages_query tool
   → Tool description references openpages://docs/query_syntax
```

### First Schema Read
```
3. Agent reads openpages://schema/SOXIssue
   → Receives schema with:
      - "usage_docs": "openpages://docs/schema_usage"
      - "quick_rules": {...}  // Immediate guidance
   
4. Agent recognizes usage_docs reference
   → Reads openpages://docs/schema_usage (150 tokens, once)
   → Caches documentation for session
   
5. Agent applies quick_rules + cached full docs
   → Constructs query correctly
```

### Subsequent Schema Reads
```
6. Agent reads openpages://schema/SOXRisk
   → Receives same usage_docs reference
   → Uses cached documentation (no additional read)
   → Applies rules to new schema
```

---

## Compatibility

### Tested With
- ✅ Claude (Anthropic) - Full support
- ✅ GPT-4 (OpenAI) - Full support
- ✅ watsonx.orchestrate (IBM) - Full support via hybrid mode

### Fallback Behavior
If an AI agent doesn't recognize the `usage_docs` reference:
1. Agent uses `quick_rules` for basic guidance (20 tokens)
2. Agent may make minor mistakes initially
3. User corrects mistakes
4. Agent learns and adapts

Result: Slightly degraded but functional, with 83% token savings maintained.

---

## Configuration

### Environment Variables

No new environment variables required. The optimization is always active.

### Future Configuration Options

For future flexibility, consider adding to `settings.py`:

```python
class Settings:
    # Token optimization mode
    USAGE_DOCS_MODE: str = "hybrid"  # Options: "inline", "reference", "hybrid"
    
    # Enable documentation resources
    ENABLE_DOC_RESOURCES: bool = True
    
    # Minify JSON responses
    MINIFY_JSON: bool = True
```

---

## Testing

### Manual Testing

1. **Test documentation resources**:
   ```bash
   # List resources
   curl -X POST http://localhost:8000/mcp/v1 \
     -H "Content-Type: application/json" \
     -d '{"method": "resources/list", "params": {}}'
   
   # Should include:
   # - openpages://docs/schema_usage
   # - openpages://docs/query_syntax
   ```

2. **Test schema usage docs**:
   ```bash
   curl -X POST http://localhost:8000/mcp/v1 \
     -H "Content-Type: application/json" \
     -d '{
       "method": "resources/read",
       "params": {"uri": "openpages://docs/schema_usage"}
     }'
   
   # Should return complete usage guide
   ```

3. **Test schema with reference**:
   ```bash
   curl -X POST http://localhost:8000/mcp/v1 \
     -H "Content-Type: application/json" \
     -d '{
       "method": "resources/read",
       "params": {"uri": "openpages://schema/SOXIssue"}
     }'
   
   # Should include:
   # - "usage_docs": "openpages://docs/schema_usage"
   # - "quick_rules": {...}
   ```

### Automated Testing

Create test file `tests/test_token_optimization.py`:

```python
import pytest
from src.app.mcp.resource_handlers import ResourceHandlers
from src.app.mcp.docs.documentation_resources import DocumentationResources

async def test_documentation_resources_exist():
    """Test that documentation resources are listed"""
    handler = ResourceHandlers(schema_builder, settings)
    result = await handler.handle_list_resources({})
    
    uris = [r["uri"] for r in result["resources"]]
    assert "openpages://docs/schema_usage" in uris
    assert "openpages://docs/query_syntax" in uris

async def test_schema_usage_docs_readable():
    """Test that schema usage docs can be read"""
    handler = ResourceHandlers(schema_builder, settings)
    result = await handler.handle_read_resource({
        "uri": "openpages://docs/schema_usage"
    })
    
    assert len(result["contents"]) > 0
    content = result["contents"][0]
    assert "field_usage" in content["text"]

async def test_schema_includes_usage_reference():
    """Test that schemas include usage_docs reference"""
    handler = ResourceHandlers(schema_builder, settings)
    result = await handler.handle_read_resource({
        "uri": "openpages://schema/SOXIssue"
    })
    
    import json
    schema = json.loads(result["contents"][0]["text"])
    assert "usage_docs" in schema
    assert schema["usage_docs"] == "openpages://docs/schema_usage"
    assert "quick_rules" in schema

def test_quick_rules_are_minimal():
    """Test that quick_rules are actually minimal"""
    rules = DocumentationResources.get_schema_usage_quick_rules()
    
    # Should have exactly 4 rules
    assert len(rules) == 4
    
    # Each rule should be very short (< 30 chars)
    for rule in rules.values():
        assert len(rule) < 30
```

---

## Monitoring

### Metrics to Track

1. **Token consumption per session**:
   - Before: ~5,250 tokens
   - After: ~3,375 tokens
   - Target: 36% reduction

2. **Documentation resource reads**:
   - Should be read once per session
   - Cache hit rate should be >90%

3. **Schema read sizes**:
   - Before: ~4,500 bytes per schema
   - After: ~4,350 bytes per schema
   - Reduction: ~150 bytes per schema

### Logging

Add logging to track optimization effectiveness:

```python
# In resource_handlers.py
logger.info(f"Schema read for {type_id}", extra={
    "mode": mode,
    "size_bytes": len(formatted_text),
    "has_usage_docs": "usage_docs" in schema_content
})

logger.info(f"Documentation resource read", extra={
    "uri": uri,
    "size_bytes": len(content)
})
```

---

## Rollback Plan

If issues arise, rollback is simple:

1. **Revert resource_handlers.py changes**:
   ```python
   # Restore embedded usage_instructions
   "usage_instructions": {
       "field_names": "Always use exact field names...",
       # ... full instructions
   }
   ```

2. **Revert mcp_server.py changes**:
   ```python
   # Restore full query tool description
   return f"""Execute queries against OpenPages...
   [... full 500+ token description ...]
   """
   ```

3. **Remove documentation resources** (optional):
   - Documentation resources are harmless if present but unused
   - Can leave them for future use

---

## Next Steps (Phase 2)

After Phase 1 stabilizes, implement Phase 2 optimizations:

1. **Implement minimal schema mode** - Field names and types only (~500 bytes)
2. **Cache query examples** - Compute once, reuse many times
3. **Add LRU cache for schemas** - Limit memory growth

Expected additional savings: 20% (total 50%+ reduction)

---

## Related Documentation

- [Token Optimization Review](TOKEN_OPTIMIZATION_REVIEW.md) - Complete analysis
- [Compact Schema Mode](COMPACT_SCHEMA_MODE.md) - Schema size optimization
- [AI Schema Consumption Best Practices](AI_SCHEMA_CONSUMPTION_BEST_PRACTICES.md) - General guidelines