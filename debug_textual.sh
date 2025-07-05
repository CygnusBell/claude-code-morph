#!/bin/bash
# Run morph with Textual debugging enabled

# Disable bracketed paste mode
printf '\e[?2004l'

# Source virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Run with textual logging
export TEXTUAL_LOG="logs/textual_debug.log"
export TEXTUAL_LOG_LEVEL="DEBUG"

# Also capture stderr to a file
python -m claude_code_morph 2> logs/stderr.log

echo "Check logs/textual_debug.log and logs/stderr.log for debugging info"