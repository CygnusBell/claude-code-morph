#!/usr/bin/env python3
"""Simple test to verify the TUI works."""

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label

class SimpleApp(App):
    """A simple test app."""
    
    def compose(self) -> ComposeResult:
        yield Header()
        yield Label("If you can see this, Textual is working!", id="test")
        yield Footer()
        
    def on_mount(self) -> None:
        self.notify("App started successfully!")

if __name__ == "__main__":
    app = SimpleApp()
    app.run()