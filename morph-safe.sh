#!/bin/bash
# Safe mode launcher for Claude Code Morph

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

# Run the safe mode repair script
echo "Starting Claude Code Morph in SAFE MODE..."
python "$SCRIPT_DIR/safe_mode.py" "$@"