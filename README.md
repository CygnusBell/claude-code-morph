# Claude Code Morph

A modular, live-editable development environment powered by Claude CLI. This self-editable coding workspace can evolve itself through live agent prompting.

## Features

- **Self-Editing Environment**: The app registers its own source directory as the working directory for Claude CLI, allowing it to modify itself
- **Hot-Reloading Panels**: Panels automatically reload when their source code changes
- **Prompt Optimization**: Built-in prompt optimizer using Claude or OpenAI to enhance your prompts
- **Persistent Claude Session**: Maintains Claude CLI state across multiple prompts
- **Workspace Management**: Save and load custom UI layouts
- **Modular Architecture**: Easy to extend with new panels

## ⚠️ Important: Package Structure

This is a **Python package**. The actual code lives in the `claude_code_morph/` subdirectory:
- **Source files**: `claude_code_morph/panels/`, `claude_code_morph/main.py`, etc.
- **NOT** in root-level directories

See [DEVELOPER_NOTES.md](DEVELOPER_NOTES.md) for detailed information about the project structure.

## Prerequisites

- Python 3.8+ (Python 3.12 or earlier recommended for best compatibility)
- pip (Python package installer)
- Claude CLI installed and configured (`claude` command available)
- (Optional) API keys for prompt optimization:
  - `ANTHROPIC_API_KEY` for Claude-based optimization
  - `OPENAI_API_KEY` for GPT-based optimization

## Installation

### Quick Start (Minimal Installation)

The easiest way to get started is with the minimal installation that includes only the core dependencies:

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-code-morph.git
cd claude-code-morph

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install minimal dependencies
pip install -r requirements-minimal.txt

# Run the application
python -m claude_code_morph
```

### Standard Installation (Recommended)

For a more integrated experience with package management:

```bash
# Clone and enter directory
git clone https://github.com/yourusername/claude-code-morph.git
cd claude-code-morph

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with minimal dependencies
pip install -e . -r requirements-minimal.txt

# Run morph
morph
```

### Optional: Advanced Features

The app includes optional features that require additional dependencies. These are **completely optional** - the app works perfectly fine without them.

#### Option 1: Using pip extras (Recommended)
```bash
# Install with Context tab support (semantic search, embeddings)
pip install -e ".[context]"

# Install with prompt optimization support (Claude/OpenAI)
pip install -e ".[optimization]"

# Install all optional features
pip install -e ".[all]"
```

#### Option 2: Manual installation
```bash
# Context tab dependencies
pip install chromadb sentence-transformers watchdog tiktoken pypdf

# Prompt optimization dependencies
pip install anthropic openai groq

# Or install everything from requirements.txt
pip install -r requirements.txt
```

**Note**: If you encounter issues installing these optional dependencies, don't worry! The app will detect missing dependencies and disable those features gracefully.

### Alternative Installation Methods

#### Method 1: Direct from GitHub
```bash
# Install directly from GitHub (minimal dependencies only)
pip install git+https://github.com/yourusername/claude-code-morph.git

# Run morph
morph
```

#### Method 2: Development Install
```bash
# For development with all features
git clone https://github.com/yourusername/claude-code-morph.git
cd claude-code-morph
pip install -e . -r requirements.txt
```

## Usage

### Running Morph

After installation, you can run morph in several ways:

```bash
# If installed with pip install -e
morph

# Launch in specific directory
morph --cwd /path/to/project

# Direct module execution (always works)
python -m claude_code_morph

# Legacy method (from root directory)
python claude_code_morph/main.py
```

The app automatically loads the default workspace with Prompt Panel and Terminal Panel.

### Keyboard Shortcuts

**Global**:
- `Ctrl+S`: Save current workspace
- `Ctrl+L`: Load workspace
- `Ctrl+Q`: Quit application
- `Ctrl+R`: Reload all panels (hot-reload)

**Copy/Paste (macOS)**:
- `Cmd+C`: Copy selected text (or all if nothing selected)
- `Cmd+Shift+C`: Copy all panel content
- `Cmd+A`: Select all text in current panel (PromptPanel only)

**Copy/Paste (Linux/Windows)**:
- `Ctrl+Shift+C`: Copy selected text
- `Cmd+Shift+C`: Copy all panel content (if supported)

**Prompt Panel**:
- `Enter`: Submit prompt
- `Ctrl+Enter`: Submit prompt (alternative)
- `Ctrl+O`: Optimize prompt
- `Ctrl+L`: Clear prompts
- `Ctrl+Up/Down`: Navigate prompt history

**Terminal Panel**:
- `Ctrl+K`: Interrupt Claude
- `Ctrl+R`: Restart Claude session

### Configuration

Configuration can be set via:

1. **Environment Variables**:
   ```bash
   export CCM_THEME=dark
   export CCM_AUTO_SAVE=true
   export CCM_HOT_RELOAD=true
   export CCM_OPTIMIZER_API=anthropic
   export ANTHROPIC_API_KEY=your-key-here
   ```

2. **Config File** (`~/.claude-code-morph/config.yaml`):
   ```yaml
   theme: dark
   auto_save_workspace: true
   hot_reload_enabled: true
   optimizer_api: anthropic
   optimizer_model: claude-3-haiku-20240307
   ```

### Creating Custom Panels

1. Create a new panel in the `panels/` directory:
   ```python
   # panels/MyCustomPanel.py
   from textual.widgets import Static
   
   class MyCustomPanel(Static):
       def __init__(self, **kwargs):
           super().__init__(**kwargs)
           self._init_params = kwargs  # Required for hot-reload
   ```

2. The panel will be automatically available for use in workspaces

3. Add it to a workspace configuration:
   ```yaml
   layout:
     - type: MyCustomPanel
       id: custom
       params:
         some_param: value
   ```

### Workspace Configuration

Workspaces are stored as YAML files in the `workspaces/` directory:

```yaml
name: my-workspace
layout:
  - type: PromptPanel
    id: prompt
    params:
      auto_start: true
  - type: TerminalPanel
    id: terminal
    params:
      auto_start: true
  - type: MyCustomPanel
    id: custom
    params: {}
```

## Development

### Project Structure

```
claude-code-morph/
├── main.py                 # Entry point and main app
├── morph_config.py        # Configuration management
├── panels/                # Panel modules
│   ├── PromptPanel.py    # Prompt input and optimization
│   └── TerminalPanel.py  # Claude CLI terminal
├── workspaces/           # Saved workspace configurations
│   └── default.yaml      # Default workspace
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### How Hot-Reloading Works

The application uses Python's `watchdog` library to monitor the `panels/` directory. When a panel file is modified:

1. The file watcher detects the change
2. The modified module is reloaded using `importlib`
3. All instances of that panel are recreated with their saved parameters
4. The UI updates automatically without losing state

### How Self-Editing Works

On startup, the app:
1. Changes the working directory to its own source directory
2. Launches Claude CLI with this directory as the cwd
3. Any prompts sent to Claude can now modify the app's source code
4. Hot-reloading ensures changes take effect immediately

This creates a powerful feedback loop where you can use Claude to:
- Add new features to the app
- Fix bugs in real-time
- Create new panel types
- Modify the UI layout
- Enhance existing functionality

## Tips

1. **Start Simple**: Begin with the default layout and gradually add panels
2. **Use Prompt Optimization**: The optimizer helps create better Claude prompts
3. **Save Workspaces**: Save your preferred layouts for different tasks
4. **Leverage Self-Editing**: Ask Claude to enhance the app itself
5. **Watch the Terminal**: The terminal panel shows Claude's responses and thinking

## Troubleshooting

### Common Installation Issues

#### Python Version Compatibility
- **Python 3.13 issues**: Some dependencies may have compatibility issues with Python 3.13. Use Python 3.12 or earlier for best results.
- **Check your Python version**: `python --version`
- **Use pyenv or conda** to manage multiple Python versions if needed

#### Dependency Installation Failures

**1. Build Tools Missing**
```bash
# On Ubuntu/Debian:
sudo apt-get install build-essential python3-dev cmake pkg-config

# On macOS:
xcode-select --install
brew install cmake pkg-config

# On Windows:
# Install Visual Studio Build Tools or use WSL
```

**2. ChromaDB Installation Issues** (Optional dependency)
```bash
# If chromadb fails, try:
pip install --upgrade pip setuptools wheel
pip install chromadb --no-cache-dir

# Or skip it entirely - the app works without it!
```

**3. Sentence Transformers Issues** (Optional dependency)
```bash
# If sentence-transformers fails due to torch:
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install sentence-transformers
```

**4. Package Conflicts**
```bash
# Create a fresh virtual environment
python -m venv fresh_venv
source fresh_venv/bin/activate
pip install -r requirements-minimal.txt
```

### Runtime Issues

- **Claude CLI not starting**: 
  - Ensure `claude` command is in your PATH
  - Test with: `claude --version`
  - If not found, install Claude CLI first

- **Prompt optimization not working**: 
  - Check API keys are set correctly
  - Test with: `echo $ANTHROPIC_API_KEY` or `echo $OPENAI_API_KEY`

- **Hot-reload not working**: 
  - Check file permissions in the `panels/` directory
  - Ensure watchdog is installed (optional dependency)

- **UI freezing**: 
  - Use Ctrl+K to interrupt Claude operations
  - Check terminal output for error messages

- **Context tab shows "not available"**:
  - This is normal if optional dependencies aren't installed
  - Install them with: `pip install chromadb sentence-transformers watchdog tiktoken pypdf`

- **Copy/Paste not working over SSH**: 
  - The app uses OSC 52 escape sequences for clipboard support over SSH
  - **iTerm2**: Works by default
  - **Terminal.app**: Enable in Preferences → Profiles → Advanced → "Allow sending of clipboard contents"
  - **tmux**: Add `set -g set-clipboard on` to ~/.tmux.conf
  - **kitty, alacritty**: Usually work by default

### Getting Help

1. **Check the logs**: Look for `app.log` and `main.log` in the project directory
2. **Run in verbose mode**: Set environment variable `CCM_DEBUG=true`
3. **Test minimal setup**: Try running with just `requirements-minimal.txt` first
4. **Report issues**: Include Python version, OS, and error messages

## Future Enhancements

- Drag-and-drop panel rearrangement
- More built-in panel types (file browser, git panel, etc.)
- Plugin system for external panels
- Theme customization
- Multi-tab terminal support