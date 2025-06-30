#!/usr/bin/env python3
"""Test script to debug terminal display issues."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.containers import Vertical
from textual.widgets import Static, Button
from claude_code_morph.panels.TerminalPanel import TerminalPanel
import asyncio
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_terminal.log'),
        logging.StreamHandler()
    ]
)

class TestTerminalApp(App):
    """Simple app to test the terminal panel."""
    
    CSS = """
    Screen {
        background: #1a1a1a;
    }
    
    #test-button {
        dock: top;
        height: 3;
        margin: 1;
    }
    """
    
    def compose(self):
        yield Button("Send Test Prompt", id="test-button")
        yield TerminalPanel(id="terminal")
        
    async def on_mount(self):
        """Set up the app when mounted."""
        self.terminal = self.query_one(TerminalPanel)
        
    async def on_button_pressed(self, event):
        """Send a test prompt when button is pressed."""
        test_prompt = "What is 2 + 2?"
        logging.info(f"Sending test prompt: {test_prompt}")
        await self.terminal.send_prompt(test_prompt, mode="develop")
        
        # Wait a bit and check the display
        await asyncio.sleep(2)
        widget = self.terminal.terminal_widget
        if widget and widget.term_screen:
            logging.info(f"Terminal cursor position: y={widget.term_screen.cursor.y}, x={widget.term_screen.cursor.x}")
            # Log first few lines
            for y in range(min(10, widget.term_screen.lines)):
                line = ""
                for x in range(widget.term_screen.columns):
                    char = widget.term_screen.buffer[y][x]
                    line += char.data or " "
                if line.strip():
                    logging.info(f"Line {y}: {repr(line.rstrip())}")

if __name__ == "__main__":
    app = TestTerminalApp()
    app.run()