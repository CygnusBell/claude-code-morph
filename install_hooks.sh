#!/bin/bash
# Install git hooks for Claude Code Morph

echo "Installing Git hooks..."

# Create .git/hooks directory if it doesn't exist
mkdir -p .git/hooks

# Copy pre-push hook
if [ -f .githooks/pre-push ]; then
    cp .githooks/pre-push .git/hooks/pre-push
    chmod +x .git/hooks/pre-push
    echo "✓ Installed pre-push hook"
else
    echo "❌ pre-push hook not found in .githooks/"
    exit 1
fi

# Optional: Install pre-commit hook
if [ -f .githooks/pre-commit ]; then
    cp .githooks/pre-commit .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit
    echo "✓ Installed pre-commit hook"
fi

echo ""
echo "Git hooks installed successfully!"
echo ""
echo "The pre-push hook will:"
echo "  - Run smoke tests (fast)"
echo "  - Run integration tests (if pytest installed)"
echo "  - Check for Python syntax errors"
echo "  - Warn about print statements"
echo ""
echo "To skip hooks temporarily, use: git push --no-verify"
echo "To uninstall: rm .git/hooks/pre-push"