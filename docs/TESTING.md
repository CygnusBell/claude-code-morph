# Testing Guide for Claude Code Morph

## Overview

Our tests focus on **integration testing** rather than unit testing because:
- Most bugs we've encountered are integration issues (DOMQuery errors, tab switching, panel loading)
- The app's UI components interact in complex ways
- Environment-specific issues (virtual environments, dependencies) are critical

## Running Tests

### Quick Smoke Test
```bash
./run_tests.sh --quick
```
Just verifies the app can start - useful for CI/CD.

### Normal Test Run
```bash
./run_tests.sh
```
Runs all integration tests.

### Verbose Mode
```bash
./run_tests.sh -v
```
Shows detailed test names and results.

### With Coverage
```bash
./run_tests.sh --coverage
```
Shows which code paths are tested.

### Manual Smoke Test
```bash
python tests/test_smoke.py
```
Basic import and initialization checks.

## Test Structure

### Integration Tests (`test_integration.py`)
Tests the full app experience:
- **App Startup**: Tests with/without context dependencies
- **Tab Switching**: Verifies Ctrl+Tab, Ctrl+1/2/3 work
- **DOMQuery Errors**: Ensures missing widgets don't crash
- **Panel Loading**: Verifies panels load in containers
- **Error Recovery**: Tests reload, CSS errors, missing files

### Context Panel Tests (`test_context_panel.py`)
Specifically targets the DOMQuery issues we fixed:
- Missing table handling
- Click events outside widgets
- Stats label updates
- Search input focus

### Smoke Tests (`test_smoke.py`)
Quick checks that can run without async:
- Module imports
- App creation
- Dependency detection

## What These Tests Catch

1. **The "p" display bug**: Would fail app startup tests
2. **DOMQuery crashes**: Explicitly tested in multiple scenarios
3. **Tab switching failures**: Covered by tab switching tests
4. **Missing dependencies**: Context availability tests
5. **Panel loading issues**: Workspace loading tests

## What These Tests DON'T Catch

1. **Visual glitches**: Can't test if UI looks correct
2. **Terminal emulation details**: Complex PTY behavior
3. **Real Claude CLI integration**: Would need mocking
4. **Performance issues**: Not testing speed
5. **Mouse interaction precision**: Only basic click testing

## Adding New Tests

When you fix a bug, add a test:

```python
@pytest.mark.asyncio
async def test_specific_bug_fix(self):
    """Test that [specific bug] doesn't happen."""
    app = ClaudeCodeMorph()
    async with app.run_test() as pilot:
        # Reproduce the bug scenario
        await pilot.press("keys-that-caused-bug")
        
        # Verify it's fixed
        assert app.is_running
        assert pilot.app.query("#expected-widget")
```

## Running Tests in CI/CD

Add to your GitHub Actions:

```yaml
- name: Run tests
  run: |
    pip install -e .[test]
    ./run_tests.sh --quick
```

## Debugging Failed Tests

1. **Check logs**: Tests create logs in `logs/` directory
2. **Run verbose**: Use `-vv` flag for full output
3. **Run single test**: 
   ```bash
   pytest tests/test_integration.py::TestAppStartup::test_app_starts_without_context_deps -vv
   ```

## Test Philosophy

We follow "**Test the problems you actually have**":
- Every test targets a real bug we've encountered
- Integration over unit tests
- Fast enough to run frequently
- Clear error messages when they fail