#!/usr/bin/env python3
"""Test script to verify lock icons are present in panel title bars."""

import asyncio
from textual.app import App
from textual.widgets import Button
from panels.BasePanel import BasePanel
from panels.PromptPanel import PromptPanel
from panels.RobustTerminalPanel import RobustTerminalPanel
from widgets.resizable import ResizableContainer


class TestApp(App):
    """Test app to verify lock functionality."""
    
    async def on_mount(self):
        """Check panels after mount."""
        await asyncio.sleep(0.5)  # Let UI settle
        
        # Find all panels
        panels = self.query(BasePanel)
        print(f"\nFound {len(panels)} panels:")
        
        for panel in panels:
            panel_name = panel.__class__.__name__
            
            # Check for lock button
            lock_buttons = panel.query(".lock-button")
            if lock_buttons:
                button = lock_buttons.first()
                icon = button.label
                print(f"  ✓ {panel_name}: Has lock button with icon '{icon}'")
            else:
                print(f"  ✗ {panel_name}: No lock button found!")
                
        # Test lock functionality
        if panels:
            test_panel = panels.first()
            print(f"\nTesting lock toggle on {test_panel.__class__.__name__}:")
            
            # Initial state
            print(f"  Initial locked state: {test_panel.is_locked}")
            
            # Toggle lock
            test_panel.toggle_lock()
            print(f"  After toggle: {test_panel.is_locked}")
            
            # Check button update
            lock_button = test_panel.query_one(".lock-button", Button)
            print(f"  Button icon: '{lock_button.label}'")
            
        self.exit()
    
    def compose(self):
        """Create test layout."""
        container = ResizableContainer()
        container.add_panel(PromptPanel())
        container.add_panel(RobustTerminalPanel())
        yield container


if __name__ == "__main__":
    app = TestApp()
    app.run()