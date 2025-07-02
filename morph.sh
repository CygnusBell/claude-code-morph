#!/bin/bash
# Run morph with automatic venv activation

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate the virtual environment
if [[ -d "$SCRIPT_DIR/venv" ]]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "Error: Virtual environment not found at $SCRIPT_DIR/venv"
    exit 1
fi

# Run morph with all arguments passed through
echo "Starting Claude Code Morph..."
morph "$@"