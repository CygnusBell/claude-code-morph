"""Morph Panel - Self-editing mode for claude-code-morph."""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

try:
    from .BasePanel import BasePanel
except ImportError:
    # When loaded dynamically, use absolute import
    import sys
    from pathlib import Path as PathLib
    sys.path.append(str(PathLib(__file__).parent.parent))
    from panels.BasePanel import BasePanel


class MorphPanel(BasePanel):
    """Panel that loads the same workspace as Main but for self-editing claude-code-morph."""
    
    DEFAULT_CSS = """
    MorphPanel {
        background: $surface;
        layout: vertical;
        height: 100%;
    }
    
    MorphPanel > Vertical {
        height: 100%;
        width: 100%;
    }
    """
    
    def __init__(self, **kwargs):
        """Initialize the Morph panel."""
        super().__init__(**kwargs)
        self._init_params = kwargs
        self.sub_panels = {}
        self.morph_source_dir = Path(__file__).parent.parent.absolute()
        logging.info(f"MorphPanel initialized with source dir: {self.morph_source_dir}")
        
    def compose(self) -> ComposeResult:
        """Compose a container that will hold the loaded workspace panels."""
        with Vertical(id="morph-workspace-container"):
            yield Static("Loading morph workspace...", id="morph-loading-message")
    
    async def on_mount(self) -> None:
        """Load the workspace panels when mounted."""
        logging.info("MorphPanel mounted, loading workspace...")
        
        # Get the app instance to access workspace loading
        app = self.app
        if hasattr(app, 'load_morph_workspace'):
            # Use a dedicated method if available
            await app.load_morph_workspace(self)
        else:
            # Fallback: manually load the default workspace panels
            await self._load_default_workspace()
    
    async def _load_default_workspace(self) -> None:
        """Load the default workspace configuration for morph mode."""
        try:
            container = self.query_one("#morph-workspace-container", Vertical)
            
            # Remove loading message
            loading_msg = container.query_one("#morph-loading-message")
            if loading_msg:
                await loading_msg.remove()
            
            # Import panel classes
            from .PromptPanel import PromptPanel
            from .EmulatedTerminalPanel import EmulatedTerminalPanel
            
            # Create prompt panel
            prompt_panel = PromptPanel(id="morph-prompt-panel")
            self.sub_panels['prompt'] = prompt_panel
            
            # Create terminal panel with morph source directory
            terminal_panel = EmulatedTerminalPanel(
                id="morph-terminal-panel",
                working_dir=str(self.morph_source_dir)
            )
            self.sub_panels['terminal'] = terminal_panel
            
            # Mount panels
            await container.mount(prompt_panel)
            await container.mount(terminal_panel)
            
            # Connect panels if they have connection methods
            if hasattr(prompt_panel, 'set_terminal_panel'):
                prompt_panel.set_terminal_panel(terminal_panel)
            
            logging.info("Morph workspace loaded successfully")
            
        except Exception as e:
            logging.error(f"Error loading morph workspace: {e}")
            container = self.query_one("#morph-workspace-container", Vertical)
            await container.mount(
                Static(f"[red]Error loading morph workspace: {e}[/red]")
            )
    
    def get_state(self) -> Dict[str, Any]:
        """Get current panel state for persistence."""
        state = {
            'panel_type': 'MorphPanel',
            'sub_panels': {}
        }
        
        # Get state from sub-panels
        for panel_id, panel in self.sub_panels.items():
            if hasattr(panel, 'get_state'):
                state['sub_panels'][panel_id] = panel.get_state()
        
        return state
    
    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore panel state from saved data."""
        # Restore sub-panel states
        if 'sub_panels' in state:
            for panel_id, panel_state in state['sub_panels'].items():
                if panel_id in self.sub_panels:
                    panel = self.sub_panels[panel_id]
                    if hasattr(panel, 'restore_state'):
                        panel.restore_state(panel_state)