#!/usr/bin/env python3
"""
Setup VSCode debugging environment for MCP Inspector
This script helps set up the environment for VSCode debugging with the MCP Inspector
"""

import os
import sys
import subprocess
import site
import shutil

def find_debugpy():
    """Find debugpy in the Python path"""
    try:
        import debugpy
        print(f"Found debugpy at: {debugpy.__file__}")
        debugpy_dir = os.path.dirname(os.path.dirname(debugpy.__file__))
        print(f"debugpy directory: {debugpy_dir}")
        return debugpy_dir
    except ImportError:
        print("debugpy not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "debugpy"])
            import debugpy
            print(f"Installed debugpy at: {debugpy.__file__}")
            debugpy_dir = os.path.dirname(os.path.dirname(debugpy.__file__))
            print(f"debugpy directory: {debugpy_dir}")
            return debugpy_dir
        except Exception as e:
            print(f"Error installing debugpy: {e}")
            return None

def update_vscode_settings(debugpy_path):
    """Update VSCode settings to include debugpy path"""
    vscode_dir = os.path.join(os.getcwd(), ".vscode")
    settings_file = os.path.join(vscode_dir, "settings.json")
    
    # Create .vscode directory if it doesn't exist
    if not os.path.exists(vscode_dir):
        os.makedirs(vscode_dir)
    
    # Create or update settings.json
    settings = {}
    if os.path.exists(settings_file):
        try:
            import json
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        except Exception as e:
            print(f"Error reading settings.json: {e}")
    
    # Update Python path settings
    if "python.analysis.extraPaths" not in settings:
        settings["python.analysis.extraPaths"] = []
    
    if debugpy_path not in settings["python.analysis.extraPaths"]:
        settings["python.analysis.extraPaths"].append(debugpy_path)
    
    # Update debugpy path
    settings["python.debugpy.path"] = os.path.join(debugpy_path, "debugpy")
    
    # Write settings back to file
    try:
        import json
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=4)
        print(f"Updated VSCode settings in {settings_file}")
    except Exception as e:
        print(f"Error writing settings.json: {e}")

def create_debug_script():
    """Create a script to run the server in debug mode"""
    script_content = """#!/usr/bin/env python3
import os
import sys
import subprocess
import time

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Set environment variables for debugging
os.environ["MCP_DEBUG"] = "true"
os.environ["PYTHONPATH"] = script_dir

# Start the MCP server in debug mode
server_process = subprocess.Popen(
    [sys.executable, os.path.join(script_dir, "src", "app", "local_mcp", "run_local_mcp.py"), "--debug"],
    env=os.environ
)

print("MCP server started. Now you can:")
print("1. Set breakpoints in VSCode")
print("2. Run the MCP Inspector in a separate terminal:")
print("   npx @modelcontextprotocol/inspector")
print("Press Ctrl+C to stop the server")

try:
    # Keep the script running
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping server...")
    server_process.terminate()
    server_process.wait()
    print("Server stopped")
"""
    
    script_path = os.path.join(os.getcwd(), "debug_server_for_vscode.py")
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    # Make the script executable
    os.chmod(script_path, 0o755)
    print(f"Created debug script at {script_path}")

def main():
    """Main function"""
    print("Setting up VSCode debugging environment for MCP Inspector...")
    
    # Find debugpy
    debugpy_path = find_debugpy()
    if not debugpy_path:
        print("Failed to find or install debugpy.")
        return False
    
    # Update VSCode settings
    update_vscode_settings(debugpy_path)
    
    # Create debug script
    create_debug_script()
    
    print("\nSetup complete!")
    print("\nTo debug with VSCode and MCP Inspector:")
    print("1. Run the debug server script:")
    print("   python debug_server_for_vscode.py")
    print("2. Set breakpoints in VSCode")
    print("3. In a separate terminal, run the MCP Inspector:")
    print("   npx @modelcontextprotocol/inspector")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)

# Made with Bob
