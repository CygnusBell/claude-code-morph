# Contributing to Claude Code Morph

Thank you for your interest in contributing to Claude Code Morph! This guide will help you get started.

## Project Structure

⚠️ **IMPORTANT**: This is a Python package. All source code lives in the `claude_code_morph/` subdirectory.

### Where to Find Things

```
claude-code-morph/
├── claude_code_morph/          # ← ALL SOURCE CODE IS HERE
│   ├── panels/                 # ← Edit panel files here
│   │   ├── BasePanel.py
│   │   ├── PromptPanel.py
│   │   └── TerminalPanel.py
│   ├── main.py                 # Main application
│   └── cli.py                  # CLI entry point
├── setup.py                    # Package configuration
├── requirements.txt            # Dependencies
└── README.md                   # User documentation
```

## Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/claude-code-morph.git
   cd claude-code-morph
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install in development mode**
   ```bash
   pip install -e .
   ```

4. **Run the application**
   ```bash
   morph
   ```

## Making Changes

### Editing Panels

1. **ALWAYS edit files in `claude_code_morph/panels/`**
   - NOT in a root-level `panels/` directory
   - The hot-reload system watches the package directory

2. **Panel Structure**
   - All panels inherit from `BasePanel`
   - Implement the `compose_content()` method
   - Use Textual's composition system for UI

3. **Hot-Reloading**
   - Changes to panel files are automatically detected
   - The panel will reload without restarting the app
   - Check `main.log` for reload messages

### Example: Adding a New Panel

1. Create a new file in `claude_code_morph/panels/`:
   ```python
   # claude_code_morph/panels/MyNewPanel.py
   from panels.BasePanel import BasePanel
   from textual.app import ComposeResult
   from textual.widgets import Static
   
   class MyNewPanel(BasePanel):
       def compose_content(self) -> ComposeResult:
           yield Static("Hello from MyNewPanel!")
   ```

2. Add it to a workspace configuration:
   ```yaml
   # claude_code_morph/workspaces/default.yaml
   panels:
     - class: MyNewPanel
       id: mynew
       width: 50%
   ```

### Testing Your Changes

1. **Check the logs**
   ```bash
   tail -f main.log
   ```

2. **Test hot-reloading**
   - Make a change to a panel file
   - Watch for reload messages in the log
   - Verify the UI updates

3. **Run manual tests**
   - Test all panel interactions
   - Verify Claude integration works
   - Check copy/paste functionality

## Common Issues

### Changes Not Appearing

1. **Wrong directory**: Ensure you're editing files in `claude_code_morph/panels/`
2. **Import errors**: Check `main.log` for Python errors
3. **Hot-reload failed**: Restart the app if necessary

### Import Errors

- Use relative imports within the package:
  ```python
  from panels.BasePanel import BasePanel  # Correct
  from BasePanel import BasePanel         # Wrong
  ```

### Claude Integration Issues

- Ensure Claude CLI is installed and working
- Check that the mode (develop/morph) is set correctly
- Verify prompts are being sent to the correct directory

## Submitting Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes**
   - Follow the existing code style
   - Add comments for complex logic
   - Update documentation if needed

3. **Test thoroughly**
   - Verify hot-reloading works
   - Test all affected functionality
   - Check for errors in `main.log`

4. **Commit with clear messages**
   ```bash
   git add -A
   git commit -m "Add feature: description of changes"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/my-new-feature
   ```

## Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings to classes and methods
- Keep lines under 100 characters

## Questions?

- Check [DEVELOPER_NOTES.md](DEVELOPER_NOTES.md) for technical details
- Open an issue for bugs or feature requests
- Join discussions in existing issues

Thank you for contributing!