#!/bin/bash
# Configuration for git hooks

# Set to "true" to skip integration tests on push (only run smoke tests)
SKIP_INTEGRATION_TESTS="${MORPH_SKIP_INTEGRATION_TESTS:-false}"

# Set to "true" to allow print statements without prompting
ALLOW_PRINT_STATEMENTS="${MORPH_ALLOW_PRINTS:-false}"

# Set to "true" to run tests in parallel (faster but less clear output)
PARALLEL_TESTS="${MORPH_PARALLEL_TESTS:-false}"

# Maximum time to wait for tests (seconds)
TEST_TIMEOUT="${MORPH_TEST_TIMEOUT:-60}"