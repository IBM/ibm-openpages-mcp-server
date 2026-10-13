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

### 2b. Encrypt credentials at rest (on-prem)

On-prem installations should not leave the OpenPages password in plaintext in `.env`.
Any setting can instead hold an `{enc}<base64>` value — the same convention as Liberty's
`{aes}` in `bootstrap.properties`. The server decrypts it at startup.

**One-time setup.** Pick where the keystore password lives first. A file readable only by
the service account is preferred over an environment variable, which anything that can
inspect the process or container definition can read:

```bash
umask 077
echo 'choose-a-strong-passphrase' > /etc/opmcp/keystore.pw
export OP_MCP_KEYSTORE_PASSWORD_FILE=/etc/opmcp/keystore.pw

venv/bin/python3 manage_secrets.py init
```

**Encrypt a value.** The plaintext is prompted for, never passed as an argument, so it
stays out of your shell history:

```bash
venv/bin/python3 manage_secrets.py encrypt --setting OPENPAGES_PASSWORD
```

Paste the printed line into `.env`, replacing the plaintext entry:

```env
OPENPAGES_PASSWORD={enc}<base64>
```

To encrypt the plaintext already in `.env` and rewrite that line in place, use
`--update-env` instead; `--stdin` reads the value from a pipe.

**Check and rotate.** `status` reports which settings are encrypted without decrypting
anything. `rotate` generates a new key, re-encrypts every `{enc}` value in `.env` under it,
and backs up both the old keystore and the old `.env` first:

```bash
venv/bin/python3 manage_secrets.py status
venv/bin/python3 manage_secrets.py rotate
```

**Back up the keystore** (`secrets/op-mcp-keystore.p12` by default). Without it every
`{enc}` value is unrecoverable. Never commit it — `.gitignore` excludes `secrets/` and
`*.p12`.

Encryption is opt-in per value: plaintext settings keep working unchanged, so an existing
install is unaffected until you choose to encrypt something.

Once a value *is* encrypted, the server will not start without the keystore that opens it.
That is deliberate. The common way to hit it is an unmounted `./secrets` volume — the
compose file always sets `OP_MCP_KEYSTORE_PATH`, so the path stays configured while the file
goes missing. Startup fails naming the settings it could not decrypt, which is far easier to
act on than ciphertext reaching OpenPages and coming back as an unexplained 401.

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