"""Widget Label - A floating label widget for displaying information on hover."""

from textual.widgets import Label
from textual.app import ComposeResult
from textual.timer import Timer
from textual.events import MouseMove, Enter, Leave
from typing import Optional, List, Tuple, ClassVar


class WidgetLabel(Label):
    """A floating label that appears on widget hover to show information."""
    
    # Class-level registry of all active labels for overlap detection
    _active_labels: ClassVar[List['WidgetLabel']] = []
    
    DEFAULT_CSS = """
    WidgetLabel {
        background: $surface;
        color: $text;
        border: tall $primary;
        padding: 0 1;
        height: auto;
        width: auto;
        layer: overlay;
        display: none;
    }
    
    WidgetLabel.visible {
        display: block;
    }
    """
    
    def __init__(self, text: str = "", auto_hide_seconds: float = 3.0, **kwargs):
        """Initialize the widget label.
        
        Args:
            text: The text to display in the label
            auto_hide_seconds: Seconds before auto-hiding (default: 3.0)
            **kwargs: Additional arguments to pass to Label
        """
        super().__init__(text, **kwargs)
        self.add_class("widget-label")
        self.auto_hide_seconds = auto_hide_seconds
        self._hide_timer: Optional[Timer] = None
        self._actual_position: Optional[Tuple[int, int]] = None
        
    def show(self) -> None:
        """Show the widget label and start the auto-hide timer."""
        self.add_class("visible")
        self._reset_hide_timer()
        # Add to active labels registry
        if self not in WidgetLabel._active_labels:
            WidgetLabel._active_labels.append(self)
        
    def hide(self) -> None:
        """Hide the widget label and cancel any pending timer."""
        self.remove_class("visible")
        self._cancel_hide_timer()
        # Remove from active labels registry
        if self in WidgetLabel._active_labels:
            WidgetLabel._active_labels.remove(self)
        
    def _reset_hide_timer(self) -> None:
        """Reset the auto-hide timer."""
        # Cancel existing timer if any
        self._cancel_hide_timer()
        
        # Start new timer if auto-hide is enabled
        if self.auto_hide_seconds > 0:
            self._hide_timer = self.set_timer(
                self.auto_hide_seconds,
                self.hide
            )
            
    def _cancel_hide_timer(self) -> None:
        """Cancel the auto-hide timer if it's running."""
        if self._hide_timer:
            self._hide_timer.stop()
            self._hide_timer = None
    
    def calculate_label_position(self, widget_x: int, widget_y: int, 
                               widget_width: int, widget_height: int) -> tuple[int, int]:
        """Calculate the optimal position for the label near a widget.
        
        The label will be positioned:
        - To the right of the widget if there's space
        - To the left if right side doesn't have space
        - Below the widget if horizontal space is insufficient
        - Above the widget if below doesn't have space
        
        Also checks for overlaps with existing labels and adjusts position accordingly.
        
        Args:
            widget_x: X coordinate of the target widget
            widget_y: Y coordinate of the target widget
            widget_width: Width of the target widget
            widget_height: Height of the target widget
            
        Returns:
            A tuple of (x, y) coordinates for the label position
        """
        if not self.screen:
            return (widget_x, widget_y)
            
        # Get screen dimensions
        screen_width = self.screen.size.width
        screen_height = self.screen.size.height
        
        # Get label dimensions (estimate if not rendered yet)
        # Account for border and padding from CSS
        label_width = self.size.width if self.size.width > 0 else len(str(self.renderable)) + 4
        label_height = self.size.height if self.size.height > 0 else 3
        
        # Calculate widget bounds
        widget_right = widget_x + widget_width
        widget_bottom = widget_y + widget_height
        
        # Preferred offset from widget
        offset_margin = 2
        
        # Generate candidate positions in order of preference
        candidate_positions = [
            # Right side (centered vertically)
            (widget_right + offset_margin, widget_y + max(0, (widget_height - label_height) // 2)),
            # Left side (centered vertically)
            (widget_x - label_width - offset_margin, widget_y + max(0, (widget_height - label_height) // 2)),
            # Below (left aligned)
            (widget_x, widget_bottom + offset_margin),
            # Above (left aligned)
            (widget_x, widget_y - label_height - offset_margin),
            # Top-right corner with offset
            (min(widget_right + offset_margin, screen_width - label_width), 
             max(widget_y - label_height - offset_margin, 0)),
            # Bottom-right corner with offset
            (min(widget_right + offset_margin, screen_width - label_width),
             min(widget_bottom + offset_margin, screen_height - label_height)),
            # Top-left corner with offset
            (max(widget_x - label_width - offset_margin, 0),
             max(widget_y - label_height - offset_margin, 0)),
            # Bottom-left corner with offset
            (max(widget_x - label_width - offset_margin, 0),
             min(widget_bottom + offset_margin, screen_height - label_height))
        ]
        
        # Find first position that doesn't overlap with other labels
        chosen_x, chosen_y = candidate_positions[0]
        
        for x, y in candidate_positions:
            # Check if position is within screen bounds
            if x < 0 or y < 0 or x + label_width > screen_width or y + label_height > screen_height:
                continue
                
            # Check for overlaps with other active labels
            has_overlap = False
            for other_label in WidgetLabel._active_labels:
                if other_label is self or not other_label._actual_position:
                    continue
                    
                other_x, other_y = other_label._actual_position
                other_width = other_label.size.width if other_label.size.width > 0 else len(str(other_label.renderable)) + 4
                other_height = other_label.size.height if other_label.size.height > 0 else 3
                
                # Check for rectangle overlap
                if (x < other_x + other_width and 
                    x + label_width > other_x and
                    y < other_y + other_height and
                    y + label_height > other_y):
                    has_overlap = True
                    break
                    
            if not has_overlap:
                chosen_x, chosen_y = x, y
                break
        
        # If all positions overlap, try to find a free spot by offsetting
        if has_overlap:
            # Try offsetting vertically from the best position
            for offset in range(1, 10):
                test_y = chosen_y + (offset * label_height)
                if test_y + label_height <= screen_height:
                    has_overlap = False
                    for other_label in WidgetLabel._active_labels:
                        if other_label is self or not other_label._actual_position:
                            continue
                        other_x, other_y = other_label._actual_position
                        other_width = other_label.size.width if other_label.size.width > 0 else len(str(other_label.renderable)) + 4
                        other_height = other_label.size.height if other_label.size.height > 0 else 3
                        
                        if (chosen_x < other_x + other_width and 
                            chosen_x + label_width > other_x and
                            test_y < other_y + other_height and
                            test_y + label_height > other_y):
                            has_overlap = True
                            break
                            
                    if not has_overlap:
                        chosen_y = test_y
                        break
        
        # Final bounds checking to ensure label stays on screen
        chosen_x = max(0, min(chosen_x, screen_width - label_width))
        chosen_y = max(0, min(chosen_y, screen_height - label_height))
        
        # Store the actual position for overlap detection
        self._actual_position = (chosen_x, chosen_y)
        
        return (chosen_x, chosen_y)
            
    def on_enter(self, event: Enter) -> None:
        """Reset timer when mouse enters the label."""
        if self.has_class("visible"):
            self._reset_hide_timer()
            
    def on_mouse_move(self, event: MouseMove) -> None:
        """Reset timer on mouse movement within the label."""
        if self.has_class("visible"):
            self._reset_hide_timer()
            
    def on_unmount(self) -> None:
        """Clean up timer when widget is unmounted."""
        self._cancel_hide_timer()
        # Remove from active labels registry
        if self in WidgetLabel._active_labels:
            WidgetLabel._active_labels.remove(self)
        super().on_unmount()