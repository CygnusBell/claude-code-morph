# Changelog

## 2025-07-04

### Fixed
- Added comprehensive error handling for DOMQuery errors
  - Wrapped all `query_one` calls in try-except blocks
  - Added proper error messages for tab switching failures
  - Fixed context tab activation when dependencies are missing
- Improved context feature initialization
  - Added checks for CONTEXT_AVAILABLE before initializing
  - Better error messages when context dependencies are missing
  - Prevents crashes when trying to use context features without deps

### Added
- Created debugging tools and documentation
  - `debug_domquery.py` - Enhanced debug script with monkey patches
  - `docs/DEBUGGING.md` - Comprehensive debugging guide
  - Better error logging throughout the application

### Changed
- Context manager initialization now fails gracefully
- Tab switching methods now show user-friendly error notifications
- Context tab activation shows helpful message about missing dependencies