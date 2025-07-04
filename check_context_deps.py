#!/usr/bin/env python3
"""Check context dependencies and diagnose import issues."""

import sys
import importlib.util
import traceback

def check_import(module_name, package_name=None):
    """Check if a module can be imported and report any issues."""
    if package_name is None:
        package_name = module_name
    
    print(f"\nChecking {module_name}...")
    
    # First check if the package is installed
    spec = importlib.util.find_spec(package_name.split('.')[0])
    if spec is None:
        print(f"  ❌ {package_name} is NOT installed")
        return False
    else:
        print(f"  ✓ {package_name} is installed at: {spec.origin}")
    
    # Try to actually import it
    try:
        module = importlib.import_module(module_name)
        print(f"  ✓ Successfully imported {module_name}")
        if hasattr(module, '__version__'):
            print(f"    Version: {module.__version__}")
        return True
    except Exception as e:
        print(f"  ❌ Failed to import {module_name}")
        print(f"    Error: {type(e).__name__}: {e}")
        print("    Traceback:")
        traceback.print_exc()
        return False

def check_claude_imports():
    """Check the specific imports used by Claude Code Morph."""
    print("\nChecking Claude Code Morph context imports...")
    
    try:
        print("\n1. Trying to import context_manager...")
        from claude_code_morph.context_manager import ContextManager, CHROMADB_AVAILABLE
        print(f"  ✓ Successfully imported context_manager")
        print(f"    CHROMADB_AVAILABLE = {CHROMADB_AVAILABLE}")
        
        # Check the actual availability flags
        import claude_code_morph.context_manager as cm
        print(f"    SENTENCE_TRANSFORMERS_AVAILABLE = {cm.SENTENCE_TRANSFORMERS_AVAILABLE}")
        print(f"    WATCHDOG_AVAILABLE = {cm.WATCHDOG_AVAILABLE}")
        print(f"    TIKTOKEN_AVAILABLE = {cm.TIKTOKEN_AVAILABLE}")
        print(f"    PYMUPDF_AVAILABLE = {cm.PYMUPDF_AVAILABLE}")
        
    except ImportError as e:
        print(f"  ❌ Failed to import context_manager")
        print(f"    Error: {e}")
        traceback.print_exc()
    
    try:
        print("\n2. Trying to import context_integration...")
        from claude_code_morph.context_integration import ContextIntegration, TerminalContextHelper
        print(f"  ✓ Successfully imported context_integration")
    except ImportError as e:
        print(f"  ❌ Failed to import context_integration")
        print(f"    Error: {e}")
        traceback.print_exc()

def main():
    print("Context Dependencies Diagnostic Tool")
    print("=" * 50)
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    
    # Check each dependency
    dependencies = [
        ("chromadb", None),
        ("sentence_transformers", "sentence-transformers"),
        ("watchdog", None),
        ("tiktoken", None),
        ("PyMuPDF", "pymupdf"),
        ("groq", None),
        ("openai", None),
        ("anthropic", None),
    ]
    
    results = {}
    for module_name, package_name in dependencies:
        results[module_name] = check_import(module_name, package_name)
    
    # Check Claude's specific imports
    check_claude_imports()
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY:")
    all_good = all(results.values())
    context_deps = ["chromadb", "sentence_transformers"]
    context_good = all(results.get(dep, False) for dep in context_deps)
    
    if all_good:
        print("✓ All dependencies are installed and working!")
    elif context_good:
        print("✓ Core context dependencies are working")
        print("⚠ Some optional dependencies are missing:")
        for dep, status in results.items():
            if not status and dep not in context_deps:
                print(f"  - {dep}")
    else:
        print("❌ Core context dependencies are missing or broken:")
        for dep in context_deps:
            if not results.get(dep, False):
                print(f"  - {dep}")
    
    print("\nTo install context dependencies:")
    print("  pip install -e .[context]")
    print("\nTo install all dependencies:")
    print("  pip install -e .[all]")

if __name__ == "__main__":
    main()