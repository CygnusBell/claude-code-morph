#!/bin/bash
# Quick setup script for Claude Code Morph

echo "Claude Code Morph Setup"
echo "====================="

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    # Check for existing venvs
    if [ -d "venv" ]; then
        echo "Found existing venv. Activating..."
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        echo "Found existing .venv. Activating..."
        source .venv/bin/activate
    else
        echo "No virtual environment found. Creating one..."
        python3 -m venv venv
        source venv/bin/activate
    fi
else
    echo "Already in virtual environment: $VIRTUAL_ENV"
fi

echo ""
echo "Using Python: $(which python)"
echo "Python version: $(python --version)"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install the package
echo ""
echo "Installing Claude Code Morph..."
pip install -e .

# Ask about optional features
echo ""
echo "Do you want to install optional features?"
echo "1) Minimal (core features only)"
echo "2) Context (adds ChromaDB, sentence-transformers)"
echo "3) AI (adds Groq, OpenAI, Anthropic clients)"
echo "4) All (everything)"
echo ""
read -p "Choice [1-4, default=1]: " choice

case $choice in
    2)
        echo "Installing context features..."
        pip install -e ".[context]"
        ;;
    3)
        echo "Installing AI features..."
        pip install -e ".[ai]"
        ;;
    4)
        echo "Installing all features..."
        pip install -e ".[all]"
        ;;
    *)
        echo "Using minimal installation."
        ;;
esac

# Run diagnostics
echo ""
echo "Running diagnostics..."
python check_context_deps.py

echo ""
echo "Setup complete!"
echo ""
echo "To run Claude Code Morph:"
echo "  ./run_morph.sh"
echo ""
echo "Or activate the venv manually:"
echo "  source venv/bin/activate"
echo "  python -m claude_code_morph"