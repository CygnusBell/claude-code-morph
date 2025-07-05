# Git Hooks for Claude Code Morph

These hooks help maintain code quality by running tests before pushing.

## Installation

```bash
./install_hooks.sh
```

## Hooks Included

### pre-push
Runs before `git push`:
- ✓ Smoke tests (always)
- ✓ Integration tests (if pytest installed)
- ✓ Python syntax check
- ✓ Warns about print statements

### pre-commit
Runs before `git commit`:
- ✓ Python syntax check (fast)
- ✓ Checks for pdb breakpoints
- ✓ Checks for merge conflict markers
- ✓ Notes new TODOs/FIXMEs

## Configuration

Set these environment variables to customize behavior:

```bash
# Skip integration tests (only run smoke tests)
export MORPH_SKIP_INTEGRATION_TESTS=true

# Allow print statements without prompting
export MORPH_ALLOW_PRINTS=true

# Run tests in parallel
export MORPH_PARALLEL_TESTS=true

# Set test timeout (seconds)
export MORPH_TEST_TIMEOUT=120
```

Or edit `.githooks/config.sh` to set defaults.

## Bypassing Hooks

If you need to push without running tests:

```bash
git push --no-verify
```

⚠️ **Use sparingly!** The hooks are there to catch problems.

## Uninstalling

```bash
rm .git/hooks/pre-push
rm .git/hooks/pre-commit
```

## Troubleshooting

**Tests fail but code works fine?**
- Make sure you're in the right virtual environment
- Run `./run_tests.sh -v` to see detailed output

**Hook runs too slowly?**
- Set `MORPH_SKIP_INTEGRATION_TESTS=true` for faster pushes
- Consider using pre-commit hook only

**Can't push urgent hotfix?**
- Use `git push --no-verify` for emergencies
- Fix tests in next commit