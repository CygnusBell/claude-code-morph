#!/usr/bin/env python3
"""Claude Code Morph - A self-editable development environment powered by Claude CLI."""

import os
import sys
import yaml
import asyncio
import importlib
import importlib.util
import signal
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static
from textual.binding import Binding
from rich.console import Console
from rich.prompt import Prompt
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

console = Console()

class PanelReloader(FileSystemEventHandler):
    """Handles hot-reloading of panel modules."""
    
    def __init__(self, app: 'ClaudeCodeMorph'):
        self.app = app
        self.panels_dir = Path(__file__).parent / "panels"
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        path = Path(event.src_path)
        if path.suffix == '.py' and path.parent == self.panels_dir:
            module_name = path.stem
            console.print(f"[yellow]Hot-reloading panel: {module_name}[/yellow]")
            self.app.call_from_thread(self.app.reload_panel, module_name)

class ClaudeCodeMorph(App):
    """Main application for Claude Code Morph."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #main-container {
        height: 100%;
        width: 100%;
    }
    
    .panel {
        border: solid blue;
        height: 100%;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+s", "save_workspace", "Save Workspace"),
        Binding("ctrl+l", "load_workspace", "Load Workspace"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+r", "reload_all", "Reload All Panels"),
    ]
    
    def __init__(self):
        super().__init__()
        self.panels: Dict[str, object] = {}
        self.current_workspace: Optional[str] = None
        self.panels_dir = Path(__file__).parent / "panels"
        self.workspaces_dir = Path(__file__).parent / "workspaces"
        
        # Ensure directories exist
        self.panels_dir.mkdir(exist_ok=True)
        self.workspaces_dir.mkdir(exist_ok=True)
        
        # Set up hot-reloading
        self.observer = Observer()
        self.panel_reloader = PanelReloader(self)
        
    def on_mount(self) -> None:
        """Called when the app starts."""
        # Start file watcher for hot-reloading
        self.observer.schedule(self.panel_reloader, str(self.panels_dir), recursive=False)
        self.observer.start()
        
        # Skip prompt and load default workspace directly
        self.call_later(lambda: asyncio.create_task(self.load_workspace_file("default.yaml")))
        
    async def startup_prompt(self) -> None:
        """Show startup prompt to user."""
        # Run in a thread to avoid blocking the UI
        choice = await self.run_worker(self._get_startup_choice, thread=True).wait()
        
        if choice == "1":
            await self.load_workspace_file("default.yaml")
        else:
            # Start with just terminal panel
            await self.load_minimal_layout()
            
    def _get_startup_choice(self) -> str:
        """Get startup choice from user (runs in thread)."""
        console.clear()
        console.print("[bold cyan]Claude Code Morph v0.1[/bold cyan]")
        console.print("\nStartup Options:")
        console.print("1. Start with default layout")
        console.print("2. Start from scratch (terminal only)")
        
        return Prompt.ask("\nYour choice", choices=["1", "2"], default="1")
        
    def compose(self) -> ComposeResult:
        """Create initial UI layout."""
        yield Header(show_clock=True)
        yield Horizontal(id="main-container")
        yield Footer()
        
    async def load_workspace_file(self, filename: str) -> None:
        """Load a workspace configuration from file."""
        workspace_path = self.workspaces_dir / filename
        
        if not workspace_path.exists():
            self.notify(f"Workspace {filename} not found, loading minimal layout", severity="warning")
            await self.load_minimal_layout()
            return
            
        try:
            with open(workspace_path, 'r') as f:
                config = yaml.safe_load(f)
                
            await self.load_workspace(config)
            self.current_workspace = filename
            self.notify(f"Loaded workspace: {filename}")
            
        except Exception as e:
            self.notify(f"Error loading workspace: {e}", severity="error")
            await self.load_minimal_layout()
            
    async def load_workspace(self, config: dict) -> None:
        """Load a workspace configuration."""
        container = self.query_one("#main-container", Horizontal)
        
        # Clear existing panels
        await container.remove_children()
        self.panels.clear()
        
        # Load panels from config
        layout = config.get("layout", [])
        
        for panel_config in layout:
            panel_type = panel_config.get("type")
            panel_id = panel_config.get("id", panel_type)
            params = panel_config.get("params", {})
            
            if panel_type:
                await self.add_panel(panel_type, panel_id, params)
                
    async def load_minimal_layout(self) -> None:
        """Load minimal layout with just terminal panel."""
        config = {
            "layout": [
                {"type": "TerminalPanel", "id": "terminal", "params": {}}
            ]
        }
        await self.load_workspace(config)
        
    async def add_panel(self, panel_type: str, panel_id: str, params: dict) -> None:
        """Dynamically load and add a panel to the layout."""
        try:
            # Import panel module
            module_path = self.panels_dir / f"{panel_type}.py"
            
            if not module_path.exists():
                self.notify(f"Panel module {panel_type}.py not found", severity="error")
                return
                
            spec = importlib.util.spec_from_file_location(panel_type, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get panel class (should have same name as module)
            panel_class = getattr(module, panel_type)
            
            # Create panel instance
            panel = panel_class(**params)
            panel.id = panel_id
            panel.classes = "panel"
            
            # Add to layout
            container = self.query_one("#main-container", Horizontal)
            await container.mount(panel)
            
            # Store reference
            self.panels[panel_id] = panel
            
        except Exception as e:
            import traceback
            error_msg = f"Error loading panel {panel_type}: {str(e)}"
            self.notify(error_msg, severity="error")
            # Also log to console and file for debugging
            console.print(f"[red]{error_msg}[/red]")
            console.print(traceback.format_exc())
            logging.error(f"{error_msg}\n{traceback.format_exc()}")
            
    async def reload_panel(self, module_name: str) -> None:
        """Hot-reload a panel module."""
        # Find panels using this module
        panels_to_reload = []
        
        for panel_id, panel in self.panels.items():
            if panel.__class__.__name__ == module_name:
                panels_to_reload.append((panel_id, panel))
                
        if not panels_to_reload:
            return
            
        for panel_id, old_panel in panels_to_reload:
            try:
                # Get panel config
                params = getattr(old_panel, '_init_params', {})
                
                # Remove old panel
                await old_panel.remove()
                del self.panels[panel_id]
                
                # Reload module
                module_path = self.panels_dir / f"{module_name}.py"
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Create new panel
                panel_class = getattr(module, module_name)
                new_panel = panel_class(**params)
                new_panel.id = panel_id
                new_panel.classes = "panel"
                
                # Add to layout
                container = self.query_one("#main-container", Horizontal)
                await container.mount(new_panel)
                
                self.panels[panel_id] = new_panel
                self.notify(f"Reloaded panel: {panel_id}")
                
            except Exception as e:
                self.notify(f"Error reloading panel {panel_id}: {e}", severity="error")
                
    def action_save_workspace(self) -> None:
        """Save current workspace configuration."""
        # Get workspace name from user
        name = Prompt.ask("Workspace name", default=self.current_workspace or "custom")
        
        if not name.endswith('.yaml'):
            name += '.yaml'
            
        # Build workspace config
        config = {
            "name": name.replace('.yaml', ''),
            "layout": []
        }
        
        for panel_id, panel in self.panels.items():
            panel_config = {
                "type": panel.__class__.__name__,
                "id": panel_id,
                "params": getattr(panel, '_init_params', {})
            }
            config["layout"].append(panel_config)
            
        # Save to file
        workspace_path = self.workspaces_dir / name
        
        with open(workspace_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        self.current_workspace = name
        self.notify(f"Saved workspace: {name}")
        
    def action_load_workspace(self) -> None:
        """Load a workspace configuration."""
        # List available workspaces
        workspaces = list(self.workspaces_dir.glob("*.yaml"))
        
        if not workspaces:
            self.notify("No saved workspaces found", severity="warning")
            return
            
        console.clear()
        console.print("[bold]Available Workspaces:[/bold]")
        
        for i, ws in enumerate(workspaces, 1):
            console.print(f"{i}. {ws.name}")
            
        choice = Prompt.ask("\nSelect workspace", choices=[str(i) for i in range(1, len(workspaces) + 1)])
        
        selected = workspaces[int(choice) - 1]
        self.call_from_thread(self.load_workspace_file, selected.name)
        
    def action_reload_all(self) -> None:
        """Reload all panels."""
        panel_types = set(panel.__class__.__name__ for panel in self.panels.values())
        
        for panel_type in panel_types:
            self.call_from_thread(self.reload_panel, panel_type)
            
    def on_unmount(self) -> None:
        """Clean up when app exits."""
        self.observer.stop()
        self.observer.join()

def main():
    """Entry point for Claude Code Morph."""
    # Set up logging
    logging.basicConfig(
        filename='main.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        force=True
    )
    logging.info("Starting Claude Code Morph...")
    
    # Redirect stderr to log file as well
    sys.stderr = open('main.log', 'a')
    
    # Set the working directory to this app's source directory
    # This allows Claude CLI to edit the app from within itself
    app_dir = Path(__file__).parent
    os.chdir(app_dir)
    
    # Inform user about self-editing capability
    console.print(f"[bold green]Working directory set to: {app_dir}[/bold green]")
    console.print("[yellow]Claude CLI can now edit this app from within itself![/yellow]\n")
    
    # Set up signal handler for Ctrl+C
    def signal_handler(sig, frame):
        console.print("\n[red]Interrupted! Exiting...[/red]")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run the app
    try:
        app = ClaudeCodeMorph()
        app.run()
    except KeyboardInterrupt:
        console.print("\n[red]Interrupted! Exiting...[/red]")
        sys.exit(0)

if __name__ == "__main__":
    main()