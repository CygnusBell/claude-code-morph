#!/usr/bin/env python3
"""Test script to verify resizable panels functionality."""

from textual.app import App, ComposeResult
from textual.widgets import Static, Header, Footer
from widgets.resizable import ResizableContainer


class TestPanel(Static):
    """Simple test panel."""
    
    def __init__(self, content: str, color: str = "blue", **kwargs):
        super().__init__(content, **kwargs)
        self.border_title = content
        self.styles.border = ("solid", color)
        self.styles.height = "100%"
        

class ResizeTestApp(App):
    """Test app for resizable panels."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    """
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        container = ResizableContainer(id="test-container")
        yield container
        
        yield Footer()
        
    async def on_mount(self) -> None:
        """Mount test panels."""
        container = self.query_one("#test-container", ResizableContainer)
        
        # Add three test panels
        await container.mount(
            TestPanel("Panel 1 - Drag the splitters to resize", "red"),
            TestPanel("Panel 2 - This panel can be resized", "green"),
            TestPanel("Panel 3 - Minimum size is 5% of container", "blue")
        )
        

if __name__ == "__main__":
    app = ResizeTestApp()
    app.run()