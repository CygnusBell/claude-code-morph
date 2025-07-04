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
echo "Python version: $(python --version)"

# Quick dependency check
if python -c "import chromadb" 2>/dev/null; then
    echo "✓ Context dependencies available"
else
    echo "⚠ Context dependencies not found - run: pip install -e .[context]"
fi

# Run the application
exec python -m claude_code_morph "$@"