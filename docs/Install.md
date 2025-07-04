# Claude Code Morph - Installation Guide

## Quick Start (Minimal Installation)

The easiest way to get started is with the minimal installation that includes only core dependencies:

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-code-morph.git
cd claude-code-morph

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with minimal dependencies
pip install -r requirements-minimal.txt

# Or install as a package
pip install .
```

This gives you:
- ✅ Main tab with Claude CLI integration
- ✅ Morph tab for self-editing
- ✅ All core functionality
- ❌ Context tab (requires optional dependencies)

## Installation Options

### 1. Minimal Installation (Recommended for new users)
```bash
pip install .
```
- Installs only core dependencies
- No build issues or complex dependencies
- Works on all Python versions

### 2. With Context Features
```bash
pip install .[context]
```
- Adds ChromaDB for semantic search
- Enables the Context tab
- Requires Python ≤ 3.12 and system dependencies

### 3. With AI Provider Libraries
```bash
pip install .[ai]
```
- Adds support for Groq, OpenAI, and Anthropic APIs
- Optional - Claude CLI works without these

### 4. Full Installation
```bash
pip install .[all]
```
- Everything including context and AI features
- For advanced users who want all features

## System Requirements

### Core Requirements
- Python 3.8 or higher
- pip
- git

### Optional Requirements (for Context tab)
- Python 3.12 or earlier (some ML dependencies don't support 3.13 yet)
- Build tools:
  - **Ubuntu/Debian**: `sudo apt-get install build-essential cmake pkg-config`
  - **macOS**: `xcode-select --install`
  - **Windows**: Install Visual Studio Build Tools

## Troubleshooting

### Python 3.13 Issues

If you're on Python 3.13 and want context features:

```bash
# Use the Python 3.13 compatible requirements
pip install -r requirements-py313.txt

# Or run the fix script
./fix_dependencies.sh
```

### Build Errors

Common errors and solutions:

1. **"cmake: not found"**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install cmake pkg-config
   
   # macOS
   brew install cmake pkg-config
   ```

2. **"error: Microsoft Visual C++ 14.0 is required"** (Windows)
   - Download and install Visual Studio Build Tools
   - Or use pre-built wheels: `pip install --only-binary :all: sentencepiece`

3. **sentencepiece build fails**
   ```bash
   # Try installing from conda instead
   conda install -c conda-forge sentencepiece
   
   # Or skip it - the app works without it
   pip install -r requirements-minimal.txt
   ```

### Context Tab Shows "Not Available"

This is normal if you haven't installed the optional dependencies. To enable:

```bash
pip install .[context]
```

Or if that fails:

```bash
pip install chromadb sentence-transformers
```

### Claude CLI Not Found

Make sure Claude CLI is installed:
```bash
# Check if installed
which claude

# If not, install it
# Follow instructions at: https://claude.ai/cli
```

## Alternative Installation Methods

### Using pip directly from GitHub
```bash
# Minimal
pip install git+https://github.com/yourusername/claude-code-morph.git

# With extras
pip install "git+https://github.com/yourusername/claude-code-morph.git#egg=claude-code-morph[context]"
```

### Development Installation
```bash
# Clone and install in editable mode
git clone https://github.com/yourusername/claude-code-morph.git
cd claude-code-morph
pip install -e .  # or pip install -e .[all]
```

### Using Poetry (if you prefer)
```bash
# Install poetry
pip install poetry

# Install dependencies
poetry install

# With extras
poetry install -E context -E ai
```

## Verifying Installation

After installation, verify everything works:

```bash
# Check the command is available
morph --version

# Run the application
morph

# Or use the full command
claude-code-morph
```

## Upgrading

To upgrade to the latest version:

```bash
# If installed from git
cd claude-code-morph
git pull
pip install -e . --upgrade

# If installed from pip
pip install --upgrade claude-code-morph
```

## Uninstalling

To completely remove:

```bash
# Uninstall the package
pip uninstall claude-code-morph

# Remove configuration (optional)
rm -rf ~/.morph
rm -rf ~/.claude
```

## Getting Help

If you encounter issues:

1. Check the logs:
   ```bash
   tail -f logs/error.log
   ```

2. Run in debug mode:
   ```bash
   morph --debug
   ```

3. Report issues: https://github.com/yourusername/claude-code-morph/issues

## Next Steps

After installation:

1. Run `morph` to start the application
2. Configure your Claude CLI API key if needed
3. Try the Main tab for normal development
4. Try the Morph tab to edit the IDE itself
5. Install context dependencies later if you want the Context tab

Remember: The app works great with just the minimal installation! Add features as you need them.