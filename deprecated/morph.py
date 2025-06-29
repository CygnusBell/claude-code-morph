#!/usr/bin/env python3
"""
Claude Code Morph Launcher
Cross-platform launcher that automatically handles virtual environment setup.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def main():
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # Determine venv paths based on OS
    venv_dir = script_dir / "venv"
    if platform.system() == "Windows":
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
    
    # Create virtual environment if it doesn't exist
    if not venv_dir.exists():
        print("🔧 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
    
    # Check if dependencies are installed
    try:
        subprocess.run(
            [str(python_exe), "-c", "import textual"],
            check=True,
            capture_output=True
        )
    except subprocess.CalledProcessError:
        print("📦 Installing dependencies...")
        subprocess.run([str(pip_exe), "install", "-r", "requirements.txt"], check=True)
    
    # Launch the application
    print("🚀 Starting Claude Code Morph...")
    os.execv(str(python_exe), [str(python_exe), "main.py"] + sys.argv[1:])

if __name__ == "__main__":
    main()