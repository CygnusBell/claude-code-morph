#!/usr/bin/env python3
"""Safe runner for Claude Code Morph that handles terminal issues."""

import os
import sys

# Disable bracketed paste mode
sys.stdout.write('\033[?2004l')
sys.stdout.flush()

# Set terminal to a safe mode
os.environ['TERM'] = 'xterm-256color'

# Remove any problematic environment variables
if 'SSH_CONNECTION' in os.environ:
    # We're in SSH, might need special handling
    pass

# Import and run the main app
from claude_code_morph.main import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting Claude Code Morph...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError running Claude Code Morph: {e}")
        print("\nTry running with: python -m claude_code_morph")
        sys.exit(1)