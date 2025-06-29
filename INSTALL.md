# Installation Guide for Claude Code Morph

## Prerequisites

- Python 3.8 or higher
- An active virtual environment (recommended)
- Claude CLI installed and configured

## Standard Installation

### For Most Developers

```bash
# Make sure you're in a virtual environment
# If not, create one:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install from GitHub
pip install git+https://github.com/yourusername/claude-code-morph.git

# Or install from local source
git clone https://github.com/yourusername/claude-code-morph.git
pip install -e ./claude-code-morph

# Run morph
morph
```

### For Project Integration

Add to your project's requirements.txt:
```
git+https://github.com/yourusername/claude-code-morph.git
```

Or requirements-dev.txt for development dependencies:
```
-e git+https://github.com/yourusername/claude-code-morph.git#egg=claude-code-morph
```

## Future: PyPI Installation

Once published to PyPI, installation will be even simpler:
```bash
pip install claude-code-morph
```

## Verifying Installation

After installation, you should be able to run:

```bash
morph --help
```

## Usage

```bash
# Launch in current directory
morph

# Launch in specific directory
morph --cwd /path/to/project

# Override morph source location (advanced)
morph --morph-dir /path/to/morph/source
```

## Troubleshooting

### "pip: command not found"

If you get this error, try:
- `pip3` instead of `pip`
- `python -m pip` or `python3 -m pip`
- Install pip: `sudo apt install python3-pip` (Ubuntu/Debian)

### "error: externally-managed-environment"

This error occurs on Ubuntu 23.04+ and Debian 12+. Solutions:

1. **Use a virtual environment** (recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

2. **Use pipx** for CLI tools:
   ```bash
   sudo apt install pipx
   pipx install -e .
   ```

3. **Override the protection** (use carefully):
   ```bash
   pip install --user -e . --break-system-packages
   ```

### "morph: command not found"

This means the installation directory isn't in your PATH:
- Check where it was installed: `pip show -f claude-code-morph | grep morph$`
- Add the directory to your PATH

### Permission errors

If you get permission errors, use `--user` flag:
```bash
pip install --user .
```

## Uninstalling

```bash
pip uninstall claude-code-morph
```