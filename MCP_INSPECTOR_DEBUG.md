# Debugging with MCP Inspector

This guide explains how to debug the local MCP server while using the MCP Inspector tool.

> **IMPORTANT NOTE**: Due to persistent issues with VSCode's debugpy integration, we strongly recommend using the all-in-one shell scripts (`run_mcp_with_inspector.sh`/`.bat`) for the most reliable experience. These scripts don't require debugpy and work consistently across environments.

## Setup

1. The project has been configured with VSCode debug configurations and scripts to facilitate debugging with the MCP Inspector tool.

2. For the most reliable approach that allows VSCode breakpoints, run the setup script:

   ```bash
   python setup_vscode_debug.py
   ```

   This script will:
   - Find or install debugpy
   - Configure VSCode settings to use the correct debugpy path
   - Create a debug server script that works with the MCP Inspector

3. Alternatively, you can install debugpy manually in several ways:

   a. Run the "Install debugpy" debug configuration in VSCode:
      - Go to the "Run and Debug" view (Ctrl+Shift+D or Cmd+Shift+D on macOS)
      - Select "Install debugpy" from the dropdown
      - Press F5 to run it

   b. Run the install script directly:
      ```bash
      python install_debugpy.py
      ```

   c. Install via pip:
      ```bash
      pip install debugpy
      ```

   d. Update all requirements:
      ```bash
      pip install -r requirements.txt
      ```

## Using the Debug Scripts

### On Linux/macOS:

```bash
./debug_mcp_for_inspector.sh
```

### On Windows:

```cmd
debug_mcp_for_inspector.bat
```

These scripts will start the local MCP server in debug mode with the appropriate environment variables set.

## Using VSCode Debugging with Breakpoints

### Option 1: Using the Setup Script (RECOMMENDED FOR DEBUGGING)

This approach allows you to use VSCode breakpoints while working with the MCP Inspector:

1. Run the setup script to configure VSCode and create the debug server script:
   ```bash
   python setup_vscode_debug.py
   ```

2. Set breakpoints in your code using VSCode (e.g., in `src/app/local_mcp/local_mcp_server.py`)

3. Run the debug server script from the terminal (NOT by pressing F5):
   ```bash
   python debug_server_for_vscode.py
   ```
   This starts the server in debug mode and keeps it running.

4. In a separate terminal, run the MCP Inspector:
   ```bash
   npx @modelcontextprotocol/inspector
   ```

5. When the MCP Inspector connects to the server, your breakpoints will be hit when that code executes.

**Important Notes:**
- You do NOT need to press F5 in VSCode - the debug server script handles starting the server in debug mode
- VSCode will automatically attach to the debug session when a breakpoint is hit
- You can use all VSCode debugging features (step through, inspect variables, etc.)
- This approach works reliably across different environments

## Using with MCP Inspector

### Option 2: All-in-One Script (RECOMMENDED FOR QUICK TESTING)

We've created all-in-one scripts that run both the server and the MCP Inspector together without requiring debugpy:

#### On Linux/macOS:

```bash
./run_mcp_with_inspector.sh
```

#### On Windows:

```cmd
run_mcp_with_inspector.bat
```

These scripts will:
1. Set up the virtual environment if needed
2. Start the MCP server in debug mode
3. Run the MCP Inspector
4. Clean up when you're done

### Option 2: Separate Scripts

If you prefer to run the server and inspector separately:

#### On Linux/macOS:

```bash
./run_mcp_inspector.sh
```

#### On Windows:

```cmd
run_mcp_inspector.bat
```

These scripts will:
1. Check if debugpy is installed and install it if needed
2. Run the MCP Inspector tool

Alternatively, you can manually run the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
```

The inspector will connect to your local MCP server, and you'll be able to:
- Set breakpoints in the code
- Step through the execution
- Inspect variables
- Debug any issues that arise

## Understanding the Different Approaches

### Three Ways to Debug

- **Setup Script + Debug Server (RECOMMENDED FOR DEBUGGING)**:
  - Uses `setup_vscode_debug.py` and `debug_server_for_vscode.py`
  - Allows setting breakpoints and using VSCode's debugging features
  - Properly configures VSCode to find debugpy
  - Requires running the MCP Inspector in a separate terminal
  - Best approach for debugging with breakpoints

- **Shell Scripts (`run_mcp_with_inspector.sh/.bat`) [RECOMMENDED FOR QUICK TESTING]**:
  - Run both the server and inspector in one command
  - Don't require VSCode's debugging features
  - Don't require debugpy
  - Work consistently across environments
  - Most reliable approach for running the MCP Inspector
  - **Note**: You won't be able to set breakpoints or use VSCode's debug features with this approach

- **VSCode Debugging ("Debug MCP with Inspector (All-in-One)")**:
  - Provides full VSCode debugging capabilities when working
  - Allows setting breakpoints, stepping through code, etc.
  - Launches both the server and inspector
  - Requires debugpy to be installed correctly
  - May encounter persistent "could not find debugpy path" errors
  - Not recommended due to reliability issues

Choose the approach that best fits your needs:
- For debugging with breakpoints: Use the Setup Script + Debug Server approach
- For reliable operation without debugging: Use the shell scripts

## Debugging Tips

1. Set breakpoints in `src/app/local_mcp/local_mcp_server.py` to debug the server's behavior
2. The `--debug` flag enables more verbose logging
3. The `MCP_DEBUG` environment variable is set to `true` to enable additional debug features

## Troubleshooting

If you encounter issues:

1. Make sure the server is running before starting the MCP Inspector
2. Check the console output for any error messages
3. Verify that the correct ports are being used (the MCP Inspector uses the standard input/output for communication)

### Common Errors

#### "Could not find debugpy path"

This error occurs when the debugpy package is not installed or not found in the Python path. To fix it:

1. Run the "Install debugpy" debug configuration in VSCode:
   - Go to the "Run and Debug" view (Ctrl+Shift+D or Cmd+Shift+D on macOS)
   - Select "Install debugpy" from the dropdown
   - Press F5 to run it

2. Run the install script directly:
   ```bash
   python install_debugpy.py
   ```

3. Check which Python interpreter VSCode is using:
   - Open the Command Palette (Ctrl+Shift+P or Cmd+Shift+P on macOS)
   - Type "Python: Select Interpreter" and select it
   - Make sure you're using the interpreter where debugpy is installed

4. If you're using a virtual environment, make sure it's activated:
   ```bash
   # For Linux/macOS
   source venv/bin/activate  # Replace 'venv' with your virtual environment name

   # For Windows
   .\venv\Scripts\activate  # Replace 'venv' with your virtual environment name
   ```

5. Use our provided scripts which handle debugpy installation automatically:
   ```bash
   # For Linux/macOS
   ./run_mcp_inspector.sh

   # For Windows
   run_mcp_inspector.bat
   ```

6. If the error persists, try installing debugpy globally:
   ```bash
   pip install debugpy --user
   ```

7. If all else fails, use the all-in-one scripts which don't require debugpy:
   ```bash
   # For Linux/macOS
   ./run_mcp_with_inspector.sh

   # For Windows
   run_mcp_with_inspector.bat
   ```

#### Connection Issues

If the MCP Inspector cannot connect to your server:

1. Make sure the server is running and listening on the correct port
2. Check for any firewall or network issues
3. Verify that the server is not crashing during startup (check the console output)