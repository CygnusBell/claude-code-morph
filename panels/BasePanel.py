"""Base Panel - Common functionality for all panels including copy/paste support."""

import asyncio
import logging
from typing import Optional
from textual.widgets import Static
from textual.binding import Binding
from textual.events import Click
from rich.console import Group
from rich.text import Text

# Try to import pyperclip, but fallback if not available
CLIPBOARD_AVAILABLE = False
fallback_copy = None
fallback_paste = None

try:
    import pyperclip
    # Test if pyperclip actually works, not just if it exists
    try:
        # Do a minimal test to see if clipboard is accessible
        pyperclip.determine_clipboard()
        CLIPBOARD_AVAILABLE = True
    except (pyperclip.PyperclipException, AttributeError, Exception):
        # Pyperclip is installed but can't access clipboard
        CLIPBOARD_AVAILABLE = False
except ImportError:
    # Pyperclip not installed
    CLIPBOARD_AVAILABLE = False

# Always import fallback as backup
try:
    from .clipboard_fallback import copy as fallback_copy, paste as fallback_paste
except ImportError:
    # If even fallback fails, create dummy functions
    def fallback_copy(text): 
        raise Exception("No clipboard method available")
    def fallback_paste(): 
        return ""

# Import OSC 52 clipboard support
try:
    from .osc52_clipboard import copy_to_clipboard_osc52, copy_with_display
    OSC52_AVAILABLE = True
except ImportError:
    OSC52_AVAILABLE = False

class BasePanel(Static):
    """Base panel class with common functionality including copy/paste support."""
    
    BINDINGS = [
        # Using Cmd+C for copy to match macOS convention and avoid terminal interrupt
        Binding("cmd+c", "copy_selected", "Copy", priority=True, show=True),
        Binding("cmd+shift+c", "copy_all", "Copy All", priority=True, show=True),
        # Also support Ctrl+Shift+C for non-Mac users
        Binding("ctrl+shift+c", "copy_selected", "Copy (Linux/Win)", priority=True, show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the base panel."""
        super().__init__(**kwargs)
        self.selected_text: Optional[str] = None
        self.selection_start: Optional[tuple] = None
        self.selection_end: Optional[tuple] = None
        self.is_selecting = False
        
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel.
        
        Override this method in subclasses to provide custom copy behavior.
        """
        # Default implementation returns the rendered text
        if hasattr(self, 'renderable') and self.renderable:
            # Convert renderable to plain text
            from rich.console import Console
            from io import StringIO
            
            buffer = StringIO()
            console = Console(file=buffer, force_terminal=False, width=self.size.width)
            console.print(self.renderable)
            return buffer.getvalue()
        return ""
        
    def get_selected_content(self) -> Optional[str]:
        """Get currently selected content.
        
        Override this method in subclasses for custom selection behavior.
        """
        # Default implementation returns None (no selection support)
        return self.selected_text
        
    def action_copy_selected(self) -> None:
        """Copy selected content to clipboard."""
        logging.info("Copy action triggered (Cmd+C)")
        try:
            # Check if app exists
            if not hasattr(self, 'app') or not self.app:
                logging.error("No app instance available for copy")
                return
                
            content = self.get_selected_content()
            if content:
                logging.debug(f"Copying selected content: {len(content)} characters")
                self._copy_to_clipboard(content)
            else:
                # If no selection, copy all
                logging.debug("No selection, copying all content")
                self.action_copy_all()
        except Exception as e:
            logging.error(f"Error in action_copy_selected: {e}", exc_info=True)
            if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                self.app.notify(f"Copy failed: {str(e)}", severity="error")
            
    def action_copy_all(self) -> None:
        """Copy all panel content to clipboard."""
        logging.info("Copy all action triggered (Cmd+Shift+C)")
        try:
            # Check if app exists
            if not hasattr(self, 'app') or not self.app:
                logging.error("No app instance available for copy")
                return
                
            content = self.get_copyable_content()
            if content:
                logging.debug(f"Copying all content: {len(content)} characters")
                self._copy_to_clipboard(content)
            else:
                if hasattr(self.app, 'notify'):
                    self.app.notify("No content to copy", severity="warning")
        except Exception as e:
            logging.error(f"Error in action_copy_all: {e}", exc_info=True)
            if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                self.app.notify(f"Copy failed: {str(e)}", severity="error")
            
    def _copy_to_clipboard(self, content: str) -> None:
        """Copy content to system clipboard."""
        from pathlib import Path
        
        logging.debug(f"Attempting to copy {len(content)} characters")
        
        # Always save to clipboard.txt file for easy access
        clipboard_file = Path(__file__).parent.parent / "clipboard.txt"
        try:
            with open(clipboard_file, 'w') as f:
                f.write(content)
            logging.info(f"Content saved to {clipboard_file}")
            
            # Show notification about file save
            if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                self.app.notify(f"Copied {len(content)} characters to clipboard.txt", severity="success")
            
            # Also display in terminal panel for easy selection
            if hasattr(self, 'app'):
                # Find terminal panel and display there
                for panel in self.app.panels.values():
                    if panel.__class__.__name__ == "TerminalPanel" and hasattr(panel, 'output'):
                        # RichLog widget requires markup
                        border = "─" * 60
                        panel.output.write(f"\n[bold yellow]╭{border}╮[/bold yellow]")
                        panel.output.write("[bold yellow]│ CONTENT COPIED TO clipboard.txt[/bold yellow]")
                        panel.output.write("[bold yellow]│ Select text below to copy manually:[/bold yellow]")
                        panel.output.write(f"[bold yellow]├{border}┤[/bold yellow]")
                        panel.output.write(f"[white]{content}[/white]")
                        panel.output.write(f"[bold yellow]╰{border}╯[/bold yellow]")
                        break
            
            return
            
        except Exception as e:
            logging.error(f"Failed to save clipboard content: {e}")
            if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                self.app.notify(f"Copy failed: {str(e)}", severity="error")
            
    def on_click(self, event: Click) -> None:
        """Handle mouse clicks for selection."""
        # Start selection on click
        self.selection_start = (event.x, event.y)
        self.selection_end = None
        self.is_selecting = True
        
    def on_mouse_move(self, event) -> None:
        """Handle mouse move for selection."""
        if self.is_selecting and self.selection_start:
            self.selection_end = (event.x, event.y)
            # Subclasses can override to implement visual selection
            
    def on_mouse_up(self, event) -> None:
        """Handle mouse release to end selection."""
        if self.is_selecting:
            self.is_selecting = False
            if self.selection_start and self.selection_end:
                # Subclasses can override to extract selected text
                pass