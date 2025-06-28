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
        try:
            # Check if app exists
            if not hasattr(self, 'app') or not self.app:
                logging.error("No app instance available for copy")
                return
                
            content = self.get_selected_content()
            if content:
                self._copy_to_clipboard(content)
                if hasattr(self.app, 'notify'):
                    self.app.notify(f"Copied {len(content)} characters to clipboard")
            else:
                # If no selection, copy all
                self.action_copy_all()
        except Exception as e:
            logging.error(f"Error in action_copy_selected: {e}", exc_info=True)
            if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                self.app.notify(f"Copy failed: {str(e)}", severity="error")
            
    def action_copy_all(self) -> None:
        """Copy all panel content to clipboard."""
        try:
            # Check if app exists
            if not hasattr(self, 'app') or not self.app:
                logging.error("No app instance available for copy")
                return
                
            content = self.get_copyable_content()
            if content:
                self._copy_to_clipboard(content)
                if hasattr(self.app, 'notify'):
                    self.app.notify(f"Copied all panel content ({len(content)} characters)")
            else:
                if hasattr(self.app, 'notify'):
                    self.app.notify("No content to copy", severity="warning")
        except Exception as e:
            logging.error(f"Error in action_copy_all: {e}", exc_info=True)
            if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                self.app.notify(f"Copy failed: {str(e)}", severity="error")
            
    def _copy_to_clipboard(self, content: str) -> None:
        """Copy content to system clipboard."""
        global CLIPBOARD_AVAILABLE, OSC52_AVAILABLE
        copy_success = False
        
        logging.debug(f"Attempting to copy {len(content)} characters")
        
        # Try OSC 52 first (works over SSH)
        if OSC52_AVAILABLE:
            try:
                logging.debug("Trying OSC 52 clipboard...")
                if copy_to_clipboard_osc52(content):
                    copy_success = True
                    logging.debug("OSC 52 copy succeeded")
                    if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                        self.app.notify("Copied! (OSC 52 - works over SSH)")
            except Exception as e:
                logging.warning(f"OSC 52 failed: {e}")
                pass
        
        # Try pyperclip if OSC 52 didn't work
        if not copy_success and CLIPBOARD_AVAILABLE:
            try:
                logging.debug("Trying pyperclip...")
                pyperclip.copy(content)
                copy_success = True
                logging.debug("Pyperclip copy succeeded")
            except Exception as e:
                # Pyperclip failed, will try fallback
                logging.warning(f"Pyperclip failed: {e}")
                CLIPBOARD_AVAILABLE = False  # Disable for future attempts
                pass
        
        # Try fallback if pyperclip failed or unavailable
        if not copy_success and fallback_copy:
            try:
                logging.debug("Trying fallback clipboard...")
                fallback_copy(content)
                copy_success = True
                logging.debug("Fallback copy succeeded")
                if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                    self.app.notify("Copied to file clipboard (install xclip/xsel for system clipboard)")
            except Exception as e:
                # Fallback also failed
                logging.warning(f"Fallback clipboard failed: {e}")
                pass
        
        # If copy succeeded, just return (no message posting needed)
        if copy_success:
            # Copy worked, nothing else to do
            pass
        else:
            # All methods failed - show the text in a copyable format
            if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                self.app.notify("Clipboard unavailable - text displayed below", severity="warning")
                
            # Display the text so user can manually copy
            if OSC52_AVAILABLE:
                try:
                    display_text, _ = copy_with_display(content)
                    # Log the copyable text
                    logging.info(display_text)
                    # Also try to show in the app if possible
                    if hasattr(self, 'app'):
                        # Find terminal panel and display there
                        for panel in self.app.panels.values():
                            if panel.__class__.__name__ == "TerminalPanel" and hasattr(panel, 'output'):
                                panel.output.write(display_text)
                                break
                except:
                    pass
            
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