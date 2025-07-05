#!/bin/bash
# Run tests for Claude Code Morph

echo "Claude Code Morph Test Runner"
echo "============================"

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    # Try to activate venv
    if [ -d "venv" ]; then
        echo "Activating virtual environment..."
        source venv/bin/activate
    elif [ -d ".venv" ]; then
        echo "Activating .venv..."
        source .venv/bin/activate
    fi
fi

echo "Using Python: $(which python)"
echo ""

# Install test dependencies if needed
if ! python -c "import pytest" 2>/dev/null; then
    echo "Installing pytest..."
    pip install pytest pytest-asyncio
fi

# Run tests with different levels of detail
if [ "$1" == "-v" ] || [ "$1" == "--verbose" ]; then
    # Verbose mode
    python -m pytest tests/ -v --tb=short
elif [ "$1" == "-vv" ]; then
    # Very verbose mode
    python -m pytest tests/ -vv
elif [ "$1" == "--quick" ]; then
    # Quick smoke test - just the critical tests
    python -m pytest tests/test_integration.py::TestAppStartup -v
else
    # Normal mode - show dots progress
    echo "Running tests..."
    python -m pytest tests/
fi

# Show coverage if requested
if [ "$1" == "--coverage" ]; then
    echo ""
    echo "Running with coverage..."
    pip install coverage > /dev/null 2>&1
    coverage run -m pytest tests/
    coverage report -m
fi