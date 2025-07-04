# Context Tab Optional Dependencies

The Context tab features in Claude Code Morph have been made optional. The application will now run without the following dependencies, with graceful degradation:

## Optional Dependencies

- **chromadb**: Vector database for semantic search
- **sentence-transformers**: For creating embeddings
- **watchdog**: For file watching capabilities
- **tiktoken**: For accurate token counting
- **pymupdf**: For PDF text extraction

## How It Works

### 1. Context Manager (`context_manager.py`)
- Checks for each dependency at import time
- Sets availability flags (e.g., `CHROMADB_AVAILABLE`)
- Methods return early or provide fallback behavior when dependencies are missing
- Token chunking falls back to character-based splitting if tiktoken is unavailable

### 2. Context Integration (`context_integration.py`)
- Checks if ChromaDB is available in `__init__`
- Sets `self.available` flag based on dependency availability
- All methods check availability before attempting operations
- Returns empty results or False for operations when unavailable

### 3. Context Panel (`panels/ContextPanel.py`)
- Checks for ChromaDB availability in `compose_content()`
- Shows an informational message when dependencies are missing
- Message includes installation instructions for the optional dependencies

### 4. Main Application (`main.py`)
- Checks `CONTEXT_AVAILABLE` flag before creating Context tab
- Only initializes context integration if dependencies are available
- Context container is only created if dependencies are available

## Installing Optional Dependencies

To enable full context features, install the optional dependencies:

```bash
pip install chromadb sentence-transformers watchdog tiktoken pymupdf
```

## Testing

Run the test script to verify graceful degradation:

```bash
python test_without_context.py
```

This script mocks the missing dependencies and verifies that:
1. The modules can be imported without errors
2. Appropriate warning messages are logged
3. The availability flags are set correctly
4. Instances can be created with `available=False`