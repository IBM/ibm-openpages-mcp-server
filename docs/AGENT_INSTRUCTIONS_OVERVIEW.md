# OpenPages MCP Server - Agent Instructions Overview

## Introduction

This document provides an overview of the AI agent instruction sets available for the OpenPages MCP Server. The server supports two operational modes, each with its own set of instructions optimized for different use cases.

## Operational Modes

### Mode 1: Ontology-Based Mode (Resource-Driven)

**Document**: [MCP_SERVER_PROMPT.md](../src/docs/MCP_SERVER_PROMPT.md)

**Description**: Uses dynamic ontology discovery through MCP resources. This mode is flexible and ontology-driven, allowing agents to discover and work with object types dynamically.

**Key Characteristics:**
- ✅ Dynamic ontology discovery via resource URIs
- ✅ Flexible - works with any configured object type
- ✅ ontology caching for performance optimization
- ✅ Uses generic tools with ontology-driven validation
- ✅ Supports advanced query grammar with JOIN operations
- ✅ Ideal for exploratory operations and complex queries

**When to Use:**
- Working with multiple object types
- Need for complex hierarchical queries with JOINs
- Exploratory data analysis
- ontology discovery and validation
- Advanced query operations (COUNT, GROUP BY, hierarchical relationships)

**Core Workflow:**
1. Read `openpages://catalog/object_types` (once per session)
2. Read `openpages://schema/{ObjectType}` (once per object type)
3. Cache ontology for subsequent operations
4. Use `execute_openpages_query` tool for complex queries
5. Use generic upsert/query tools with ontology validation

**Tools Used:**
- `execute_openpages_query` - Advanced query tool with full SQL-like grammar
- Generic object tools (dynamically generated based on configuration)
- Resource access via `openpages://` URIs

---

### Mode 2: Type-Based Mode (Tool-Driven)

**Document**: [TYPE_BASED_MODE_PROMPT.md](TYPE_BASED_MODE_PROMPT.md)

**Description**: Uses predefined typed tools with embedded ontology. This mode is optimized for specific object type operations with faster performance and simpler workflows.

**Key Characteristics:**
- ✅ Predefined typed tools for specific object types
- ✅ Embedded ontology - no separate ontology fetching required
- ✅ Optimized performance - direct tool invocation
- ✅ Simplified field naming (user-friendly property names)
- ✅ Built-in association handling
- ✅ Ideal for standard CRUD operations

**When to Use:**
- Working with specific object types (Issues, Controls, Risks, Use Cases)
- Standard create, read, update operations
- Simple queries with filtering and sorting
- Performance-critical operations
- Straightforward data management tasks

**Core Workflow:**
1. Use typed tools directly (no ontology fetching needed)
2. Follow field naming conventions from tool ontology
3. Use system field filters (no prefix) and custom field filters (`filter_` prefix)
4. Leverage association fields for relationships

**Tools Used:**
- `openpages_upsert_issue` / `openpages_query_issue`
- `openpages_upsert_control` / `openpages_query_control`
- `openpages_upsert_risk` / `openpages_query_risk`
- `openpages_upsert_usecase` / `openpages_query_usecase`

---

## Common Elements

Both modes share these common features:

### Context Variables
Both modes support OpenPages UI context variables:
- `op_username`, `op_user_profile_id`, `op_user_locale`
- `op_object_id`, `op_object_type_name`, `op_object_name`
- `op_view_type`, `op_view_name`, `op_workflow_stage`
- `op_base_url`

### Date Handling
Both modes use the same date format:
- **Format**: `YYYY-MM-DD` (e.g., `2024-01-15`)
- **Date range filters**: `creation_date_from`, `creation_date_to`, etc.

### Default Query Fields
Both modes return these default fields in queries:
- `resource_id` - Unique object identifier
- `name` - Object name
- `description` - Object description
- `task_view_url` - Direct link to OpenPages UI


---

## Choosing the Right Mode

### Choose Ontology-Based Mode When:
- 🔍 You need to discover available object types dynamically
- 🔗 You need complex queries with JOINs and hierarchical relationships
- 📊 You're performing data analysis across multiple object types
- 🎯 You need to work with custom or newly configured object types
- 🔄 You need advanced query features (COUNT, GROUP BY, ANCESTOR/DESCENDANT)

### Choose Type-Based Mode When:
- ⚡ Performance is critical
- 🎯 You need simple CRUD operations

---

## Implementation Notes

### For Developers

**Ontology-Based Mode:**
- Implemented in: `src/app/mcp/resource_handlers.py`, `src/app/mcp/tool_handlers.py`
- ontology caching: `src/app/mcp/schema_builder.py`
- Query tool: `src/app/tools/query_tool.py`
- Configuration: `src/app/config/object_types.json`

**Type-Based Mode:**
- Implemented in: `src/app/tools/generic_object_tools.py`
- Tool generation: Dynamic based on object type configuration
- ontology embedding: ontology is built into tool definitions

### For AI Agent Developers

**Ontology-Based Mode:**
- Reference: [MCP_SERVER_PROMPT.md](MCP_SERVER_PROMPT.md)
- Sample implementation: [samples/OpenPagesQueryAgent/](../../samples/OpenPagesQueryAgent/)

**Type-Based Mode:**
- Reference: [TYPE_BASED_MODE_PROMPT.md](TYPE_BASED_MODE_PROMPT.md)
- Tool schemas: Available via MCP `tools/list` endpoint
- No additional setup required

---

## Related Documentation

### Core Documentation
- [MCP_SERVER_PROMPT.md](../src/docs/MCP_SERVER_PROMPT.md) - Ontology-Based Mode instructions
- [TYPE_BASED_MODE_PROMPT.md](TYPE_BASED_MODE_PROMPT.md) - Type-Based Mode instructions

### Technical Documentation
- [QUERY_GRAMMAR_RESOURCE.md](QUERY_GRAMMAR_RESOURCE.md) - Query syntax reference
- [RESOURCE_TOOLS.md](RESOURCE_TOOLS.md) - Resource access tools

### Setup and Deployment
- [SETUP.md](SETUP.md) - Server setup instructions
- [DEPLOYMENT.md](DEPLOYMENT.md) - Deployment guide
- [AUTHENTICATION.md](AUTHENTICATION.md) - Authentication configuration

### Monitoring and Operations
- [OBSERVABILITY.md](OBSERVABILITY.md) - Logging, metrics, and tracing
- [HEALTH_CHECKS.md](HEALTH_CHECKS.md) - Health check endpoints


---

## Support and Feedback

For questions, issues, or feedback:
1. Review the appropriate mode-specific documentation
2. Check the related technical documentation
3. Examine the sample implementations
4. Consult the test suite for usage examples

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-25 | Initial documentation split into mode-specific instructions |

---

**Note**: This overview document is maintained alongside the mode-specific instruction documents. When updating instructions, ensure all three documents remain synchronized.