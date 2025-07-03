"""Base Panel - Common functionality for all panels including copy/paste support."""

import asyncio
import logging
from typing import Optional, Dict, Any
from textual.widgets import Static, Button
from textual.binding import Binding
from textual.events import Click, MouseDown, Leave, Enter
from textual.app import ComposeResult
from textual.containers import Horizontal, Container
from textual.coordinate import Coordinate
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
        height: 100%;
        width: 100%;
        margin: 0;
        padding: 0;
        overflow: auto;
        background: $surface;
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
    
    /* Widget Label Styles */
    .widget-label {
        background: rgba(0, 0, 0, 0.85);
        color: rgba(255, 255, 255, 0.95);
        padding: 1 2;
        
        text-align: left;
        text-style: none;
        opacity: 0;
        
        layer: overlay;
        
        width: auto;
        height: auto;
        max-width: 60;
        
    }
    
    .widget-label.visible {
        opacity: 1;
    }
    
    .widget-label.fade-in {
        opacity: 1;
    }
    
    .widget-label.fade-out {
        opacity: 0;
    }
    
    /* Position labels at top-right of widgets */
    .widget-label.top-right {
        dock: top;
        align: right top;
        margin: 1 1 0 0;
    }
    
    /* Position labels at top-left of widgets */
    .widget-label.top-left {
        dock: top;
        align: left top;
        margin: 1 0 0 1;
    }
    
    /* Centered label style */
    .widget-label.centered {
        dock: top;
        align: center top;
        margin: 1 0 0 0;
    }
    
    /* Alternative label styles */
    .widget-label.minimal {
        background: rgba(0, 0, 0, 0.5);
        padding: 0 1;
        
        text-style: none;
    }
    
    .widget-label.accent {
        background: rgba(30, 144, 255, 0.8);
        color: white;
        text-style: bold;
    }
    
    .widget-label.warning {
        background: rgba(255, 165, 0, 0.8);
        color: black;
        text-style: bold;
    }
    
    /* Widget type specific label styles */
    .widget-label.button-label {
        background: rgba(46, 204, 113, 0.8);  /* Green */
        color: white;
        text-style: bold;
        
    }
    
    .widget-label.input-label {
        background: rgba(52, 152, 219, 0.8);  /* Blue */
        color: white;
        text-style: none;
        
    }
    
    .widget-label.panel-label {
        background: rgba(155, 89, 182, 0.8);  /* Purple */
        color: white;
        text-style: italic;
        
    }
    
    .widget-label.text-label {
        background: rgba(241, 196, 15, 0.8);  /* Yellow */
        color: black;
        text-style: none;
        
    }
    
    .widget-label.container-label {
        background: rgba(189, 195, 199, 0.8);  /* Gray */
        color: black;
        text-style: italic;
        
    }
    
    """
    
    # Ensure BasePanel CSS is always included
    CSS = DEFAULT_CSS
    
    BINDINGS = [
        # Using Cmd+C for copy to match macOS convention and avoid terminal interrupt
        Binding("cmd+c", "copy_selected", "Copy", priority=True, show=False),
        Binding("cmd+shift+c", "copy_all", "Copy All", priority=True, show=False),
        # Also support Ctrl+Shift+C for non-Mac users
        Binding("ctrl+shift+c", "copy_selected", "Copy (Linux/Win)", priority=True, show=False),
        # Add lock toggle shortcut
        Binding("ctrl+l", "toggle_lock", "Lock/Unlock", priority=True, show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the base panel."""
        super().__init__(**kwargs)
        self.selected_text: Optional[str] = None
        self.selection_start: Optional[tuple] = None
        self.selection_end: Optional[tuple] = None
        self.is_selecting = False
        self.is_locked = False
        self.hovered_widget = None
        self.hover_label = None
        self.widget_label = None
        
    def is_morph_mode_active(self) -> bool:
        """Check if Morph Mode is currently active."""
        if hasattr(self, 'app') and self.app:
            # Look for PromptPanel and check if morph mode is active
            try:
                for widget in self.app.query("PromptPanel"):
                    if hasattr(widget, 'selected_mode') and widget.selected_mode == "morph":
                        logging.debug(f"Morph mode is active: {widget.selected_mode}")
                        return True
                logging.debug("Morph mode is not active")
            except Exception as e:
                logging.debug(f"Error checking morph mode: {e}")
        return False
        
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
        """Handle mouse move for selection and widget hover detection."""
        # Handle selection
        if self.is_selecting and self.selection_start:
            self.selection_end = (event.x, event.y)
            # Subclasses can override to implement visual selection
            
        # Handle widget hover detection
        if self.is_morph_mode_active():
            # Convert event coordinates to screen coordinates
            screen_x = event.screen_x if hasattr(event, 'screen_x') else event.x
            screen_y = event.screen_y if hasattr(event, 'screen_y') else event.y
            
            # Use screen coordinates for widget detection
            self._check_widget_hover(screen_x, screen_y)
            
            # Debug log
            if hasattr(self, '_last_log_time'):
                import time
                if time.time() - self._last_log_time > 1:  # Log once per second
                    logging.info(f"Mouse move in morph mode at panel:({event.x}, {event.y}) screen:({screen_x}, {screen_y})")
                    self._last_log_time = time.time()
            else:
                import time
                self._last_log_time = time.time()
            
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
            
            
    def get_widget_info(self, widget=None) -> str:
        """Get formatted information about a widget.
        
        Args:
            widget: The widget to get info about. If None, uses self.
            
        Returns:
            A formatted string containing the widget's path in the DOM tree and other info.
        """
        if widget is None:
            widget = self
            
        # Build the DOM path by traversing up the widget hierarchy
        path_parts = []
        current = widget
        
        while current is not None:
            # Build identifier for current widget
            identifier = current.__class__.__name__
            
            # Add ID if present
            if hasattr(current, 'id') and current.id:
                identifier += f"#{current.id}"
                
            # Add CSS classes if present (limit to 2 for brevity)
            if hasattr(current, 'classes') and current.classes:
                classes = list(current.classes)[:2]
                if classes:
                    identifier += "." + ".".join(classes)
                if len(current.classes) > 2:
                    identifier += "..."
                    
            path_parts.append(identifier)
            
            # Move up to parent
            if hasattr(current, 'parent'):
                current = current.parent
                # Stop at the app level to avoid too long paths
                if hasattr(current, '__class__') and current.__class__.__name__ == 'ClaudeCodeMorph':
                    break
            else:
                break
                
        # Reverse to show top-down path
        path_parts.reverse()
        
        # Create the path string
        dom_path = " > ".join(path_parts)
        
        # Also include additional details about the target widget
        info_parts = [f"Path: {dom_path}"]
        
        # Add widget dimensions if available
        if hasattr(widget, 'region'):
            region = widget.region
            info_parts.append(f"Size: {region.width}x{region.height}")
            info_parts.append(f"Position: ({region.x}, {region.y})")
        
        # Format as a multi-line string for better readability
        return "\n".join(info_parts)
    
            
    def _check_widget_hover(self, x: int, y: int) -> None:
        """Check if mouse is hovering over a widget and show label if in Morph Mode."""
        if not self.is_morph_mode_active():
            return
            
        # Log what we're looking for
        logging.debug(f"Looking for widget at screen position ({x}, {y})")
            
        # Find the most specific widget at the mouse position
        # Start with children and work our way down to find the deepest visible widget
        candidates = []
        
        def check_widget_at_position(w, depth=0):
            """Recursively check if widget contains position and track depth."""
            if hasattr(w, 'region') and w.visible:
                region = w.region
                # Region coordinates are screen coordinates
                if (region.x <= x < region.x + region.width and
                    region.y <= y < region.y + region.height):
                    # Add this widget as a candidate
                    candidates.append((depth, w))
                    # Check its children for deeper matches
                    if hasattr(w, 'children'):
                        for child in w.children:
                            check_widget_at_position(child, depth + 1)
        
        # Start checking from this panel's children
        for child in self.children:
            check_widget_at_position(child)
        
        # Also check the panel itself
        check_widget_at_position(self)
        
        # Sort by depth (deepest first) and pick the most specific widget
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Debug: log candidates
        if candidates:
            logging.info(f"Found {len(candidates)} widget candidates at position ({x}, {y})")
            for depth, w in candidates[:5]:  # Log top 5
                w_id = getattr(w, 'id', 'no-id')
                w_region = getattr(w, 'region', 'no-region')
                logging.info(f"  Depth {depth}: {w.__class__.__name__} (id={w_id}) region={w_region}")
        else:
            logging.debug(f"No widget candidates found at position ({x}, {y})")
        
        # Find the most relevant widget (skip pure containers without IDs)
        widget = None
        for depth, candidate in candidates:
            # Skip generic containers ONLY if they have no ID AND no classes
            # But always include containers with IDs (like queue-container)
            if (candidate.__class__.__name__ in ['Container', 'Horizontal', 'Vertical', 'ScrollableContainer'] and 
                not getattr(candidate, 'id', None) and 
                not getattr(candidate, 'classes', set())):
                logging.debug(f"Skipping container without ID or classes: {candidate}")
                continue
            widget = candidate
            break
        
        # If we're hovering over a different widget or no widget
        if widget != self.hovered_widget:
            # Remove previous label if it exists
            if self.hover_label:
                self.hover_label.remove()
                self.hover_label = None
                
            self.hovered_widget = widget
            
            # Show label for the new widget (but not for the panel itself)
            if widget and widget != self:
                self._show_widget_label(widget, x, y)
                
    def _show_widget_label(self, widget, x: int, y: int) -> None:
        """Show a label for the hovered widget."""
        if not widget:
            return
            
        # Track the hovered widget
        self.hovered_widget = widget
            
        # Get widget type and basic info
        widget_type = widget.__class__.__name__
        widget_id = getattr(widget, 'id', None)
        widget_classes = list(widget.classes) if hasattr(widget, 'classes') else []
        
        # Build label parts
        label_parts = [widget_type]
        
        # Add ID if present
        if widget_id:
            label_parts.append(f"#{widget_id}")
            
        # Add classes if present
        if widget_classes:
            class_str = '.'.join(widget_classes[:2])  # Limit to 2 classes
            if len(widget_classes) > 2:
                class_str += "..."
            label_parts.append(f".{class_str}")
            
        # Add widget-specific info
        extra_info = []
        
        # For buttons, show the label
        if widget_type == "Button" and hasattr(widget, 'label'):
            extra_info.append(f'"{widget.label}"')
            
        # For text areas, show character count
        elif widget_type == "TextArea" and hasattr(widget, 'text'):
            char_count = len(widget.text)
            extra_info.append(f"{char_count} chars")
            
        # For labels/static widgets, show truncated content
        elif widget_type in ["Label", "Static"] and hasattr(widget, 'renderable'):
            content = str(widget.renderable)[:20]
            if len(str(widget.renderable)) > 20:
                content += "..."
            extra_info.append(f'"{content}"')
            
        # Combine all parts
        label_text = ' '.join(label_parts)
        if extra_info:
            label_text += f" ({', '.join(extra_info)})"
            
        # For now, use notifications to verify the hover detection is working
        logging.info(f"Showing widget label: {label_text}")
        if hasattr(self, 'app') and hasattr(self.app, 'notify'):
            # Use a shorter timeout so notifications don't stack up
            self.app.notify(label_text, severity="information", timeout=1)
            
        # TODO: Implement actual floating label widget
        # self.hover_label = WidgetLabel(label_text, auto_hide_seconds=0)
        # ...
                
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
            
    def show_widget_label(self, widget, text: str, position: Optional[Coordinate] = None) -> None:
        """Show a widget label with the specified text.
        
        Args:
            widget: The widget to show the label for
            text: The text to display in the label
            position: Optional position for the label. If not provided, will position near the widget
        """
        # Lazily import WidgetLabel to avoid circular imports
        try:
            from ..widgets.widget_label import WidgetLabel
        except ImportError:
            # Fallback for when module is loaded dynamically
            from claude_code_morph.widgets.widget_label import WidgetLabel
        
        # Remove any existing widget label
        if self.widget_label:
            try:
                self.widget_label.remove()
            except Exception:
                pass
            self.widget_label = None
            
        # Create and mount new widget label
        self.widget_label = WidgetLabel(text)
        
        # Get the app's screen to mount the label at the overlay layer
        if hasattr(self, 'app') and self.app and hasattr(self.app, 'screen'):
            # Mount the label to the screen's overlay layer
            self.app.screen.mount(self.widget_label, layer="overlay")
            
            # Position the label
            if position:
                # Use provided position
                self.widget_label.styles.offset = (position.x, position.y)
            else:
                # Position near the widget
                widget_region = widget.region
                # Position above the widget by default
                label_x = widget_region.x + (widget_region.width // 2)
                label_y = widget_region.y - 2  # 2 lines above the widget
                
                # Adjust if too close to top
                if label_y < 0:
                    label_y = widget_region.y + widget_region.height + 1  # Below widget instead
                    
                self.widget_label.styles.offset = (label_x, label_y)
                
            # Make the label visible and start auto-hide timer
            self.widget_label.show()
            
    def hide_widget_label(self) -> None:
        """Hide and remove the current widget label."""
        if self.widget_label:
            try:
                self.widget_label.remove()
            except Exception:
                pass
            self.widget_label = None
            
    def on_enter(self, event: Enter) -> None:
        """Handle mouse enter events on widgets."""
        # Enter/Leave events don't have widget attribute in Textual
        # This functionality would need to be implemented differently
        pass
            
    def on_leave(self, event: Leave) -> None:
        """Handle mouse leave events on widgets."""
        # Enter/Leave events don't have widget attribute in Textual
        # This functionality would need to be implemented differently
        pass
