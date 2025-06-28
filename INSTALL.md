# Installation Guide for Claude Code Morph

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)

## Installation Methods

### 1. Install from source (Recommended for developers)

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-code-morph.git
cd claude-code-morph

# Install in editable mode (for development)
pip install -e .

# Or for a regular installation
pip install .
```

### 2. Install with pip3 (if pip is not available)

```bash
# If you only have pip3 available
pip3 install -e .

# Or
python3 -m pip install -e .
```

### 3. Install in virtual environment (Cleanest approach)

```bash
# Create a virtual environment
python -m venv morph-env
source morph-env/bin/activate  # On Windows: morph-env\Scripts\activate

# Install
pip install -e .
```

### 4. Install globally without sudo

```bash
# Install to user directory
pip install --user .

# Make sure ~/.local/bin is in your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
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