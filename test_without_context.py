#!/usr/bin/env python3
"""
Test script to verify the context modules handle missing dependencies gracefully.

This script simulates an environment where ChromaDB and related dependencies
are not installed, to ensure the modules gracefully degrade.
"""

import sys
import os

# Add the package to the path
sys.path.insert(0, os.path.dirname(__file__))

# Mock missing dependencies before importing
class MockModule:
    def __getattr__(self, name):
        raise ImportError(f"Mock: {name} not available")

# Replace modules in sys.modules to simulate missing dependencies
sys.modules['chromadb'] = MockModule()
sys.modules['sentence_transformers'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['watchdog.observers'] = MockModule()
sys.modules['watchdog.events'] = MockModule()
sys.modules['tiktoken'] = MockModule()
sys.modules['pymupdf'] = MockModule()

# Now try to import the context modules
print("Testing context_manager.py...")
try:
    from claude_code_morph.context_manager import (
        ContextManager, CHROMADB_AVAILABLE, SENTENCE_TRANSFORMERS_AVAILABLE,
        WATCHDOG_AVAILABLE, TIKTOKEN_AVAILABLE, PYMUPDF_AVAILABLE
    )
    
    print(f"✓ Successfully imported context_manager")
    print(f"  - CHROMADB_AVAILABLE: {CHROMADB_AVAILABLE}")
    print(f"  - SENTENCE_TRANSFORMERS_AVAILABLE: {SENTENCE_TRANSFORMERS_AVAILABLE}")
    print(f"  - WATCHDOG_AVAILABLE: {WATCHDOG_AVAILABLE}")
    print(f"  - TIKTOKEN_AVAILABLE: {TIKTOKEN_AVAILABLE}")
    print(f"  - PYMUPDF_AVAILABLE: {PYMUPDF_AVAILABLE}")
    
    # Test creating a ContextManager instance
    cm = ContextManager()
    print(f"✓ Created ContextManager instance")
    print(f"  - available: {cm.available}")
    
except ImportError as e:
    print(f"✗ Failed to import context_manager: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error with context_manager: {e}")
    sys.exit(1)

print("\nTesting context_integration.py...")
try:
    from claude_code_morph.context_integration import ContextIntegration
    
    print(f"✓ Successfully imported context_integration")
    
    # Test creating a ContextIntegration instance
    ci = ContextIntegration()
    print(f"✓ Created ContextIntegration instance")
    print(f"  - available: {ci.available}")
    
except ImportError as e:
    print(f"✗ Failed to import context_integration: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error with context_integration: {e}")
    sys.exit(1)

print("\nTesting ContextPanel.py...")
try:
    # First mock the BasePanel dependency
    sys.modules['claude_code_morph.panels.BasePanel'] = type(sys)('mock')
    sys.modules['claude_code_morph.panels.BasePanel'].BasePanel = object
    
    from claude_code_morph.panels.ContextPanel import ContextPanel
    
    print(f"✓ Successfully imported ContextPanel")
    
except ImportError as e:
    print(f"✗ Failed to import ContextPanel: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Unexpected error with ContextPanel: {e}")
    sys.exit(1)

print("\n✓ All checks passed! The context modules can handle missing dependencies gracefully.")