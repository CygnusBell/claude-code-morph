#!/usr/bin/env python3
"""CLI entry point for Claude Code Morph."""

import os
import sys
import argparse
from pathlib import Path

def main():
    """Main entry point for the morph command."""
    parser = argparse.ArgumentParser(description="Claude Code Morph - Self-editable IDE")
    parser.add_argument("--cwd", help="Working directory (defaults to current directory)")
    parser.add_argument("--morph-dir", help="Override morph source directory")
    args = parser.parse_args()
    
    # Determine the morph source directory
    # When installed via pip, __file__ will be in site-packages
    morph_package_dir = Path(__file__).parent
    morph_source_dir = morph_package_dir.parent  # Go up to the installed package root
    
    # Check if we're running from source (development mode)
    if (morph_source_dir / "main.py").exists():
        # Running from source
        pass
    else:
        # Installed via pip - main.py should be in the package
        morph_source_dir = morph_package_dir
    
    # Allow override
    if args.morph_dir:
        morph_source_dir = Path(args.morph_dir).absolute()
    
    # Set environment variable so main.py knows where morph source is
    os.environ["MORPH_SOURCE_DIR"] = str(morph_source_dir)
    
    # Set working directory
    if args.cwd:
        os.chdir(args.cwd)
    # else: stay in current directory
    
    # Store the user's working directory
    os.environ["MORPH_USER_CWD"] = os.getcwd()
    
    # Import and run the main app
    sys.path.insert(0, str(morph_source_dir))
    
    # Import after path is set
    from main import main as run_app
    
    # Run the app
    run_app()

if __name__ == "__main__":
    main()