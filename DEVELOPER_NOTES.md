# Developer Notes for Claude Code Morph

## CRITICAL: Package Structure

This project is a **Python package** installed via pip. Understanding the directory structure is crucial to avoid editing the wrong files.

### Directory Structure

```
claude-code-morph/
├── setup.py                    # Package configuration
├── requirements.txt            # Package dependencies
├── README.md                   # User documentation
├── INSTALL.md                  # Installation guide
├── DEVELOPER_NOTES.md          # This file
├── claude_code_morph/          # ⚠️ THE ACTUAL PACKAGE CODE ⚠️
│   ├── __init__.py
│   ├── main.py                 # Main application entry
│   ├── cli.py                  # CLI entry point (morph command)
│   ├── panels/                 # ⚠️ EDIT THESE FILES ⚠️
│   │   ├── BasePanel.py        # Base class for all panels
│   │   ├── PromptPanel.py      # Prompt input and style selection
│   │   ├── TerminalPanel.py    # Claude interaction display
│   │   ├── clipboard_fallback.py
│   │   └── osc52_clipboard.py
│   └── workspaces/             # Saved workspace configurations
└── (other project files)
```

## Important Notes

### 1. Always Edit Files in the Package Directory

**CORRECT**: Edit files in `/claude_code_morph/panels/`
**WRONG**: Creating or editing files in `/panels/` (root level)

### 2. How the Package Works

- The `morph` command is defined in `setup.py` as an entry point
- It runs `claude_code_morph.cli:main`
- The CLI sets up environment variables and launches the main app
- Hot-reloading watches the package directory, not the root

### 3. Installation Modes

#### Development Mode (Recommended)
```bash
pip install -e .
```
- Creates a link to your development directory
- Changes to files in `claude_code_morph/` are immediately reflected
- No need to reinstall after changes

#### Regular Installation
```bash
pip install .
```
- Copies files to site-packages
- Changes to source files won't be reflected until reinstall

### 4. Hot-Reloading

The hot-reload system watches:
- `claude_code_morph/panels/` for panel changes
- Automatically reloads panels when their `.py` files are modified
- Only reloads the specific panel that changed, preserving state in others

### 5. Working Directory Management

When morph runs:
- In "develop" mode: Uses the user's current working directory
- In "morph" mode: Uses the morph source directory for self-editing
- Environment variables set by CLI:
  - `MORPH_SOURCE_DIR`: Points to the package directory
  - `MORPH_USER_CWD`: The directory where user ran `morph`

### 6. Common Pitfalls

1. **Editing wrong files**: Always check you're in `claude_code_morph/` subdirectory
2. **Import errors**: Use relative imports within the package
3. **Hot-reload not working**: Check the file watcher is monitoring the right directory
4. **Package not found**: Ensure you've run `pip install -e .` in development

### 7. Testing Changes

1. Make changes to files in `claude_code_morph/panels/`
2. The app should hot-reload automatically
3. Check `main.log` for reload messages and errors
4. If hot-reload fails, restart the app with `morph`

### 8. Debugging Tips

- Check `main.log` for detailed error messages
- Use `logging.debug()` statements to trace execution
- The compose methods are called during hot-reload
- Panel state is preserved in `_init_params` during reload

## Adding New Panels

1. Create new panel in `claude_code_morph/panels/`
2. Inherit from `BasePanel`
3. Implement `compose_content()` method
4. Add to workspace configuration in `workspaces/default.yaml`

## Project Philosophy

This is a "self-editing" environment where Claude can modify its own interface. The package structure enables:
- Clean separation of package code from project files
- Easy distribution via pip
- Hot-reloading for rapid development
- Self-modification when in "morph" mode