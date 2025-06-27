# Claude Code Morph

A modular, live-editable development environment powered by Claude CLI. This self-editable coding workspace can evolve itself through live agent prompting.

## Features

- **Self-Editing Environment**: The app registers its own source directory as the working directory for Claude CLI, allowing it to modify itself
- **Hot-Reloading Panels**: Panels automatically reload when their source code changes
- **Prompt Optimization**: Built-in prompt optimizer using Claude or OpenAI to enhance your prompts
- **Persistent Claude Session**: Maintains Claude CLI state across multiple prompts
- **Workspace Management**: Save and load custom UI layouts
- **Modular Architecture**: Easy to extend with new panels

## Installation

1. **Prerequisites**:
   - Python 3.8+
   - Claude CLI installed and configured (`claude` command available)
   - (Optional) API keys for prompt optimization:
     - `ANTHROPIC_API_KEY` for Claude-based optimization
     - `OPENAI_API_KEY` for GPT-based optimization

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Starting the Application

```bash
python main.py
```

On startup, you'll be prompted to:
- Start with the default layout (Prompt Panel + Terminal Panel)
- Start from scratch (Terminal Panel only)

### Keyboard Shortcuts

**Global**:
- `Ctrl+S`: Save current workspace
- `Ctrl+L`: Load workspace
- `Ctrl+Q`: Quit application
- `Ctrl+R`: Reload all panels (hot-reload)

**Prompt Panel**:
- `Enter`: Submit prompt
- `Ctrl+Enter`: Submit prompt (alternative)
- `Ctrl+O`: Optimize prompt
- `Ctrl+L`: Clear prompts
- `Ctrl+Up/Down`: Navigate prompt history

**Terminal Panel**:
- `Ctrl+C`: Send interrupt to Claude
- `Ctrl+D`: Restart Claude CLI

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

- **Claude CLI not starting**: Ensure `claude` command is in your PATH
- **Prompt optimization not working**: Check API keys are set correctly
- **Hot-reload not working**: Check file permissions in the `panels/` directory
- **UI freezing**: Use Ctrl+C in terminal to interrupt long-running operations

## Future Enhancements

- Drag-and-drop panel rearrangement
- More built-in panel types (file browser, git panel, etc.)
- Plugin system for external panels
- Theme customization
- Multi-tab terminal support