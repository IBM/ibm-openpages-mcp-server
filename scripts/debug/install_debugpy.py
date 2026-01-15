#!/usr/bin/env python3
"""
Install debugpy into the current Python environment
This script is used to ensure debugpy is installed for VSCode debugging
"""

import subprocess
import sys
import os

def main():
    """Install debugpy if not already installed"""
    print("Checking for debugpy...")
    
    try:
        import debugpy
        print(f"debugpy is already installed at: {debugpy.__file__}")
        print(f"debugpy version: {debugpy.__version__}")
        return True
    except ImportError:
        print("debugpy not found. Installing...")
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "debugpy"])
            print("debugpy installed successfully!")
            
            # Verify installation
            import debugpy
            print(f"debugpy installed at: {debugpy.__file__}")
            print(f"debugpy version: {debugpy.__version__}")
            return True
        except Exception as e:
            print(f"Error installing debugpy: {e}")
            return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)

# Made with Bob
