#!/bin/bash
# Disable bracketed paste mode and run morph

# Disable bracketed paste mode
printf '\e[?2004l'

# Source virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the application
exec python -m claude_code_morph "$@"