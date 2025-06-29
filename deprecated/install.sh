#!/bin/bash
# Quick installer for Claude Code Morph

set -e

echo "🚀 Claude Code Morph Quick Installer"
echo "===================================="
echo ""

# Check if in virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✓ Virtual environment detected: $VIRTUAL_ENV"
    echo ""
    echo "Installing claude-code-morph..."
    pip install -e .
    echo ""
    echo "✅ Installation complete! You can now run: morph"
else
    echo "⚠️  No virtual environment detected."
    echo ""
    echo "It's recommended to install in a virtual environment:"
    echo ""
    echo "  python -m venv venv"
    echo "  source venv/bin/activate  # On Windows: venv\\Scripts\\activate"
    echo "  pip install -e ."
    echo ""
    echo "Or use the included launcher that manages its own venv:"
    echo "  ./morph"
fi