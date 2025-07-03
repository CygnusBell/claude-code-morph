"""Resizable container widget for panels with draggable splitters."""

import logging
from typing import List, Optional, Union
from textual.widget import Widget
from textual.widgets import Static
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.app import ComposeResult
from textual.events import MouseDown, MouseMove, MouseUp
from textual.geometry import Offset


class Splitter(Static):
    """A draggable splitter widget for resizing panels."""
    
    DEFAULT_CSS = """
    Splitter {
        height: 1;
        background: transparent;
        color: $surface-lighten-2;
        padding: 0;
        margin: 0 0;
    }
    
    Splitter:hover {
        color: $primary;
    }
    
    Splitter.dragging {
        color: $accent;
    }
    
    Splitter.locked {
        color: $error-darken-2;
    }
    
    Splitter .splitter-line {
        width: 1fr;
    }
    
    Splitter .lock-icon {
        width: auto;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }
    
    Splitter .lock-icon:hover {
        background: $primary;
        color: $text;
    }
    
    Splitter.locked .lock-icon {
        color: $error;
    }
    """
    
    def __init__(self, index: int, **kwargs):
        """Initialize the splitter.
        
        Args:
            index: The index of this splitter (which panels it separates)
        """
        super().__init__(**kwargs)
        self.index = index
        self.dragging = False
        self.drag_start_y = 0
        self.panel_sizes_start = []
        self.locked = False
        self.update_content()
        
    def update_content(self) -> None:
        """Update the splitter content with lock status."""
        width = max(1, self.size.width) if hasattr(self, 'size') else 40
        if self.locked:
            # Just show a simple line, let CSS handle the color
            self.update("─" * width)
            self.add_class("locked")
        else:
            self.update("─" * width)
            self.remove_class("locked")
            
    def on_mouse_down(self, event: MouseDown) -> None:
        """Start dragging on mouse down."""
        if event.button == 1:  # Left click
            logging.debug(f"Splitter {self.index} clicked, locked={self.locked}")
            # Don't allow dragging if locked
            if self.locked:
                logging.info(f"Splitter {self.index} is locked, preventing drag")
                event.stop()
                return
                
            self.dragging = True
            self.drag_start_y = event.screen_y
            self.add_class("dragging")
            
            # Capture mouse to ensure we get all mouse events
            self.capture_mouse()
            
            # Get the resizable container
            container = self.parent
            if isinstance(container, ResizableContainer):
                # Store initial panel sizes
                self.panel_sizes_start = container.panel_sizes.copy()
                
            event.stop()
            
    def on_mouse_up(self, event: MouseUp) -> None:
        """Stop dragging on mouse up."""
        if self.dragging:
            self.dragging = False
            self.remove_class("dragging")
            self.release_mouse()
            event.stop()
            
    def on_mouse_move(self, event: MouseMove) -> None:
        """Handle mouse movement while dragging."""
        if self.dragging:
            # Calculate the movement delta
            delta_y = event.screen_y - self.drag_start_y
            
            # Get the resizable container
            container = self.parent
            if isinstance(container, ResizableContainer):
                container.resize_panels(self.index, delta_y, self.panel_sizes_start)
                
            event.stop()
            
    def toggle_lock(self) -> None:
        """Toggle the lock state of this splitter."""
        self.locked = not self.locked
        self.update_content()


class ResizableContainer(Container):
    """A container that allows resizing child panels with draggable splitters."""
    
    DEFAULT_CSS = """
    ResizableContainer {
        layout: vertical;
        height: 100%;
        width: 100%;
        margin: 0;
        padding: 0;
        overflow: auto;
    }
    
    ResizableContainer > .panel-wrapper {
        width: 100%;
        height: 100%;
        overflow: hidden;
        margin: 0;
        padding: 0;
    }
    """
    
    panel_sizes: reactive[List[float]] = reactive(list)
    
    def __init__(self, **kwargs):
        """Initialize the resizable container."""
        super().__init__(**kwargs)
        self.panels: List[Widget] = []
        self.splitters: List[Splitter] = []
        self._initial_sizes: Optional[List[float]] = None
        
    def compose(self) -> ComposeResult:
        """Compose the container layout."""
        # This will be populated dynamically as panels are added
        logging.debug("ResizableContainer compose called")
        return []
        
    async def mount(self, *widgets: Union[Widget, str], **kwargs) -> List[Widget]:
        """Mount widgets as resizable panels.
        
        This overrides the default mount to add splitters between panels.
        """
        mounted_widgets = []
        
        for widget in widgets:
            if isinstance(widget, Widget):
                # Create a wrapper for the panel
                wrapper = Container(classes="panel-wrapper")
                logging.debug(f"Created wrapper for {widget} with classes {wrapper.classes}")
                # Mount the widget inside the wrapper
                await wrapper.mount(widget)
                
                # Add splitter before panel (except for the first one)
                if self.panels:
                    splitter = Splitter(len(self.splitters))
                    self.splitters.append(splitter)
                    result = await super().mount(splitter)
                    if result:
                        mounted_widgets.extend(result)
                
                # Add the panel wrapper
                self.panels.append(widget)
                result = await super().mount(wrapper)
                if result:
                    mounted_widgets.extend(result)
        
        # Initialize or update panel sizes when panels change
        if self.panels:
            self._initial_sizes = [1.0 / len(self.panels)] * len(self.panels)
            self.panel_sizes = self._initial_sizes.copy()
            logging.info(f"ResizableContainer: Set panel sizes to {self.panel_sizes}")
            
        # Apply initial sizes with a small delay to ensure layout is ready
        self.call_after_refresh(self._apply_sizes)
        
        return mounted_widgets
        
    async def remove_children(self) -> List[Widget]:
        """Remove all children and reset state."""
        removed = await super().remove_children()
        self.panels.clear()
        self.splitters.clear()
        self._initial_sizes = None
        self.panel_sizes = []
        return removed
        
    def resize_panels(self, splitter_index: int, delta_y: int, initial_sizes: List[float]) -> None:
        """Resize panels based on splitter movement.
        
        Args:
            splitter_index: Index of the splitter being dragged
            delta_y: Vertical movement delta in pixels
            initial_sizes: Panel sizes at the start of the drag
        """
        if not self.panels or len(self.panels) < 2:
            return
            
        # Get container height
        container_height = self.size.height
        if container_height <= 0:
            return
            
        # Calculate delta as a fraction of container height
        delta_fraction = delta_y / container_height
        
        # Get the panels affected by this splitter
        panel_above_idx = splitter_index
        panel_below_idx = splitter_index + 1
        
        if panel_above_idx >= len(initial_sizes) or panel_below_idx >= len(initial_sizes):
            return
            
        # Calculate new sizes based on initial sizes
        new_sizes = initial_sizes.copy()
        
        # Adjust the sizes of the two panels
        new_sizes[panel_above_idx] = initial_sizes[panel_above_idx] + delta_fraction
        new_sizes[panel_below_idx] = initial_sizes[panel_below_idx] - delta_fraction
        
        # Enforce minimum panel size (5% of container)
        min_size = 0.05
        
        if new_sizes[panel_above_idx] < min_size:
            new_sizes[panel_above_idx] = min_size
            new_sizes[panel_below_idx] = initial_sizes[panel_above_idx] + initial_sizes[panel_below_idx] - min_size
        elif new_sizes[panel_below_idx] < min_size:
            new_sizes[panel_below_idx] = min_size
            new_sizes[panel_above_idx] = initial_sizes[panel_above_idx] + initial_sizes[panel_below_idx] - min_size
            
        # Update panel sizes
        self.panel_sizes = new_sizes
        self._apply_sizes()
        
    def _apply_sizes(self) -> None:
        """Apply the current panel sizes to the actual widgets."""
        logging.info(f"_apply_sizes called - panels: {len(self.panels)}, sizes: {self.panel_sizes}")
        if not self.panels or not self.panel_sizes:
            logging.info("_apply_sizes: No panels or panel_sizes yet - container is empty")
            return
            
        # Get all panel wrappers
        wrappers = self.query(".panel-wrapper")
        logging.info(f"Found {len(wrappers)} panel wrappers")
        
        for i, (wrapper, size) in enumerate(zip(wrappers, self.panel_sizes)):
            # Use fr units for better layout
            # Each panel gets proportional height based on its size
            wrapper.styles.height = f"{size:.2f}fr"
            
            logging.info(f"Panel {i} height set to {size:.2f}fr - wrapper: {wrapper}")
            # Force refresh of the wrapper
            wrapper.refresh(layout=True)
            
    def on_resize(self, event) -> None:
        """Handle container resize events."""
        # Reapply sizes when the container is resized
        self._apply_sizes()
        # Update splitter content to ensure proper width
        for splitter in self.splitters:
            splitter.update_content()