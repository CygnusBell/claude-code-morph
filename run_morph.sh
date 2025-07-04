#!/bin/bash
# Disable bracketed paste mode and run morph

# Disable bracketed paste mode
printf '\e[?2004l'

# Source virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "No virtual environment found! Please create one with:"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -e .[all]"
    exit 1
fi

# Show which Python we're using
echo "Using Python: $(which python)"

# Run the application
exec python -m claude_code_morph "$@"