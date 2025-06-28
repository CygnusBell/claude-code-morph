"""Fallback clipboard functionality when system clipboard is not available."""

import os
from pathlib import Path

class FallbackClipboard:
    """Simple file-based clipboard fallback."""
    
    def __init__(self):
        self.clipboard_file = Path.home() / ".claude_code_morph_clipboard"
    
    def copy(self, text: str) -> None:
        """Copy text to fallback clipboard."""
        try:
            with open(self.clipboard_file, 'w', encoding='utf-8') as f:
                f.write(text)
        except Exception as e:
            raise Exception(f"Failed to write to clipboard file: {e}")
    
    def paste(self) -> str:
        """Paste text from fallback clipboard."""
        try:
            if self.clipboard_file.exists():
                with open(self.clipboard_file, 'r', encoding='utf-8') as f:
                    return f.read()
            return ""
        except Exception as e:
            raise Exception(f"Failed to read from clipboard file: {e}")

# Global instance
_fallback_clipboard = FallbackClipboard()

def copy(text: str) -> None:
    """Copy text to clipboard."""
    _fallback_clipboard.copy(text)

def paste() -> str:
    """Paste text from clipboard."""
    return _fallback_clipboard.paste()