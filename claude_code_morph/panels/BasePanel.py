"""Base Panel - Common functionality for all panels including copy/paste support."""

import asyncio
import logging
from typing import Optional, Dict, Any
from textual.widgets import Static, Button
from textual.binding import Binding
from textual.events import Click, MouseDown
from textual.app import ComposeResult
from textual.containers import Horizontal, Container
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
    
    DEFAULT_CSS = """
    BasePanel {
        layout: vertical;
        margin: 0;
        padding: 0;
    }
    
    .panel-header {
        height: 1;
        background: $boost;
        padding: 0 1;
        layout: horizontal;
        align: center middle;
    }
    
    .panel-name {
        width: 1fr;
        text-align: left;
        color: $text-muted;
        text-style: italic;
    }
    
    Button.gear-button {
        width: 3;
        height: 1;
        margin: 0;
        padding: 0 1;
        background: transparent;
        color: $text-muted;
        content-align: center middle;
        text-align: center;
        text-style: bold;
        border: none;
    }
    
    Button.gear-button:hover {
        color: $primary;
        background: transparent;
    }
    
    .gear-container {
        width: auto;
        height: 1;
        margin: 0;
        padding: 0;
    }
    
    .context-menu {
        width: 20;
        height: 5;
        background: red;
        border: solid white;
        display: none;
        layer: overlay;
        offset-y: 2;
        offset-x: -15;
    }
    
    .context-menu.visible {
        display: block;
    }
    
    .context-menu-item {
        width: 100%;
        height: 3;
        background: blue;
        color: white;
    }
    
    .context-menu-item:hover {
        background: $primary;
        color: $text;
    }
    
    """
    
    # Ensure BasePanel CSS is always included
    CSS = DEFAULT_CSS
    
    BINDINGS = [
        # Using Cmd+C for copy to match macOS convention and avoid terminal interrupt
        Binding("cmd+c", "copy_selected", "Copy", priority=True, show=True),
        Binding("cmd+shift+c", "copy_all", "Copy All", priority=True, show=True),
        # Also support Ctrl+Shift+C for non-Mac users
        Binding("ctrl+shift+c", "copy_selected", "Copy (Linux/Win)", priority=True, show=False),
        # Add lock toggle shortcut
        Binding("ctrl+l", "toggle_lock", "Lock/Unlock", priority=True, show=True),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the base panel."""
        super().__init__(**kwargs)
        self.selected_text: Optional[str] = None
        self.selection_start: Optional[tuple] = None
        self.selection_end: Optional[tuple] = None
        self.is_selecting = False
        self.is_locked = False
        
    def compose(self) -> ComposeResult:
        """Create the base panel layout with panel name."""
        # Add panel header with name
        with Horizontal(classes="panel-header"):
            yield Static(f"{self.__class__.__name__}", classes="panel-name")
            # Container for gear button and its dropdown menu
            with Container(classes="gear-container"):
                self.gear_button = Button("⚙", classes="gear-button")
                yield self.gear_button
                
                # Context menu (initially hidden) - positioned as dropdown
                with Container(classes="context-menu") as self.context_menu:
                    lock_text = "🔓 Lock" if not self.is_locked else "🔒 Unlock"
                    yield Button(lock_text, classes="context-menu-item", id="lock-btn")
        
        # Subclasses should override compose_content to add their content
        if hasattr(self, 'compose_content'):
            yield from self.compose_content()
    
    def compose_content(self) -> ComposeResult:
        """Override this method in subclasses to add panel content."""
        # Default empty implementation
        return []
        
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
                
    def on_mount(self) -> None:
        """Set up event handlers when panel is mounted."""
        # Nothing needed here - Button widget handles clicks automatically
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button == self.gear_button:
            logging.info("Gear button clicked!")
            self.toggle_context_menu()
            event.stop()
        elif event.button.id == "lock-btn":
            self.toggle_lock()
            self.hide_context_menu()
            event.stop()
            
    def on_click(self, event: Click) -> None:
        """Handle click events."""
        # Hide context menu if clicking outside
        if hasattr(self, 'context_menu') and self.context_menu.has_class('visible'):
            # Check if click is outside the context menu AND not on the gear button
            if (not self.context_menu.region.contains(event.x, event.y) and 
                not self.gear_button.region.contains(event.x, event.y)):
                self.hide_context_menu()
                
    def toggle_context_menu(self) -> None:
        """Toggle the visibility of the context menu."""
        if self.context_menu.has_class('visible'):
            self.context_menu.remove_class('visible')
            logging.info("Context menu hidden")
        else:
            self.context_menu.add_class('visible')
            # Debug the menu structure
            logging.info(f"Context menu shown, children: {list(self.context_menu.children)}")
            logging.info(f"Context menu classes: {self.context_menu.classes}")
            logging.info(f"Context menu styles: {self.context_menu.styles}")
            # Check button visibility
            lock_btn = self.query_one("#lock-btn", Button)
            if lock_btn:
                logging.info(f"Lock button found - label: {lock_btn.label}, visible: {lock_btn.visible}, display: {lock_btn.styles.display}")
            
    def hide_context_menu(self) -> None:
        """Hide the context menu."""
        if hasattr(self, 'context_menu'):
            self.context_menu.remove_class('visible')
            
    def action_toggle_lock(self) -> None:
        """Action to toggle lock via keyboard shortcut."""
        self.toggle_lock()
            
    def toggle_lock(self, event=None) -> None:
        """Toggle the lock state of this panel."""
        self.is_locked = not self.is_locked
        logging.info(f"Panel {type(self).__name__} lock toggled: is_locked={self.is_locked}")
        
        # Update lock button text
        lock_btn = self.query_one("#lock-btn", Button)
        if lock_btn:
            lock_text = "🔓 Lock" if not self.is_locked else "🔒 Unlock"
            lock_btn.label = lock_text
                
        # Update all splitters connected to this panel
        self._update_connected_splitters()
        
        # Notify user
        if hasattr(self, 'app') and hasattr(self.app, 'notify'):
            state = "locked" if self.is_locked else "unlocked"
            self.app.notify(f"Panel {state}", severity="information")
            
    def _update_connected_splitters(self) -> None:
        """Update the lock state of splitters connected to this panel."""
        # Import here to avoid circular import
        try:
            from ..widgets.resizable import ResizableContainer
        except ImportError:
            # Fallback for dynamic loading
            import sys
            from pathlib import Path
            widgets_path = Path(__file__).parent.parent / "widgets"
            if str(widgets_path) not in sys.path:
                sys.path.insert(0, str(widgets_path))
            from resizable import ResizableContainer
        
        # Find the ResizableContainer ancestor
        # The panel is wrapped in a Container, so we need to traverse up
        container = self.parent
        logging.debug(f"Looking for ResizableContainer, starting from {type(container)}")
        
        # Skip the wrapper Container
        if container and container.has_class("panel-wrapper"):
            container = container.parent
            logging.debug(f"Skipped wrapper, now at: {type(container) if container else 'None'}")
            
        # Check if we need to continue searching - use class name comparison due to dynamic loading
        found = False
        if container and type(container).__name__ == "ResizableContainer":
            logging.debug("Found ResizableContainer immediately after skipping wrapper")
            found = True
            
        if not found:
            # Otherwise traverse up until we find ResizableContainer
            while container and type(container).__name__ != "ResizableContainer":
                container = container.parent
                logging.debug(f"Checking parent: {type(container) if container else 'None'}")
                if container and type(container).__name__ == "ResizableContainer":
                    logging.debug("Found ResizableContainer after traversal")
                    found = True
            
        if container and type(container).__name__ == "ResizableContainer":
            # Find this panel's index in the container's panels list
            panel_index = -1
            logging.debug(f"Looking for {self} ({type(self).__name__}) in panels list")
            for i, panel in enumerate(container.panels):
                logging.debug(f"  Panel {i}: {panel} ({type(panel).__name__})")
                if panel == self:
                    panel_index = i
                    break
            
            logging.debug(f"Found panel at index {panel_index} in container with {len(container.panels)} panels")
            logging.debug(f"Container has {len(container.splitters)} splitters")
                    
            if panel_index >= 0:
                # Update ALL splitters based on ALL panels' lock states
                for i, splitter in enumerate(container.splitters):
                    # A splitter at index i is between panels i and i+1
                    panel_above_locked = False
                    panel_below_locked = False
                    
                    # Get the panels connected to this splitter
                    if i < len(container.panels) - 1:
                        panel_above = container.panels[i]
                        panel_below = container.panels[i + 1]
                        
                        if hasattr(panel_above, 'is_locked'):
                            panel_above_locked = panel_above.is_locked
                        if hasattr(panel_below, 'is_locked'):
                            panel_below_locked = panel_below.is_locked
                            
                    # Lock splitter if either connected panel is locked
                    splitter.locked = panel_above_locked or panel_below_locked
                    splitter.update_content()
                    logging.debug(f"Updated splitter {i}: locked={splitter.locked} (above={panel_above_locked}, below={panel_below_locked})")
                    
                # No need to update other panels' UI as we're using a gear menu now
        else:
            logging.warning(f"Could not find ResizableContainer for panel {self}")