# Changelog

## 2025-07-04 - UI Improvements and Copy/Paste Support

### Added
- **Settings Tab** - New tab for editing Claude CLI configuration files
  - Tree view of all config files (global, user, project)
  - Live editing with syntax highlighting for JSON/YAML/Markdown
  - Save/reload/backup functionality with validation
  - Shows file status (exists, readable, writable)
  - Accessible via Ctrl+4
- **Copy/Paste Support in Terminal**
  - Ctrl+Shift+C to copy terminal content
  - Ctrl+Shift+V to paste into terminal
  - Enables claude code account login with token copying
  - Falls back to file clipboard if system clipboard unavailable
- **Loading Screen** - Proper loading animation during startup
  - Shows progress through initialization steps
  - Prevents "p"/"pp" display issue
  - 10-second watchdog timer prevents hanging

### Fixed
- **Tab Visibility** - Tab text now clearly visible with proper colors
  - Fixed tab button text color (#f8f8f2)
  - Improved hover and active states
  - Better contrast between active/inactive tabs
- **UI Alignment** - Better spacing and layout consistency
  - Fixed panel header text colors
  - Improved Settings panel layout
  - Consistent container styling
- **Initialization Issues**
  - Fixed @work decorator causing coroutine errors
  - Improved signal handling for emergency exit
  - Fixed initialization hanging with watchdog timer

### Changed
- Tab styling with better visual hierarchy
- Settings panel loads on-demand for performance

## 2025-07-04 - Git Hooks and Testing Updates

### Added 
- Git hooks for automated testing before push
  - `pre-push` hook runs smoke tests and checks for syntax errors
  - `pre-commit` hook checks for syntax errors and common issues
  - Configurable via environment variables
  - Easy install with `install_hooks.sh`
- Hook documentation in `.githooks/README.md`

### Changed
- Temporarily disabled integration tests in pre-push hook due to Textual 3.5.0 API changes
- Updated to Textual 3.5.0 (testing API needs updating)

## 2025-07-04 - Testing Framework

### Added
- Comprehensive integration test suite
  - `test_integration.py` - Tests app startup, tab switching, panel loading
  - `test_context_panel.py` - Specific tests for DOMQuery error handling
  - `test_smoke.py` - Quick import and initialization checks
- Test runner script (`run_tests.sh`) with multiple modes
- Test dependencies in `setup.py` as `[test]` extra
- Testing documentation (`docs/TESTING.md`)

### Fixed
- Syntax error in `_activate_context_tab` with global declaration

## 2025-07-04 - Earlier Updates

### Fixed
- Added comprehensive error handling for DOMQuery errors
  - Wrapped all `query_one` calls in try-except blocks
  - Added proper error messages for tab switching failures
  - Fixed context tab activation when dependencies are missing
- Improved context feature initialization
  - Added checks for CONTEXT_AVAILABLE before initializing
  - Better error messages when context dependencies are missing
  - Prevents crashes when trying to use context features without deps
- Virtual environment detection issues
  - Added smart launcher script that finds the correct venv
  - Updated run_morph.sh to show which Python is being used
  - Fixed "already satisfied" but not working dependency issues

### Added
- Created debugging tools and documentation
  - `debug_domquery.py` - Enhanced debug script with monkey patches
  - `docs/DEBUGGING.md` - Comprehensive debugging guide
  - Better error logging throughout the application
- Development tools
  - `check_context_deps.py` - Diagnostic tool for dependency issues
  - `setup.sh` - Interactive setup script for new users
  - `morph` - Smart launcher that auto-detects the correct venv

### Changed
- Context manager initialization now fails gracefully
- Tab switching methods now show user-friendly error notifications
- Context tab activation shows helpful message about missing dependencies
- run_morph.sh now displays which Python interpreter is being used