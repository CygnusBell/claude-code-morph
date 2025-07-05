# Debugging Guide for Claude Code Morph

## Common Issues and Solutions

### 1. DOMQuery Errors

**Symptom**: Textual error overlay mentioning "DOMQuery" appears over the IDE.

**Cause**: The app tries to query for widgets that may not exist yet, especially when switching tabs or during initialization.

**Fixes Applied**:
- Added try-except blocks around all `query_one` calls in tab switching methods
- Added proper error handling in `_activate_context_tab` method
- Added initialization checks for context features before attempting to use them

**Debug Tools**:
1. **Enhanced Debug Script** (`debug_domquery.py`):
   ```bash
   python debug_domquery.py
   ```
   This script adds extensive logging and monkey patches to capture DOMQuery errors with full context.

2. **Textual Debug Mode** (`debug_textual.sh`):
   ```bash
   ./debug_textual.sh
   ```
   Runs the app with Textual's built-in debugging enabled. Check `logs/textual_debug.log` for details.

3. **Simple Test Script** (`test_simple.py`):
   ```bash
   python test_simple.py
   ```
   Tests if Textual is working at all with a minimal app.

### 2. Terminal Display Issues ("p" on screen)

**Symptom**: App shows just the letter "p" and nothing else.

**Cause**: Terminal bracketed paste mode interfering with the TUI.

**Solutions**:
1. Use the safe runner script:
   ```bash
   ./run_morph.sh
   ```

2. Or use the Python wrapper:
   ```bash
   python morph_safe.py
   ```

### 3. Dependency Issues

**Symptom**: Installation fails due to tiktoken or sentencepiece on Python 3.13.

**Solution**: Install minimal requirements first:
```bash
pip install -r requirements-minimal.txt
```

Then optionally install context features:
```bash
pip install -e .[context]
```

### 4. Context Tab Not Available

**Symptom**: Context tab missing or showing errors, or showing "requirements not installed" even though pip says "already satisfied".

**Cause**: Multiple issues can cause this:
1. Optional dependencies not installed
2. Using wrong Python/pip (system vs virtual environment)
3. Multiple virtual environments with different installations

**Solutions**:

1. **Check which Python you're using**:
   ```bash
   which python
   which pip
   ```
   If it shows `/usr/bin/python`, you're using system Python!

2. **Use the correct virtual environment**:
   ```bash
   source venv/bin/activate  # or .venv/bin/activate
   pip install -e .[context]
   ```

3. **Use the provided launcher scripts**:
   ```bash
   ./run_morph.sh  # Automatically activates the right venv
   # or
   ./morph         # Smart launcher that finds the right venv
   ```

4. **Check your dependencies**:
   ```bash
   python check_context_deps.py
   ```

5. **If pip says "already satisfied" but it's not working**:
   This usually means you installed to a different environment. Make sure to:
   - Activate the venv first: `source venv/bin/activate`
   - Then install: `pip install -e .[context]`
   - Then run: `python -m claude_code_morph`

If you still have issues with specific dependencies, you can skip them and the app will work without context features.

## Log Files

All logs are stored in the `logs/` directory:

- `main.log` - General application logs
- `error.log` - Error-specific logs with stack traces
- `textual_debug.log` - Textual framework debug logs (when using debug mode)
- `stderr.log` - Standard error output
- `debug_YYYYMMDD_HHMMSS.log` - Timestamped debug logs from debug_domquery.py

## Checking Logs

To see the most recent errors:
```bash
tail -n 50 logs/error.log
```

To monitor logs in real-time:
```bash
tail -f logs/main.log
```

To search for specific errors:
```bash
grep -i "domquery" logs/*.log
```

## Widget Tree Debugging

The app logs the widget tree at various points. To see the current widget structure:
```bash
grep -A 20 "Widget tree" logs/main.log | tail -50
```

## Environment Variables

For additional debugging, you can set these environment variables:

```bash
# Enable Textual debugging
export TEXTUAL_LOG="logs/textual_debug.log"
export TEXTUAL_LOG_LEVEL="DEBUG"

# Run the app
python -m claude_code_morph
```

## Reporting Issues

When reporting issues, please include:

1. The error message from the overlay (if visible)
2. Contents of `logs/error.log` (last 100 lines)
3. Python version: `python --version`
4. OS information
5. Whether you're using SSH or a local terminal
6. Which dependencies you have installed

You can gather this info with:
```bash
python --version > debug_info.txt
echo "---" >> debug_info.txt
pip list | grep -E "(textual|claude-code-morph|chromadb)" >> debug_info.txt
echo "---" >> debug_info.txt
tail -100 logs/error.log >> debug_info.txt
```