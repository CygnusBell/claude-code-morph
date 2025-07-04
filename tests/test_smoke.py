#!/usr/bin/env python3
"""Quick smoke tests to verify basic functionality."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that core modules can be imported."""
    try:
        import claude_code_morph.main
        assert True
    except ImportError as e:
        assert False, f"Failed to import main: {e}"


def test_app_creation():
    """Test that app can be created."""
    from claude_code_morph.main import ClaudeCodeMorph
    
    app = ClaudeCodeMorph()
    assert app is not None
    assert hasattr(app, 'compose')
    assert hasattr(app, 'on_mount')


def test_context_detection():
    """Test context availability detection."""
    import claude_code_morph.main as main
    
    # Should be a boolean
    assert isinstance(main.CONTEXT_AVAILABLE, bool)
    
    # Log the result for debugging
    print(f"CONTEXT_AVAILABLE = {main.CONTEXT_AVAILABLE}")


def test_panel_imports():
    """Test that panels can be imported."""
    panels_to_test = [
        'BasePanel',
        'PromptPanel',
        'EmulatedTerminalPanel',
        'ContextPanel',
        'MorphPanel',
        'FileEditorPanel'
    ]
    
    for panel_name in panels_to_test:
        try:
            module = __import__(
                f'claude_code_morph.panels.{panel_name}',
                fromlist=[panel_name]
            )
            panel_class = getattr(module, panel_name)
            assert panel_class is not None
            print(f"✓ {panel_name} imported successfully")
        except ImportError as e:
            # Some panels might have optional dependencies
            if "ContextPanel" in panel_name:
                print(f"⚠ {panel_name} skipped (optional dependencies)")
            else:
                assert False, f"Failed to import {panel_name}: {e}"


if __name__ == "__main__":
    # Run the smoke tests
    print("Running smoke tests...")
    test_imports()
    test_app_creation()
    test_context_detection()
    test_panel_imports()
    print("\nAll smoke tests passed! ✓")