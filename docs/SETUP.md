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

Create a `.env` file in the project root with your OpenPages credentials.

**For On-Premises or IBM Cloud Hosted instances (use Basic Authentication):**

```env
# OpenPages Connection
OPENPAGES_BASE_URL=your-openpages-url.com
OPENPAGES_AUTHENTICATION_TYPE=basic
OPENPAGES_USERNAME=your-username
OPENPAGES_PASSWORD=your-password

# Server Settings
SERVER_MODE=local
SSL_VERIFY=True
LOG_LEVEL=INFO
DEBUG=False
HOST=0.0.0.0
PORT=8000
```

**For IBM Cloud SaaS instances (use Bearer Authentication):**

```env
# OpenPages Connection
OPENPAGES_BASE_URL=your-openpages-url.com
OPENPAGES_AUTHENTICATION_TYPE=bearer
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

Ensure these files exist:
- `src/app/config/object_types.json` - Object type configuration
- `.env` - Environment variables (in project root)

### 4. Run the Server

#### Local Mode (stdio transport for MCP clients):

**Using convenience script (recommended):**
```bash
# Linux/Mac
./scripts/run_mcp.sh local

# Windows
scripts\run_mcp.bat local
```

**Using Python directly:**
```bash
python main.py --mode local
```

With debug mode:
```bash
python main.py --mode local --debug
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

### Issue 1: "ModuleNotFoundError: No module named 'fastapi'"
**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### Issue 2: "No module named 'mcp'"
**Solution:** Install the MCP library:
```bash
pip install mcp>=1.9.4
```

### Issue 3: Object types not loading
**Solution:** Ensure `src/app/config/object_types.json` exists and is valid JSON. Tools are dynamically generated from this configuration file.

### Issue 4: Authentication errors
**Solution:**
- Verify your credentials in `.env`
- **For on-premises or IBM Cloud hosted instances:** Use `OPENPAGES_AUTHENTICATION_TYPE=basic` with username/password
- **For IBM Cloud SaaS instances:** Use `OPENPAGES_AUTHENTICATION_TYPE=bearer` with API key and authentication URL
- Ensure you have both `OPENPAGES_APIKEY` and `OPENPAGES_AUTHENTICATION_URL` for bearer auth
- Check that `OPENPAGES_BASE_URL` is correct (with or without https://)

## Testing

### Test Local Mode
```bash
# Start the server using convenience script
./scripts/run_mcp.sh local

# Or using Python directly
python main.py --mode local --debug
```

**Note:** Local mode uses stdio transport and is designed for MCP clients like IBM Bob or MCP Inspector. It does not provide an HTTP endpoint.

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
- [ ] `.env` file created with correct credentials in project root
- [ ] `src/app/config/object_types.json` exists and is valid JSON
- [ ] Local mode starts without errors (`python main.py --mode local`)
- [ ] Remote mode starts without errors (`python main.py --mode remote`)
- [ ] Can access API docs in remote mode (http://localhost:8000/docs)

## Next Steps

1. Test creating an object (Issue, Control, or Risk)
2. Test querying objects
3. Test updating objects
4. Test deleting objects
5. Add custom object types to `src/app/config/object_types.json` if needed

## Support

If you encounter any issues:
1. Check the logs for detailed error messages
2. Verify all configuration files are in place
3. Ensure all dependencies are installed
4. Review the MIGRATION_SUMMARY.md for detailed information about the changes