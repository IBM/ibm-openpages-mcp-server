# Deploying OpenPages MCP Server to IBM Orchestrate (AWS Marketplace)

This guide explains how to deploy your OpenPages MCP server to IBM Orchestrate on AWS Marketplace, using API key authentication for secure access to OpenPages.

## Overview

IBM Orchestrate on AWS Marketplace is a cloud-based platform that allows you to integrate various tools and services, including MCP (Model Context Protocol) servers, making them available to AI agents and automation workflows. By deploying your OpenPages MCP server to Orchestrate, you can:

- Make OpenPages GRC capabilities available to AI agents across your organization
- Manage API keys securely for multiple environments (draft, live, production)
- Enable team-wide access to OpenPages tools through a centralized cloud platform
- Integrate with other Orchestrate toolkits and workflows
- Leverage AWS infrastructure for scalability and reliability

## Understanding Environments

In Orchestrate, **environments** are logical separations that allow you to maintain different configurations and credentials for different stages of your deployment lifecycle. They are **not files**, but rather configuration contexts within Orchestrate.

### Common Environment Types

- **draft**: Development/testing environment
  - Used for testing changes before production
  - Points to a non-production OpenPages instance
  - Uses separate API keys with limited permissions
  - Safe for experimentation

- **live** (or **production**): Production environment
  - Used for actual business operations
  - Points to your production OpenPages instance
  - Uses production API keys with appropriate permissions
  - Requires careful change management

- **staging** (optional): Pre-production environment
  - Used for final testing before production deployment
  - Mirrors production configuration
  - Separate API keys and OpenPages instance

### How Environments Work

When you create a connection in Orchestrate, you configure it for specific environments:

```bash
# This creates separate credential sets for "draft" and "live"
for env in draft live; do
    orchestrate connections configure -a openpages-grc --env $env
done
```

Each environment maintains its own:
- OpenPages base URL (e.g., `https://openpages-draft.aws.com` vs `https://openpages-live.aws.com`)
- API keys (different keys for draft vs live)
- Configuration settings

When AI agents or workflows use your toolkit, they specify which environment to use:
```bash
# Use draft environment for testing
orchestrate toolkits invoke --name openpages-grc --env draft --tool query_issues

# Use live environment for production
orchestrate toolkits invoke --name openpages-grc --env live --tool query_issues
```

## Prerequisites

Before deploying to Orchestrate on AWS Marketplace, ensure you have:

1. **AWS Account** with access to AWS Marketplace
2. **IBM Orchestrate subscription** on AWS Marketplace (active and configured)
3. **OpenPages instances** for each environment:
   - Draft/development OpenPages instance (optional but recommended)
   - Production OpenPages instance
4. **OpenPages API Keys** for each environment you want to deploy to
5. **Orchestrate CLI installed** and configured with your AWS credentials
6. **OpenPages MCP Server** tested locally with API key authentication
7. **Python 3.12+** available in your Orchestrate execution environment

## AWS Marketplace Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AWS Cloud Infrastructure                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                  IBM Orchestrate (AWS Marketplace)                │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  Orchestrate Connections (Secure Credential Vault)          │ │  │
│  │  │  ┌──────────────────┐  ┌──────────────────┐                │ │  │
│  │  │  │ Draft Env        │  │ Live Env         │                │ │  │
│  │  │  │ • OP_BASE_URL    │  │ • OP_BASE_URL    │                │ │  │
│  │  │  │ • OP_APIKEY      │  │ • OP_APIKEY      │                │ │  │
│  │  │  │ • OP_AUTH_URL    │  │ • OP_AUTH_URL    │                │ │  │
│  │  │  │ (AWS Secrets)    │  │ (AWS Secrets)    │                │ │  │
│  │  │  └──────────────────┘  └──────────────────┘                │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  Orchestrate Toolkit (MCP Server)                           │ │  │
│  │  │  • Name: openpages-grc                                      │ │  │
│  │  │  • Kind: mcp                                                │ │  │
│  │  │  • Command: python main.py --mode local                     │ │  │
│  │  │  • Tools: All OpenPages tools                              │ │  │
│  │  │  • Execution: AWS Lambda or ECS                            │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  │  ┌─────────────────────────────────────────────────────────────┐ │  │
│  │  │  AI Agents & Workflows                                      │ │  │
│  │  │  • Access via Orchestrate API                               │ │  │
│  │  │  • API key authentication                                   │ │  │
│  │  │  • Execute GRC operations                                   │ │  │
│  │  └─────────────────────────────────────────────────────────────┘ │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                │                                         │
│                                │ HTTPS + API Key                         │
│                                ▼                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │          OpenPages on AWS Marketplace (or VPC)                    │  │
│  │  • REST API with API Key authentication                           │  │
│  │  • Secure token-based access                                      │  │
│  │  • Multi-environment support                                      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Deployment

### Step 0: Obtain OpenPages API Keys

Before deployment, obtain API keys from your OpenPages AWS Marketplace instance:

1. **Log into OpenPages** on AWS Marketplace
2. **Navigate to API Settings** (typically under Administration > API Keys)
3. **Generate API Keys** for each environment:
   - Draft environment API key
   - Live/Production environment API key
4. **Note the Authentication URL** (e.g., `https://your-openpages.aws.com/api/auth`)
5. **Save keys securely** - you'll need them for the next steps

### Step 1: Test MCP Server Locally with API Key

Before deploying to Orchestrate, verify your server works with API key authentication:

```bash
# 1. Navigate to your MCP server directory
cd /path/to/grc-mcp-server

# 2. Create a test environment file with API key
cat > .env.test << EOF
OPENPAGES_BASE_URL=https://your-openpages.aws.com
OPENPAGES_AUTHENTICATION_TYPE=bearer
OPENPAGES_APIKEY=your-api-key-here
OPENPAGES_AUTHENTICATION_URL=https://your-openpages.aws.com/api/auth
SSL_VERIFY=True
SERVER_MODE=local
DEBUG=False
EOF

# 3. Test the server locally
python main.py --mode local --env-file .env.test

# 4. In another terminal, test with MCP Inspector or a simple test
# The server should successfully authenticate and list tools
```

### Step 2: Create Orchestrate Connection

Create a connection in Orchestrate on AWS Marketplace to manage OpenPages API keys:

```bash
# Add the connection
orchestrate connections add -a openpages-grc

# Configure for each environment
for env in draft live; do
    orchestrate connections configure \
        -a openpages-grc \
        --env $env \
        --type team \
        --kind key_value
done
```

**Explanation**:
- `-a openpages-grc`: Application/connection name
- `--env $env`: Environment (draft, live, production, etc.)
- `--type team`: Shared credentials across team members (stored in AWS Secrets Manager)
- `--kind key_value`: Store credentials as key-value pairs

### Step 3: Set API Key Credentials for Each Environment

Store OpenPages API keys securely in Orchestrate (backed by AWS Secrets Manager):

```bash
# Set API key for draft environment
orchestrate connections set-credentials \
    -a openpages-grc \
    --env draft \
    -e "OPENPAGES_BASE_URL=https://openpages-draft.aws.com" \
    -e "OPENPAGES_AUTHENTICATION_TYPE=bearer" \
    -e "OPENPAGES_APIKEY=your-draft-api-key-here" \
    -e "OPENPAGES_AUTHENTICATION_URL=https://openpages-draft.aws.com/api/auth"

# Set API key for live environment
orchestrate connections set-credentials \
    -a openpages-grc \
    --env live \
    -e "OPENPAGES_BASE_URL=https://openpages-live.aws.com" \
    -e "OPENPAGES_AUTHENTICATION_TYPE=bearer" \
    -e "OPENPAGES_APIKEY=your-live-api-key-here" \
    -e "OPENPAGES_AUTHENTICATION_URL=https://openpages-live.aws.com/api/auth"
```

**Security Notes**:
- API keys are stored in AWS Secrets Manager via Orchestrate
- Keys are encrypted at rest and in transit
- Access is controlled via AWS IAM policies
- Keys are never exposed in logs or API responses
- Supports automatic key rotation if configured in OpenPages

### Step 4: Package MCP Server for AWS Deployment

Prepare your MCP server for deployment in AWS environment:

```bash
# 1. Create a deployment package
cd /path/to/grc-mcp-server

# 2. Ensure all dependencies are listed
pip freeze > requirements.txt

# 3. Create a deployment-ready package (if using Lambda)
# Note: Orchestrate may handle this automatically
mkdir -p deployment
cp -r src deployment/
cp main.py requirements.txt deployment/
cp -r src/app/config/object_types.json deployment/src/app/config/

# 4. Create a deployment configuration file
cat > deployment/orchestrate_config.json << EOF
{
  "runtime": "python3.12",
  "handler": "main.py",
  "mode": "local",
  "environment_variables": {
    "SERVER_MODE": "local",
    "SSL_VERIFY": "True",
    "LOG_LEVEL": "INFO"
  }
}
EOF
```

### Step 5: Register MCP Server as Orchestrate Toolkit

Register your OpenPages MCP server as an Orchestrate toolkit using the correct command syntax:

```bash
# Import the toolkit
orchestrate toolkits add \
    --kind mcp \
    --name openpages-grc \
    --description "IBM OpenPages GRC on AWS - API key auth - provides tools for managing controls, risks, issues, and executing SQL queries" \
    --command "python main.py --mode local" \
    --package-root "./grc-mcp-server" \
    --language python \
    --tools "*" \
    --app-id openpages-grc
```

**Parameters Explained**:
- `--kind mcp`: Specifies this is an MCP server toolkit
- `--name openpages-grc`: Toolkit name (used for identification in Orchestrate)
- `--description`: Human-readable description of what the toolkit does
- `--command`: Command to execute the MCP server (`python main.py --mode local`)
- `--package-root`: Path to your MCP server code directory (e.g., `"./grc-mcp-server"`)
  - This should be the directory containing your `main.py`, `src/`, and `requirements.txt`
  - Can be a relative or absolute path
- `--language python`: Specifies the runtime language (Python)
  - Orchestrate will automatically install dependencies from `requirements.txt`
- `--tools "*"`: Wildcard to include all tools from the server
- `--app-id openpages-grc`: Links to the connection created earlier (provides API keys from AWS Secrets Manager)

**Important Notes**:
1. **Package Root**: The `--package-root` should point to where your MCP server code is located
   - If deploying from your local machine: `"./grc-mcp-server"` or full path
   - Orchestrate will upload this directory to AWS
   
2. **Dependencies**: Orchestrate automatically installs Python dependencies from `requirements.txt` in the package root

3. **Environment Variables**: API keys and other credentials are automatically injected from the connection (stored in AWS Secrets Manager)

**Alternative: Using pipx (for published packages)**

If you publish your MCP server as a Python package to PyPI or a private repository:

```bash
orchestrate toolkits add \
    --kind mcp \
    --name openpages-grc \
    --description "IBM OpenPages GRC integration - API key authentication" \
    --command "pipx run openpages-mcp-server@1.0.0" \
    --tools "*" \
    --app-id openpages-grc
```

This approach is similar to the Tavily example and doesn't require `--package-root` since the package is installed from a repository.

### Step 6: Verify Deployment

Test that your toolkit is properly registered and working:

```bash
# 1. List all toolkits
orchestrate toolkits list

# 2. Get details about your toolkit
orchestrate toolkits get --name openpages-grc

# 3. Verify connection to OpenPages
orchestrate connections test -a openpages-grc --env draft

# 4. Test toolkit execution (if Orchestrate provides this)
orchestrate toolkits test --name openpages-grc --env draft

# 5. Test a specific tool
orchestrate toolkits invoke \
    --name openpages-grc \
    --env draft \
    --tool execute_openpages_query \
    --params '{"query": "SELECT [Name] FROM [SOXIssue] LIMIT 5", "format": "json"}'
```

**Expected Results**:
- Toolkit should be listed and show as "active"
- Connection test should succeed with API key authentication
- Tool invocation should return OpenPages data
- No authentication errors in logs

## Available Tools

Once deployed, the following tools will be available in Orchestrate:

### Generic Object Management
- `openpages_manage_object`: Schema-aware CRUD operations for any object type

### SQL Query Tool
- `execute_openpages_query`: Execute SQL-like queries against OpenPages

### Object-Specific Tools (Configurable)
Based on your `object_types.json` configuration:

**Controls**:
- `openpages_upsert_control`: Create or update controls
- `openpages_query_controls`: Search and retrieve controls
- `openpages_delete_control`: Delete controls

**Issues**:
- `openpages_upsert_issue`: Create or update issues
- `openpages_query_issues`: Search and retrieve issues
- `openpages_delete_issue`: Delete issues

**Risks**:
- `openpages_upsert_risk`: Create or update risks
- `openpages_query_risks`: Search and retrieve risks
- `openpages_delete_risk`: Delete risks

## AWS-Specific Configuration

### Environment Variables in AWS

When deploying to Orchestrate on AWS, environment variables are managed through the connection:

```bash
# All environment variables are set via the connection
# No need for .env files in AWS deployment

# Example: Adding additional configuration
orchestrate connections set-credentials \
    -a openpages-grc \
    --env draft \
    -e "OPENPAGES_BASE_URL=https://openpages-draft.aws.com" \
    -e "OPENPAGES_AUTHENTICATION_TYPE=bearer" \
    -e "OPENPAGES_APIKEY=your-api-key" \
    -e "OPENPAGES_AUTHENTICATION_URL=https://openpages-draft.aws.com/api/auth" \
    -e "SSL_VERIFY=True" \
    -e "LOG_LEVEL=INFO" \
    -e "RATE_LIMIT_ENABLED=True"
```

### AWS Secrets Manager Integration

Orchestrate automatically stores credentials in AWS Secrets Manager:

```bash
# View secrets (requires AWS CLI and appropriate IAM permissions)
aws secretsmanager list-secrets --filters Key=tag-key,Values=orchestrate-connection

# Rotate API keys
# 1. Generate new API key in OpenPages
# 2. Update the connection
orchestrate connections set-credentials \
    -a openpages-grc \
    --env live \
    -e "OPENPAGES_APIKEY=new-api-key-here"

# 3. Restart the toolkit
orchestrate toolkits restart --name openpages-grc
```

### Dynamic Object Types

To add or modify available object types:

1. Edit `src/app/config/object_types.json`
2. Restart the toolkit in Orchestrate
3. New tools will be automatically available

## Monitoring and Troubleshooting on AWS

### Viewing Logs

Orchestrate on AWS integrates with CloudWatch for logging:

```bash
# View toolkit execution logs via Orchestrate CLI
orchestrate toolkits logs --name openpages-grc --env draft --tail 100

# View logs in AWS CloudWatch (requires AWS CLI)
aws logs tail /aws/orchestrate/openpages-grc --follow

# Check connection status
orchestrate connections status -a openpages-grc --env draft

# View CloudWatch metrics
aws cloudwatch get-metric-statistics \
    --namespace Orchestrate/Toolkits \
    --metric-name Invocations \
    --dimensions Name=ToolkitName,Value=openpages-grc \
    --start-time 2024-01-01T00:00:00Z \
    --end-time 2024-01-02T00:00:00Z \
    --period 3600 \
    --statistics Sum
```

### Common Issues

**Issue: "Authentication failed" or "Invalid API key"**
```bash
# Verify API key is set correctly
orchestrate connections get-credentials -a openpages-grc --env draft

# Test OpenPages API key directly
curl -X POST https://your-openpages.aws.com/api/auth \
  -H "Content-Type: application/json" \
  -d '{"apiKey": "your-api-key"}'

# Update API key if needed
orchestrate connections set-credentials \
    -a openpages-grc \
    --env draft \
    -e "OPENPAGES_APIKEY=new-valid-api-key"
```

**Issue: "Connection timeout" or "Network error"**
```bash
# Check if OpenPages is accessible from AWS
# Verify VPC peering or security groups if using private OpenPages

# Test connectivity
curl -v https://your-openpages.aws.com/api/health

# Check AWS security groups and network ACLs
aws ec2 describe-security-groups --filters Name=tag:Name,Values=orchestrate-*

# Verify SSL certificate
openssl s_client -connect your-openpages.aws.com:443 -servername your-openpages.aws.com
```

**Issue: "Runtime error" or "Module not found"**
```bash
# Verify all dependencies are in requirements.txt
cat requirements.txt

# Check toolkit configuration
orchestrate toolkits get --name openpages-grc

# Redeploy if needed
orchestrate toolkits redeploy --name openpages-grc
```

**Issue: "uv install failed: exit status 1" - Dependency Installation Failed**

This error means Orchestrate's `uv` package installer failed to install your dependencies from `requirements.txt`.

**Root Cause**: Your current `requirements.txt` includes:
- Development tools (pytest, black, mypy, debugpy, flake8, isort)
- Beta packages (opentelemetry-instrumentation-fastapi>=0.42b0)
- Testing dependencies

These cause `uv` to fail during installation in Orchestrate.

**Solution: Use a minimal requirements.txt for Orchestrate deployment**

```bash
cd /path/to/grc-mcp-server

# Create a deployment-specific requirements file
cat > requirements-orchestrate.txt << 'EOF'
# Minimal requirements for Orchestrate deployment
# Core dependencies only - no dev/test tools

# Core API framework
fastapi>=0.104.0
uvicorn>=0.24.0
httpx>=0.24.0

# Data validation
pydantic>=2.5.0
pydantic-settings>=2.1.0

# MCP protocol
mcp>=1.9.4

# Environment configuration
python-dotenv>=1.0.0

# Observability - Metrics only (optional)
prometheus-client>=0.19.0
EOF

# Create deployment directory with minimal requirements
mkdir -p deployment
cp main.py deployment/
cp requirements-orchestrate.txt deployment/requirements.txt
cp -r src deployment/

# Deploy with the clean requirements
orchestrate toolkits add \
    --kind mcp \
    --name openpages-grc \
    --description "IBM OpenPages GRC integration - API key auth" \
    --command "python main.py --mode local" \
    --package-root "./deployment" \
    --language python \
    --tools "*" \
    --app-id openpages-grc
EOF

# Solution 2: Test requirements.txt locally with uv
# Install uv if not already installed
pip install uv

# Test if uv can install your dependencies
uv pip install -r requirements-orchestrate.txt

# If it fails locally, you'll see the actual error message
# Fix the requirements.txt until it works locally

# Solution 2b: Try even more minimal requirements
# If still failing, try removing packages one by one
cat > requirements-minimal.txt << 'EOF'
mcp>=1.9.4
httpx>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
EOF

# Test this minimal set
uv pip install -r requirements-minimal.txt

# Solution 3: Remove version constraints that might cause issues
# Change from:
#   package==1.2.3
# To:
#   package>=1.2.0

# Solution 4: Remove optional/development dependencies
# Remove these if present:
# - pytest, pytest-asyncio (testing)
# - black, isort, flake8, mypy (development tools)
# - debugpy (debugging)

# Solution 5: After fixing requirements.txt, try again
orchestrate toolkits add \
    --kind mcp \
    --name openpages-grc \
    --description "IBM OpenPages GRC integration" \
    --command "python main.py --mode local" \
    --package-root "./deployment" \
    --language python \
    --tools "*" \
    --app-id openpages-grc
```

**Critical Finding: If uv works locally but fails in Orchestrate**

If `uv pip install -r requirements-orchestrate.txt` succeeds locally (showing "Audited X packages") but fails in Orchestrate, this indicates an **environment issue in Orchestrate**, not a problem with your requirements.txt.

**Possible causes:**
1. **Python version mismatch**: Your local uses Python 3.11, but Orchestrate might use a different version
2. **Network restrictions**: Orchestrate's environment can't reach PyPI or package repositories
3. **Missing system dependencies**: Some packages need system libraries that aren't available in Orchestrate
4. **Orchestrate configuration issue**: The toolkit deployment environment isn't properly configured

**Solutions:**

```bash
# Solution 1: Specify Python version explicitly (if supported)
orchestrate toolkits add \
    --kind mcp \
    --name openpages-grc \
    --description "IBM OpenPages GRC integration" \
    --command "python main.py --mode local" \
    --package-root "./deployment" \
    --language python \
    --python-version "3.11" \
    --tools "*" \
    --app-id openpages-grc

# Solution 2: Contact IBM Orchestrate Support
# Since uv works locally but fails in Orchestrate, this is likely an Orchestrate platform issue
# Provide them with:
# 1. Your working requirements-orchestrate.txt
# 2. Proof that uv pip install works locally
# 3. The full error message from Orchestrate
# 4. Request they check:
#    - Python version in their toolkit deployment environment
#    - Network access to PyPI
#    - System dependencies available
#    - uv configuration in their environment

# Solution 3: Try the pipx method (bypasses uv install)
# This requires publishing your package to PyPI or a private repository first
# See the pipx deployment section above
```

**Recommended Next Steps:**
1. Contact IBM Orchestrate support - this appears to be a platform configuration issue
2. Ask if there are any known issues with Python package installation in toolkits
3. Request documentation on their toolkit deployment environment specifications
4. Consider using the pipx deployment method as an alternative

**Minimal Working requirements.txt for Orchestrate:**

```txt
# Absolute minimum for MCP server to work
mcp>=1.9.4
httpx>=0.24.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
```

**Note**: If FastAPI/Uvicorn are causing issues, you can remove them since the MCP server runs in local/stdio mode and doesn't need the HTTP server components for Orchestrate deployment.

**Issue: "Server Error 500" during toolkit upload (package issues)**

If you still get 500 errors after fixing dependencies:

```bash
# Clean up the package directory
cd /path/to/grc-mcp-server

# Remove unnecessary files
rm -rf .git .pytest_cache __pycache__ *.pyc
rm -rf .venv venv env
rm -rf .vscode .idea
rm -rf tests/ docs/ monitoring/ nginx/ scripts/
rm -rf *.log .env .env.*

# Create a minimal deployment directory
mkdir -p deployment
cp main.py deployment/
cp requirements.txt deployment/
cp -r src deployment/

# Verify the structure
tree deployment/
# Should show:
# deployment/
# ├── main.py
# ├── requirements.txt
# └── src/
#     └── app/
#         ├── __init__.py
#         ├── config/
#         ├── core/
#         ├── mcp/
#         ├── observability/
#         └── tools/

# Try with the clean deployment directory
orchestrate toolkits add \
    --kind mcp \
    --name openpages-grc \
    --description "IBM OpenPages GRC integration" \
    --command "python main.py --mode local" \
    --package-root "./deployment" \
    --language python \
    --tools "*" \
    --app-id openpages-grc
```

**Issue: "Rate limit exceeded"**
```bash
# Check OpenPages API rate limits
# Adjust rate limiting in connection settings
orchestrate connections set-credentials \
    -a openpages-grc \
    --env draft \
    -e "RATE_LIMIT_REQUESTS_PER_MINUTE=30"

# Monitor API usage in CloudWatch
aws cloudwatch get-metric-statistics \
    --namespace Orchestrate/Toolkits \
    --metric-name APICallCount \
    --dimensions Name=ToolkitName,Value=openpages-grc
```

## Security Best Practices for AWS Deployment

1. **Use AWS Secrets Manager**: Orchestrate automatically stores API keys in AWS Secrets Manager with encryption at rest
2. **Enable API Key Rotation**:
   - Set up automatic rotation in OpenPages
   - Update Orchestrate connections when keys rotate
   - Use AWS Lambda for automated rotation workflows
3. **Separate Environments**: Maintain distinct API keys for draft, live, and production
4. **Least Privilege IAM**:
   - Use IAM roles with minimal required permissions
   - Restrict access to Secrets Manager
   - Enable MFA for sensitive operations
5. **Network Security**:
   - Use VPC peering for private OpenPages instances
   - Configure security groups to restrict access
   - Enable VPC Flow Logs for network monitoring
6. **Audit Logging**:
   - Enable CloudTrail for all Orchestrate operations
   - Enable OpenPages audit logging
   - Monitor API key usage in CloudWatch
7. **SSL/TLS**:
   - Always use HTTPS for OpenPages connections
   - Verify SSL certificates (`SSL_VERIFY=True`)
   - Use AWS Certificate Manager for certificate management
8. **API Key Management**:
   - Never commit API keys to source control
   - Use different keys for each environment
   - Monitor for unauthorized key usage
   - Implement key expiration policies
9. **Compliance**:
   - Ensure deployment meets your organization's compliance requirements
   - Use AWS Config for compliance monitoring
   - Enable AWS GuardDuty for threat detection

## Updating the Toolkit

When you update your MCP server code:

```bash
# 1. Pull latest changes
cd /path/to/grc-mcp-server
git pull

# 2. Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# 3. Restart the toolkit in Orchestrate
orchestrate toolkits restart --name openpages-grc

# Or update the toolkit configuration if needed
orchestrate toolkits update \
    --name openpages-grc \
    --description "Updated description" \
    --command "/path/to/updated/command"
```

## Complete AWS Deployment Script

Here's a complete script to automate the deployment to AWS:

```bash
#!/bin/bash
# deploy_to_orchestrate_aws.sh

set -e  # Exit on error

# Configuration
APP_NAME="openpages-grc"
SERVER_PATH="/path/to/grc-mcp-server"
ENVIRONMENTS=("draft" "live")
AWS_REGION="us-east-1"

echo "=========================================="
echo "Deploying OpenPages MCP Server to Orchestrate on AWS"
echo "=========================================="

# Step 1: Verify AWS credentials
echo "Verifying AWS credentials..."
aws sts get-caller-identity || { echo "AWS credentials not configured"; exit 1; }

# Step 2: Create connection
echo "Creating Orchestrate connection..."
orchestrate connections add -a $APP_NAME || echo "Connection already exists"

# Step 3: Configure environments with API keys
for env in "${ENVIRONMENTS[@]}"; do
    echo ""
    echo "Configuring environment: $env"
    echo "----------------------------------------"
    
    orchestrate connections configure \
        -a $APP_NAME \
        --env $env \
        --type team \
        --kind key_value
    
    # Prompt for API key credentials
    read -p "Enter OPENPAGES_BASE_URL for $env (e.g., https://openpages-$env.aws.com): " base_url
    read -p "Enter OPENPAGES_AUTHENTICATION_URL for $env (e.g., $base_url/api/auth): " auth_url
    read -sp "Enter OPENPAGES_APIKEY for $env: " api_key
    echo
    
    # Set credentials (stored in AWS Secrets Manager)
    echo "Storing credentials in AWS Secrets Manager..."
    orchestrate connections set-credentials \
        -a $APP_NAME \
        --env $env \
        -e "OPENPAGES_BASE_URL=$base_url" \
        -e "OPENPAGES_AUTHENTICATION_TYPE=bearer" \
        -e "OPENPAGES_APIKEY=$api_key" \
        -e "OPENPAGES_AUTHENTICATION_URL=$auth_url" \
        -e "SSL_VERIFY=True" \
        -e "LOG_LEVEL=INFO"
    
    echo "✓ Environment $env configured"
done

# Step 4: Package the MCP server
echo ""
echo "Packaging MCP server..."
cd $SERVER_PATH
zip -r openpages-mcp-server.zip main.py src/ requirements.txt -x "*.pyc" -x "__pycache__/*" -x ".git/*"
echo "✓ Package created: openpages-mcp-server.zip"

# Step 5: Register toolkit
echo ""
echo "Registering MCP toolkit in Orchestrate..."
orchestrate toolkits add \
    --kind mcp \
    --name $APP_NAME \
    --description "IBM OpenPages GRC on AWS - API key authentication" \
    --command "python main.py --mode local" \
    --package-root "$SERVER_PATH" \
    --language python \
    --tools "*" \
    --app-id $APP_NAME

echo ""
echo "=========================================="
echo "✓ Deployment complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Verify deployment: orchestrate toolkits get --name $APP_NAME"
echo "2. Test connection: orchestrate connections test -a $APP_NAME --env draft"
echo "3. View logs: orchestrate toolkits logs --name $APP_NAME --env draft"
echo "4. Monitor in CloudWatch: aws logs tail /aws/orchestrate/$APP_NAME --follow"
echo ""
```

### Usage

```bash
# Make the script executable
chmod +x deploy_to_orchestrate_aws.sh

# Run the deployment
./deploy_to_orchestrate_aws.sh
```

## Using the Toolkit in Orchestrate

Once deployed, AI agents can use your OpenPages tools:

```javascript
// Example: Query OpenPages issues
const result = await orchestrate.callTool({
    toolkit: "openpages-grc",
    tool: "openpages_query_issues",
    environment: "draft",
    parameters: {
        filters: {
            "Status": "Open"
        },
        limit: 10
    }
});

// Example: Create a new control
const control = await orchestrate.callTool({
    toolkit: "openpages-grc",
    tool: "openpages_upsert_control",
    environment: "live",
    parameters: {
        name: "Access Control Policy",
        description: "Ensure proper access controls are in place",
        fields: {
            "Status": "Active",
            "Type": "Preventive"
        }
    }
});
```

## Comparison: Local vs AWS Orchestrate Deployment

| Aspect | Local Deployment | AWS Orchestrate Deployment |
|--------|------------------|----------------------------|
| **Access** | Single user | Team-wide across organization |
| **Credentials** | Local .env file | AWS Secrets Manager |
| **Authentication** | Basic or API key | API key (bearer token) |
| **Environments** | Manual switching | Environment selection via CLI |
| **Monitoring** | Local logs | CloudWatch Logs & Metrics |
| **Scaling** | Single instance | Auto-scaling via AWS |
| **Integration** | Direct MCP | Orchestrate workflows + AWS services |
| **Security** | User-managed | AWS-managed (IAM, KMS, GuardDuty) |
| **Infrastructure** | Local machine | AWS Lambda/ECS/Fargate |
| **Cost** | Free (local resources) | AWS + Orchestrate subscription |
| **Availability** | Depends on local machine | High availability (AWS SLA) |
| **Backup** | Manual | Automated (AWS backups) |
| **Compliance** | User responsibility | AWS compliance certifications |

## Next Steps

1. **Test Thoroughly**: Test all tools in draft environment before using in live
2. **Document Usage**: Create internal documentation for your team
3. **Set Up Monitoring**: Configure alerts for failures or errors
4. **Create Workflows**: Build Orchestrate workflows that use your OpenPages tools
5. **Train Users**: Educate team members on available tools and best practices

## AWS Cost Optimization

### Estimating Costs

```bash
# Monitor AWS costs for Orchestrate
aws ce get-cost-and-usage \
    --time-period Start=2024-01-01,End=2024-01-31 \
    --granularity MONTHLY \
    --metrics BlendedCost \
    --filter file://orchestrate-filter.json

# Set up cost alerts
aws budgets create-budget \
    --account-id <account-id> \
    --budget file://orchestrate-budget.json
```

### Cost Optimization Tips

1. **Right-size compute resources**: Choose appropriate Lambda memory/timeout or ECS task size
2. **Use reserved capacity**: For predictable workloads, use AWS Savings Plans
3. **Optimize API calls**: Implement caching to reduce OpenPages API calls
4. **Monitor CloudWatch costs**: Set retention policies for logs
5. **Use AWS Cost Explorer**: Analyze spending patterns and optimize

## Additional Resources

### Documentation
- [MCP Protocol Specification](https://modelcontextprotocol.io)
- [IBM Orchestrate on AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-orchestrate)
- [OpenPages on AWS Marketplace](https://aws.amazon.com/marketplace/pp/prodview-openpages)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [AWS CloudWatch Documentation](https://docs.aws.amazon.com/cloudwatch/)
- Project README: `../README.md`
- Deployment Architecture: `./DEPLOYMENT_ARCHITECTURE.md`

### AWS Services Used
- **AWS Secrets Manager**: Secure credential storage
- **AWS CloudWatch**: Logging and monitoring
- **AWS Lambda or ECS**: Compute execution
- **AWS IAM**: Access control
- **AWS VPC**: Network isolation (optional)
- **AWS Certificate Manager**: SSL/TLS certificates

## Support

For issues or questions:

1. **Check troubleshooting section** above for common issues
2. **Review CloudWatch logs**:
   ```bash
   aws logs tail /aws/orchestrate/openpages-grc --follow
   ```
3. **Test locally first** with API key:
   ```bash
   python main.py --mode local --env-file .env.test
   ```
4. **Contact support**:
   - Orchestrate issues: IBM Orchestrate support
   - OpenPages issues: OpenPages support team
   - AWS infrastructure: AWS Support
   - MCP server code: Your development team

## Deployment Checklist

- [ ] AWS account configured with appropriate permissions
- [ ] Orchestrate subscription active on AWS Marketplace
- [ ] OpenPages API keys obtained for all environments
- [ ] MCP server tested locally with API key authentication
- [ ] Orchestrate CLI installed and configured
- [ ] Connections created for all environments
- [ ] API keys stored in AWS Secrets Manager via Orchestrate
- [ ] Toolkit registered and deployed
- [ ] Deployment verified with test queries
- [ ] CloudWatch logging configured
- [ ] Cost monitoring and alerts set up
- [ ] Security groups and network access configured
- [ ] Team members granted appropriate IAM permissions
- [ ] Documentation updated with environment-specific details
- [ ] Runbook created for common operations

---

**Note**: This guide is specifically for deploying to IBM Orchestrate on AWS Marketplace with API key authentication. Ensure you have:
- Appropriate AWS IAM permissions
- Valid Orchestrate subscription
- OpenPages API keys for each environment
- Coordination with your IT, security, and cloud teams for production deployments
</content>
<line_count>485</line_count>