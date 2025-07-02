#!/usr/bin/env python3
"""
Claude Code Morph - Safe Mode
Launches only the EmulatedTerminalPanel with instructions to fix errors.
"""

import os
import sys
from pathlib import Path

# Add the package to Python path
package_dir = Path(__file__).parent / "claude_code_morph"
sys.path.insert(0, str(package_dir.parent))

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer
from claude_code_morph.panels.EmulatedTerminalPanel import EmulatedTerminalPanel

class SafeModeApp(App):
    """Minimal app with just the terminal panel for fixing errors."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    EmulatedTerminalPanel {
        height: 100%;
        margin: 1;
        border: solid $primary;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit Safe Mode"),
    ]
    
    def compose(self) -> ComposeResult:
        """Create the safe mode layout."""
        yield Header(show_clock=True)
        
        # Create terminal panel
        self.terminal = EmulatedTerminalPanel(id="terminal")
        yield self.terminal
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Set up the terminal with fix instructions."""
        # Wait for terminal to be ready
        await self.terminal.start()
        
        # Send the safe mode prompt
        safe_mode_prompt = """
Please check main.log for errors and fix them. Here are some helpful commands:

1. View recent errors:
   tail -n 100 main.log | grep -A 10 -B 5 "ERROR\\|Exception\\|Traceback"

2. Edit problem files:
   nano claude_code_morph/panels/PromptPanel.py
   nano claude_code_morph/panels/BasePanel.py

3. Common fixes:
   - Add missing imports (e.g., from textual.widgets import Select)
   - Remove unsupported parameters (e.g., tooltip from Button)
   - Fix CSS property values

4. When done, exit with Ctrl+Q to automatically restart morph

Working directory: """ + os.getcwd()
        
        await self.terminal.send_prompt(safe_mode_prompt, mode="morph")

def main():
    """Run the safe mode app."""
    print("Starting Claude Code Morph in SAFE MODE...")
    print("This will launch a terminal to fix any errors.")
    print()
    
    # Set environment to morph mode
    os.environ["MORPH_MODE"] = "morph"
    
    app = SafeModeApp()
    app.run()
    
    print("\nSafe mode exited.")
    
    # Ask if user wants to start morph normally
    try:
        response = input("Start morph normally? (Y/n): ").strip().lower()
        if response != 'n':
            print("Starting morph...")
            import subprocess
            subprocess.run([sys.executable, "-m", "claude_code_morph.cli"])
    except KeyboardInterrupt:
        print("\nExiting without starting morph.")

if __name__ == "__main__":
    main()