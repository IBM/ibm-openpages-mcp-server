# Setup Instructions

## Quick Start

### 1. Install Dependencies

```bash
# Install all required dependencies
pip install -r requirements.txt
```

If you encounter any issues, install the core dependencies individually:

```bash
pip install fastapi>=0.104.0
pip install uvicorn>=0.24.0
pip install httpx>=0.24.0
pip install pydantic>=2.5.0
pip install pydantic-settings>=2.1.0
pip install mcp>=1.9.4
pip install python-dotenv>=1.0.0
```

### 2. Configure Environment

Create a `.env` file in the project root with your OpenPages credentials:

```env
# OpenPages Connection
OPENPAGES_BASE_URL=your-openpages-url.com
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=your-username
OPENPAGES_PASSWORD=your-password

# For Bearer Authentication (optional)
OPENPAGES_APIKEY=your-api-key
OPENPAGES_AUTHENTICATION_URL=https://iam.cloud.ibm.com/identity/token

# Server Settings
SERVER_MODE=local
SSL_VERIFY=True
LOG_LEVEL=INFO
DEBUG=False
HOST=0.0.0.0
PORT=8000
```

### 3. Verify Configuration Files

Ensure these files exist in the project root:
- `object_types.json` - Object type configuration
- `.env` - Environment variables

### 4. Run the Server

#### Local Mode (stdio transport for MCP clients):
```bash
python src/app/local_mcp/run_local_mcp.py
```

With debug mode:
```bash
python src/app/local_mcp/run_local_mcp.py --debug
```

#### Remote Mode (HTTP API):
```bash
python main.py --mode remote
```

Or with custom settings:
```bash
python main.py --mode remote --host 0.0.0.0 --port 8000
```

## Troubleshooting

### Issue 1: "Tools schema file not found"
**Solution:** The `tools_schema.json` file should be in `src/app/local_mcp/`. It has been copied from the beta version.

### Issue 2: "ModuleNotFoundError: No module named 'fastapi'"
**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### Issue 3: "No module named 'mcp'"
**Solution:** Install the MCP library:
```bash
pip install mcp>=1.9.4
```

### Issue 4: Object types not loading
**Solution:** Ensure `object_types.json` is in the project root directory and is valid JSON.

### Issue 5: Authentication errors
**Solution:** 
- Verify your credentials in `.env`
- For bearer auth, ensure you have both `OPENPAGES_APIKEY` and `OPENPAGES_AUTHENTICATION_URL`
- Check that `OPENPAGES_BASE_URL` is correct (with or without https://)

## Testing

### Test Local Mode
```bash
# Start the server
python src/app/local_mcp/run_local_mcp.py --debug

# In another terminal, test with MCP inspector
python run_mcp_inspector.py
```

### Test Remote Mode
```bash
# Start the server
python main.py --mode remote

# Test the health endpoint
curl http://localhost:8000/

# Test the API
curl http://localhost:8000/docs
```

## Verification Checklist

- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with correct credentials
- [ ] `object_types.json` exists in project root
- [ ] `tools_schema.json` exists in `src/app/local_mcp/`
- [ ] Local mode starts without errors
- [ ] Remote mode starts without errors
- [ ] Can list tools in local mode
- [ ] Can access API docs in remote mode (http://localhost:8000/docs)

## Next Steps

1. Test creating an object (Issue, Control, or Risk)
2. Test querying objects
3. Test updating objects
4. Test deleting objects
5. Add custom object types to `object_types.json` if needed

## Support

If you encounter any issues:
1. Check the logs for detailed error messages
2. Verify all configuration files are in place
3. Ensure all dependencies are installed
4. Review the MIGRATION_SUMMARY.md for detailed information about the changes