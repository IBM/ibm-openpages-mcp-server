# Integration Tests for GRC MCP Server

This directory contains integration tests for the deployed GRC MCP Server, focusing on ontology-based tools.

## Overview

The test suite validates a deployed MCP server instance by testing:

1. **Health & Protocol** - Server availability and MCP protocol compliance
2. **Resource Discovery** - Catalog and object type schema retrieval
3. **Query Execution** - OpenPages query tool functionality
4. **Complete CRUD Workflow** - End-to-end object lifecycle testing

## Test Structure

### Single Test File: `test_deployed_ontology_tools.py`

The test suite is organized into test classes that run in sequence:

```
TestHealthEndpoint (1 test)
├── test_health_endpoint

TestMCPProtocol (3 tests)
├── test_initialize
├── test_tools_list
└── test_resources_list

TestResourceDiscovery (3 tests)
├── test_list_resources_via_tool
├── test_get_resource_catalog_via_tool
└── test_get_resource_schema_via_tool

TestResourceRetrieval (2 tests)
├── test_read_catalog_resource_via_mcp
└── test_read_object_type_schema_via_mcp

TestQueryExecution (2 tests)
├── test_simple_query
└── test_query_with_filter

TestCRUDWorkflow (8 tests - run in order, share state)
├── test_01_create_issue          → Creates Issue, stores ID
├── test_02_update_issue          → Updates Issue using stored ID
├── test_03_create_control        → Creates Control, stores ID
├── test_04_associate_objects     → Associates Control with Issue
├── test_05_verify_association    → Queries to verify association
├── test_06_dissociate_objects    → Removes association
├── test_07_delete_control        → Deletes Control
└── test_08_delete_issue          → Deletes Issue
```

**Total: 19 tests**

### CRUD Workflow Details

The CRUD tests run **sequentially** and share state via the `crud_state` fixture:

- **State Sharing**: Object IDs are passed between tests using a class-scoped fixture
- **Test Ordering**: Tests use `@pytest.mark.order()` to ensure correct execution sequence
- **Failure Isolation**: If a test fails, you can pinpoint exactly which tool/operation failed
- **Automatic Cleanup**: Delete tests run at the end to clean up test objects

**Key Benefits:**
- ✅ Each tool is tested independently
- ✅ Failures are easy to diagnose (specific test name shows which tool failed)
- ✅ Tests can be run individually for debugging
- ✅ Complete workflow validation from create to delete

## Configuration

### Required Configuration

Only one environment variable is required:

```bash
export MCP_SERVER_URL="http://your-server:8000"
```

### Optional Configuration

You can customize test behavior via environment variables or a `config.json` file:

**Environment Variables:**
```bash
export MCP_API_KEY="your-api-key"                  # Required for production mode
export MCP_API_KEY_HEADER="X-Api-Key"              # Optional: custom header name
export MCP_SERVER_URL="http://localhost:8000"      # Required
export TEST_OBJECT_TYPE="issue"                     # Default: "issue"
export TIMEOUT="60"                                 # Default: 60 seconds
export CLEANUP_TEST_OBJECTS="true"                  # Default: true
export RATE_LIMIT_DELAY="1.0"                       # Default: 1.0 seconds
```

**config.json (optional):**
```json
  "api_key": "your-api-key-here",
  "api_key_header_name": "X-Api-Key",
{
  "mcp_server_url": "http://localhost:8000",
  "test_object_type": "issue",
  "timeout": 60,
  "cleanup_test_objects": true,
  "rate_limit_delay": 1.0
}
```

**Note:** Environment variables take precedence over `config.json` values.

### Configuration Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `mcp_server_url` | URL of deployed MCP server | - | **Yes** |
| `api_key` | API key for authentication | - | **Yes** (production) |
| `api_key_header_name` | Name of API key header | `"X-Api-Key"` | No |
| `test_object_type` | Object type for query tests | `"issue"` | No |
| `timeout` | HTTP request timeout (seconds) | `60` | No |
| `cleanup_test_objects` | Delete test objects after tests | `true` | No |
| `rate_limit_delay` | Delay between requests (seconds) | `1.0` | No |

### Authentication & Session Management

**Authentication:**

The tests support the MCP server's authentication requirements:
- **Production/Remote Mode** (`OPENPAGES_AUTH_MODE=user`): Requires `MCP_API_KEY` environment variable or `api_key` in config.json
- **Development/Local Mode** (`OPENPAGES_AUTH_MODE=server`): No authentication required

The API key is sent in the `X-Api-Key` header (or custom header specified by `MCP_API_KEY_HEADER`).

**Session Management:**

Tests use a **single MCP client session** for all tests:
- Session is initialized once at the start with the `initialize` handshake
- Session ID (if provided by server via `Mcp-Session-Id` header) is captured and reused
- All subsequent requests include the session ID in the `Mcp-Session-Id` header
- Session is closed at the end of all tests
- Supports servers with `MCP_SESSION_ENFORCEMENT=true`

This approach maintains session state across tests and matches real-world client behavior.

## Running Tests


### With Authentication (Production Mode)

Run tests with API key authentication:
```bash
MCP_SERVER_URL="http://localhost:8000" \
MCP_API_KEY="your-api-key" \
pytest tests/integration/test_deployed_ontology_tools.py -v
```

With custom API key header name:
```bash
MCP_SERVER_URL="http://localhost:8000" \
MCP_API_KEY="your-api-key" \
MCP_API_KEY_HEADER="X-Custom-Api-Key" \
pytest tests/integration/test_deployed_ontology_tools.py -v -s
```
### Prerequisites

1. Install dependencies:
```bash
pip install pytest pytest-asyncio httpx
```

2. Ensure MCP server is deployed and accessible

### Basic Usage

Run all tests:
```bash
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py -v
```

Run with detailed output:
```bash
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py -v -s
```

### Running Specific Test Classes

Run only health and protocol tests:
```bash
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestHealthEndpoint -v
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestMCPProtocol -v
```

Run only resource tests:
```bash
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestResourceDiscovery -v
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestResourceRetrieval -v
```

Run only query tests:
```bash
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestQueryExecution -v
```

Run only CRUD workflow:
```bash
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestCRUDWorkflow -v -s
```

### Running Individual CRUD Tests

You can run individual CRUD tests for debugging (but they depend on previous tests):

```bash
# Run just the create test
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestCRUDWorkflow::test_01_create_issue -v -s

# Run create and update tests
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestCRUDWorkflow::test_01_create_issue tests/integration/test_deployed_ontology_tools.py::TestCRUDWorkflow::test_02_update_issue -v -s
```

**Note:** CRUD tests depend on each other, so running them out of order may fail.

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  integration-test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install pytest pytest-asyncio httpx
    
    - name: Run integration tests
      env:
        MCP_SERVER_URL: ${{ secrets.MCP_SERVER_URL }}
        TIMEOUT: 60
        RATE_LIMIT_DELAY: 1.0
      run: |
        pytest tests/integration/test_deployed_ontology_tools.py -v --tb=short
```

### Jenkins Pipeline Example

```groovy
pipeline {
    agent any
    
    environment {
        MCP_SERVER_URL = credentials('mcp-server-url')
        TIMEOUT = '60'
        RATE_LIMIT_DELAY = '1.0'
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install pytest pytest-asyncio httpx'
            }
        }
        
        stage('Integration Tests') {
            steps {
                sh '''
                    pytest tests/integration/test_deployed_ontology_tools.py \
                        -v --tb=short \
                        --junitxml=test-results.xml
                '''
            }
        }
    }
    
    post {
        always {
            junit 'test-results.xml'
        }
    }
}
```

### GitLab CI Example

```yaml
integration-tests:
  stage: test
  image: python:3.11
  
  variables:
    TIMEOUT: "60"
    RATE_LIMIT_DELAY: "1.0"
  
  before_script:
    - pip install pytest pytest-asyncio httpx
  
  script:
    - pytest tests/integration/test_deployed_ontology_tools.py -v --tb=short
  
  only:
    - main
    - develop
```

## Test Validation

### What Each Test Validates

#### Health & Protocol Tests
- ✅ Server is accessible and healthy
- ✅ MCP protocol handshake works
- ✅ All required tools are registered
- ✅ Resources are available

#### Resource Tests
- ✅ Catalog resource is accessible
- ✅ Object type schemas are available
- ✅ Resources can be listed via tools
- ✅ Resources can be read via MCP endpoints

#### Query Tests
- ✅ Simple SELECT queries work
- ✅ Queries with WHERE clauses work
- ✅ Query results are properly formatted

#### CRUD Workflow Tests
- ✅ `openpages_upsert_object` - Create objects
- ✅ `openpages_upsert_object` - Update objects
- ✅ `openpages_associate_objects` - Create associations
- ✅ `execute_openpages_query` - Verify data
- ✅ `openpages_dissociate_objects` - Remove associations
- ✅ `openpages_delete_object` - Delete objects

## Troubleshooting

### Common Issues

#### 1. Connection Refused
```
Error: Connection refused to http://localhost:8000
```

**Solution:** Ensure the MCP server is running and accessible at the specified URL.

#### 2. Timeout Errors
```
Error: ReadTimeout
```

**Solutions:**
- Increase timeout: `export TIMEOUT=120`
- Check server performance
- Verify network connectivity

#### 3. Rate Limiting (429 Errors)
```
Error: 429 Too Many Requests
```

**Solutions:**
- Increase delay: `export RATE_LIMIT_DELAY=2.0`
- Tests will automatically skip on rate limit errors

#### 4. Authentication Errors
```
Error: 401 Unauthorized
```

**Solution:** Ensure the MCP server has valid OpenPages credentials configured.

#### 5. CRUD Test Failures

If a CRUD test fails, the exact failing tool is identified by the test name:

- `test_01_create_issue` fails → `openpages_upsert_object` (create) has issues
- `test_02_update_issue` fails → `openpages_upsert_object` (update) has issues
- `test_04_associate_objects` fails → `openpages_associate_objects` has issues
- `test_06_dissociate_objects` fails → `openpages_dissociate_objects` has issues
- `test_07_delete_control` fails → `openpages_delete_object` has issues

### Debug Mode

Run tests with maximum verbosity:
```bash
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py -vv -s --tb=long
```

### Test Specific Tool

To test a specific tool in isolation:

```bash
# Test only query tool
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestQueryExecution -v -s

# Test only create operation
MCP_SERVER_URL="http://localhost:8000" pytest tests/integration/test_deployed_ontology_tools.py::TestCRUDWorkflow::test_01_create_issue -v -s
```

## Test Output

The test suite provides detailed output with custom formatting:

```
=== Integration Test Results ===

Health & Protocol:
  ✓ test_health_endpoint (0.15s)
  ✓ test_initialize (0.23s)
  ✓ test_tools_list (0.18s)
  ✓ test_resources_list (0.21s)

Resource Discovery:
  ✓ test_list_resources_via_tool (1.12s)
  ✓ test_get_resource_catalog_via_tool (1.08s)
  ✓ test_get_resource_schema_via_tool (1.15s)

Query Execution:
  ✓ test_simple_query (1.34s)
  ✓ test_query_with_filter (1.28s)

CRUD Workflow:
  ✓ test_01_create_issue (1.45s)
  ✓ test_02_update_issue (1.38s)
  ✓ test_03_create_control (1.42s)
  ✓ test_04_associate_objects (1.51s)
  ✓ test_05_verify_association (1.29s)
  ✓ test_06_dissociate_objects (1.47s)
  ✓ test_07_delete_control (1.33s)
  ✓ test_08_delete_issue (1.35s)

Total: 19 passed in 18.94s
```

## Files

- `test_deployed_ontology_tools.py` - Main test suite (all tests)
- `conftest.py` - Pytest configuration and custom reporting
- `pytest.ini` - Pytest settings
- `config.json.example` - Example configuration file
- `README.md` - This file

## Dependencies

```
pytest>=7.0.0
pytest-asyncio>=0.21.0
httpx>=0.24.0
```

Install with:
```bash
pip install pytest pytest-asyncio httpx
```

## License

This test suite is part of the GRC MCP Server project.