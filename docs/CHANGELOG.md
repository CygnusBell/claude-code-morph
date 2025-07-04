# Changelog

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