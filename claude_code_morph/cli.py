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
    morph_package_dir = Path(__file__).parent  # This is claude_code_morph/
    
    # The source directory is always the package directory
    morph_source_dir = morph_package_dir
    
    # Allow override
    if args.morph_dir:
        morph_source_dir = Path(args.morph_dir).absolute()
    
    # Set environment variable so main.py knows where morph source is
    os.environ["MORPH_SOURCE_DIR"] = str(morph_source_dir)
    
    # Debug: Print paths
    print(f"Morph source directory: {morph_source_dir}")
    print(f"Panels directory would be: {morph_source_dir / 'panels'}")
    
    # Set working directory
    if args.cwd:
        os.chdir(args.cwd)
    # else: stay in current directory
    
    # Store the user's working directory
    os.environ["MORPH_USER_CWD"] = os.getcwd()
    
    # Import and run the main app
    # Add parent directory to path so we can import claude_code_morph
    sys.path.insert(0, str(morph_source_dir.parent))
    
    # Import after path is set
    from claude_code_morph.main import main as run_app
    
    # Run the app
    run_app()

if __name__ == "__main__":
    main()