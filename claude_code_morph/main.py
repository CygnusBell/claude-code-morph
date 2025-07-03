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
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Type
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll, Container
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane
from textual.binding import Binding
from rich.console import Console
from rich.prompt import Prompt
# Hot-reloading disabled - watchdog imports removed
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
from .session_manager import SessionManager

console = Console()

# Hot-reloading disabled - use F5 for manual reload
# class PanelReloader(FileSystemEventHandler):
#     """Handles hot-reloading of panel modules."""
#     
#     def __init__(self, app: 'ClaudeCodeMorph'):
#         self.app = app
#         self.panels_dir = Path(__file__).parent / "panels"
#         
#     def on_modified(self, event):
#         if event.is_directory:
#             return
#             
#         path = Path(event.src_path)
#         if path.suffix == '.py' and path.parent == self.panels_dir:
#             module_name = path.stem
#             console.print(f"[yellow]Hot-reloading panel: {module_name}[/yellow]")
#             logging.info(f"Hot-reload triggered for: {module_name}")
#             self.app.call_from_thread(self.app.reload_panel, module_name)

class ClaudeCodeMorph(App):
    """Main application for Claude Code Morph."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    Button {
        text-style: none !important;
    }
    
    Button:focus {
        text-style: none !important;
    }
    
    Button:hover {
        text-style: none !important;
    }
    
    Button:focus-within {
        text-style: none !important;
    }
    
    Button.-active {
        text-style: none !important;
    }
    
    #main-container {
        height: 99%;
        width: 100%;
    }
    
    .panel-container {
        height: 1fr;
        min-height: 5;
    }
    
    .panel {
        border: none;
        height: 100%;
        margin: 0;
        padding: 0;
    }
    
    .splitter {
        height: 1;
        background: $boost;
        dock: top;
    }
    
    .splitter:hover {
        background: $primary;
    }
    
    PromptPanel {
        background: $surface;
    }
    
    TerminalPanel {
        background: #1e1e1e;
        border: none;
        margin: 0;
        padding: 0;
    }
    
    #terminal-output {
        background: #1e1e1e;
    }
    
    #tab-container {
        height: 100%;
    }
    
    TabbedContent {
        background: $surface;
    }
    
    TabPane {
        height: 100%;
        padding: 0;
    }
    
    Tabs {
        height: 3;
        background: $panel;
    }
    
    Tab {
        padding: 0 2;
    }
    
    Tab:hover {
        text-style: bold;
    }
    
    Tab.-active {
        background: $primary;
        text-style: bold;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+s", "save_workspace", "Save Workspace"),
        Binding("ctrl+l", "load_workspace", "Load Workspace"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+shift+f", "launch_safe_mode", "Fix (Safe Mode)"),
        Binding("ctrl+t", "reload_all", "Reload All", show=True, priority=True),
        Binding("ctrl+tab", "switch_tab", "Switch Tab", show=False),
        Binding("ctrl+1", "main_tab", "Main Tab", show=False),
        Binding("ctrl+2", "morph_tab", "Morph Tab", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.panels: Dict[str, object] = {}
        self.current_workspace: Optional[str] = None
        
        # Use morph source directory for internal files
        self.morph_source = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent))
        self.panels_dir = self.morph_source / "panels"
        self.workspaces_dir = self.morph_source / "workspaces"
        
        # Ensure directories exist
        self.panels_dir.mkdir(exist_ok=True)
        self.workspaces_dir.mkdir(exist_ok=True)
        
        # Hot-reloading disabled - use F5 for manual reload
        # self.observer = Observer()
        # self.panel_reloader = PanelReloader(self)
        
        # Initialize session manager
        self.session_manager = SessionManager()
        self._auto_save_timer = None
        
        # Track morph tab state
        self.morph_tab_activated = False
        self.main_panels: Dict[str, object] = {}
        self.morph_panels: Dict[str, object] = {}
        
    def on_parser_error(self, event) -> None:
        """Handle CSS parser errors."""
        logging.error(f"CSS Parser Error: {event}")
        
    def on_css_change(self, event) -> None:
        """Log CSS changes and errors."""
        try:
            super().on_css_change(event)
        except Exception as e:
            logging.error(f"CSS Change Error: {e}", exc_info=True)
            
    def compose(self) -> ComposeResult:
        """Create the main layout."""
        yield Header()
        from .widgets.resizable import ResizableContainer
        
        # Create the tabbed content
        with TabbedContent("Main", "Morph", id="tab-container"):
            # Main tab content
            with TabPane("Main", id="main-tab"):
                yield ResizableContainer(id="main-container")
            # Morph tab content  
            with TabPane("Morph", id="morph-tab"):
                yield ResizableContainer(id="morph-container")
                
        yield Footer()
        
    def on_key(self, event) -> None:
        """Debug key events."""
        # Log to both file and console for debugging
        msg = f"App received key: {event.key}"
        logging.info(msg)
        print(f"\n[KEY DEBUG] {msg}", flush=True)
        
        if event.key == "ctrl+comma":
            print("\n[KEY DEBUG] Ctrl+Comma detected! Calling reload...", flush=True)
            logging.info("Ctrl+Comma detected in app!")
            # Don't stop the event, let it continue to action
        
    def on_mount(self) -> None:
        """Called when the app starts."""
        # Hot-reloading disabled - use F5 for manual reload
        # try:
        #     self.observer.schedule(self.panel_reloader, str(self.panels_dir), recursive=False)
        #     self.observer.start()
        # except Exception as e:
        #     logging.warning(f"Could not start file watcher for hot-reloading: {e}")
        #     # Continue without hot-reloading
        
        # Check for existing session
        session_info = self.session_manager.get_session_info()
        if session_info:
            self.notify(f"Found session from {session_info.get('saved_at', 'unknown time')}")
            # Load session after workspace with a delay to ensure tabs are ready
            self.set_timer(0.1, lambda: asyncio.create_task(self._load_with_session()))
        else:
            # Skip prompt and load default workspace directly with a delay
            self.set_timer(0.1, lambda: asyncio.create_task(self.load_workspace_file("default.yaml")))
            
        # Connect the panels after loading with a slight delay to ensure panels are ready
        self.call_later(lambda: self.set_timer(0.1, self._connect_panels))
        
        # Start auto-save timer (30 seconds)
        self._start_auto_save()
        
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
        console.print("[bold cyan]Claude Code Morph v0.1 - DEBUG VERSION[/bold cyan]")
        console.print("\nStartup Options:")
        console.print("1. Start with default layout")
        console.print("2. Start from scratch (terminal only)")
        
        return Prompt.ask("\nYour choice", choices=["1", "2"], default="1")
        
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
        """Load a workspace configuration into the main tab."""
        from .widgets.resizable import ResizableContainer
        
        # Get the main container from within the main tab
        try:
            # First get the tab container, then find the main-container within it
            tab_container = self.query_one("#tab-container", TabbedContent)
            logging.debug(f"Found tab container: {tab_container}")
            
            # The main-container is inside the first TabPane (main-tab)
            main_tab = tab_container.get_child_by_id("main-tab")
            if not main_tab:
                # Try alternative method
                for child in tab_container.children:
                    if hasattr(child, 'id') and child.id == "main-tab":
                        main_tab = child
                        break
            
            if not main_tab:
                logging.error("Could not find main-tab")
                self.notify("Error: Could not find main tab", severity="error")
                return
                
            logging.debug(f"Found main tab: {main_tab}")
            
            container = main_tab.query_one("#main-container", ResizableContainer)
            logging.debug(f"Found container: {container}")
        except Exception as e:
            logging.error(f"Could not find main container: {e}", exc_info=True)
            self.notify(f"Error finding main container: {e}", severity="error")
            return
        
        # Clear existing panels
        await container.remove_children()
        self.panels.clear()
        
        # Load panels from config
        layout = config.get("layout", [])
        
        logging.info(f"Loading workspace with {len(layout)} panels")
        self.notify(f"Loading workspace with {len(layout)} panels")
        
        for panel_config in layout:
            panel_type = panel_config.get("type")
            panel_id = panel_config.get("id", panel_type)
            params = panel_config.get("params", {})
            
            logging.info(f"Loading panel: {panel_type} (id: {panel_id})")
            self.notify(f"Loading panel: {panel_type} (id: {panel_id})")
            
            if panel_type:
                await self.add_panel(panel_type, panel_id, params, container)
                
    async def load_minimal_layout(self) -> None:
        """Load minimal layout with just terminal panel."""
        config = {
            "layout": [
                {"type": "TerminalPanel", "id": "terminal", "params": {}}
            ]
        }
        await self.load_workspace(config)
        
    async def add_panel(self, panel_type: str, panel_id: str, params: dict, container=None) -> None:
        """Dynamically load and add a panel to the layout."""
        try:
            # Import panel module
            module_path = self.panels_dir / f"{panel_type}.py"
            
            if not module_path.exists():
                self.notify(f"Panel module {panel_type}.py not found", severity="error")
                return
                
            # Add the project root to sys.path temporarily to allow imports
            project_root = str(Path(__file__).parent)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            spec = importlib.util.spec_from_file_location(panel_type, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Get panel class (should have same name as module)
            panel_class = getattr(module, panel_type)
            
            # Create panel instance
            panel = panel_class(**params)
            panel.id = panel_id
            
            # Try to set classes and catch CSS errors
            try:
                panel.classes = "panel"
            except Exception as e:
                logging.error(f"CSS Error setting panel classes: {e}", exc_info=True)
                self.notify(f"CSS Error: {e}", severity="error")
            
            # Add to layout
            if container is None:
                from .widgets.resizable import ResizableContainer
                # Get the main container from within the main tab
                tab_container = self.query_one("#tab-container", TabbedContent)
                main_tab = tab_container.get_child_by_id("main-tab")
                container = main_tab.query_one("#main-container", ResizableContainer)
            await container.mount(panel)
            
            # Store reference
            self.panels[panel_id] = panel
            
            logging.info(f"Successfully added panel {panel_id}")
            
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
        # Prevent recursive reloads
        if hasattr(self, '_reloading') and self._reloading:
            logging.warning("Already reloading, skipping to prevent recursion")
            return
            
        self._reloading = True
        try:
            logging.info(f"reload_panel called for module: {module_name}")
            
            # Find panels using this module
            panels_to_reload = []
            
            for panel_id, panel in self.panels.items():
                if panel.__class__.__name__ == module_name:
                    panels_to_reload.append((panel_id, panel))
                    
            if not panels_to_reload:
                logging.warning(f"No panels found using module: {module_name}")
                return
            
            logging.info(f"Found {len(panels_to_reload)} panels to reload")
            
            for panel_id, old_panel in panels_to_reload:
                try:
                    # Get panel config
                    params = getattr(old_panel, '_init_params', {})
                    
                    # Preserve state from old panel
                    preserved_state = {}
                    if hasattr(old_panel, '_preserved_state'):
                        # Save current state
                        if hasattr(old_panel, 'selected_style'):
                            preserved_state['selected_style'] = old_panel.selected_style
                        if hasattr(old_panel, 'selected_mode'):
                            preserved_state['selected_mode'] = old_panel.selected_mode
                        if hasattr(old_panel, 'prompt_input') and old_panel.prompt_input:
                            preserved_state['prompt_text'] = old_panel.prompt_input.text
                        if hasattr(old_panel, 'prompt_history'):
                            preserved_state['prompt_history'] = old_panel.prompt_history
                        if hasattr(old_panel, 'history_index'):
                            preserved_state['history_index'] = old_panel.history_index
                    
                    # Find the wrapper containing the old panel
                    from .widgets.resizable import ResizableContainer
                    # Get the main container from within the main tab
                    tab_container = self.query_one("#tab-container", TabbedContent)
                    main_tab = tab_container.get_child_by_id("main-tab")
                    container = main_tab.query_one("#main-container", ResizableContainer)
                    
                    # Find the index of this panel in the container
                    panel_index = -1
                    for i, p in enumerate(container.panels):
                        if p == old_panel:
                            panel_index = i
                            break
                    
                    if panel_index == -1:
                        logging.error(f"Could not find panel {panel_id} in container")
                        return
                    
                    # Find the wrapper that contains this panel
                    wrapper_to_replace = None
                    for child in container.children:
                        if hasattr(child, 'children') and old_panel in child.children:
                            wrapper_to_replace = child
                            break
                    
                    if not wrapper_to_replace:
                        logging.error(f"Could not find wrapper for panel {panel_id}")
                        return
                    
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
                    
                    # Restore preserved state
                    if preserved_state and hasattr(new_panel, '_preserved_state'):
                        for key, value in preserved_state.items():
                            if hasattr(new_panel, key):
                                setattr(new_panel, key, value)
                    
                    # Replace the old panel in the wrapper
                    await old_panel.remove()
                    await wrapper_to_replace.mount(new_panel)
                    
                    # Update the panels list in container
                    container.panels[panel_index] = new_panel
                    
                    # Update our panels dict
                    del self.panels[panel_id]
                    self.panels[panel_id] = new_panel
                    self.notify(f"Reloaded panel: {panel_id}")
                    
                    # Restore prompt text after mount
                    if panel_id == "prompt" and preserved_state.get('prompt_text') and hasattr(new_panel, 'prompt_input'):
                        new_panel.prompt_input.text = preserved_state['prompt_text']
                    
                    # Reconnect panels if this was PromptPanel or we have both panels
                    if panel_id == "prompt" or (panel_id == "terminal" and "prompt" in self.panels):
                        self._connect_panels()
                    
                except Exception as e:
                    import traceback
                    error_msg = f"Error reloading panel {panel_id}: {e}"
                    self.notify(error_msg, severity="error")
                    logging.error(f"{error_msg}\n{traceback.format_exc()}")
                    # Try to restore the old panel if something went wrong
                    if panel_id not in self.panels and old_panel:
                        self.panels[panel_id] = old_panel
        finally:
            self._reloading = False
                
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
        
    
    def action_launch_safe_mode(self) -> None:
        """Launch safe mode to fix errors."""
        import subprocess
        
        # Save session before exiting
        self._save_session()
        
        # Notify user
        self.notify("Launching Safe Mode to fix errors...", severity="warning")
        
        # Create a flag file to indicate safe mode request
        safe_mode_flag = self.morph_source.parent / ".safe_mode_requested"
        safe_mode_flag.touch()
        
        # Force exit the app
        logging.info("User requested safe mode fix via Ctrl+Shift+F")
        
        # Try graceful exit first
        try:
            self.exit(return_code=99)  # Special code for safe mode
        except:
            # If graceful exit fails, force exit
            import os
            os._exit(99)
    
    
    def action_reload_all(self) -> None:
        """Reload all panels by reloading their modules."""
        logging.info("User requested reload all via Ctrl+T")
        self.notify("Reloading all panels...", severity="information")
        
        # Also log to console for debugging
        import sys
        print("\n[CTRL+T PRESSED] Reloading all panels...", file=sys.stderr)
        
        async def _do_reload():
            try:
                # Get unique panel types currently loaded
                panel_types = set()
                for panel in self.panels.values():
                    panel_types.add(panel.__class__.__name__)
                
                # Reload each panel type
                for panel_type in panel_types:
                    await self.reload_panel(panel_type)
                    
                self.notify("All panels reloaded successfully!", severity="success")
                
            except Exception as e:
                logging.error(f"Error reloading panels: {e}")
                self.notify(f"Error reloading panels: {e}", severity="error")
        
        # Schedule the async reload
        self.call_later(lambda: asyncio.create_task(_do_reload()))
    
    def action_switch_tab(self) -> None:
        """Switch between Main and Morph tabs."""
        tabs = self.query_one("#tab-container", TabbedContent)
        if tabs.active == "main-tab":
            tabs.active = "morph-tab"
            self._activate_morph_tab()
        else:
            tabs.active = "main-tab"
    
    def action_main_tab(self) -> None:
        """Switch to Main tab."""
        tabs = self.query_one("#tab-container", TabbedContent)
        tabs.active = "main-tab"
    
    def action_morph_tab(self) -> None:
        """Switch to Morph tab."""
        tabs = self.query_one("#tab-container", TabbedContent)
        tabs.active = "morph-tab"
        self._activate_morph_tab()
    
    def _activate_morph_tab(self) -> None:
        """Initialize morph tab on first activation."""
        if not self.morph_tab_activated:
            self.morph_tab_activated = True
            # Load workspace into morph container
            self.call_later(lambda: asyncio.create_task(self._load_morph_workspace()))
    
    async def _load_morph_workspace(self) -> None:
        """Load workspace configuration into morph tab."""
        # Load terminal panel into morph container
        from .widgets.resizable import ResizableContainer
        container = self.query_one("#morph-container", ResizableContainer)
        
        # Create terminal panel with morph source directory
        panel_params = {
            "working_directory": str(self.morph_source.parent),
            "auto_start": True
        }
        
        # Create and mount the terminal panel
        try:
            # Import panel module
            module_path = self.panels_dir / "TerminalPanel.py"
            spec = importlib.util.spec_from_file_location("TerminalPanel", module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Create panel instance
            panel_class = getattr(module, "TerminalPanel")
            panel = panel_class(**panel_params)
            panel.id = "morph_terminal"
            panel.classes = "panel"
            
            # Mount to morph container
            await container.mount(panel)
            
            # Store reference in morph_panels
            self.morph_panels["morph_terminal"] = panel
            
            self.notify("Morph tab initialized with Claude Code Morph source directory")
            
        except Exception as e:
            self.notify(f"Error loading morph terminal: {e}", severity="error")
            logging.error(f"Error loading morph terminal: {e}")
    
    
    def _connect_panels(self) -> None:
        """Connect the prompt panel to the terminal panel."""
        prompt_panel = self.panels.get("prompt")
        terminal_panel = self.panels.get("terminal")
        
        logging.info(f"Connecting panels: prompt={prompt_panel}, terminal={terminal_panel}")
        
        if prompt_panel and terminal_panel:
            # Set the on_submit callback
            if hasattr(terminal_panel, 'send_prompt'):
                prompt_panel.on_submit = terminal_panel.send_prompt
                self.notify("Panels connected successfully")
                logging.info("Panels connected successfully")
                
                # Note: Can't set Select widget values directly due to Textual limitations
            else:
                logging.error("Terminal panel does not have send_prompt method")
        else:
            logging.warning(f"Could not connect panels: prompt={prompt_panel}, terminal={terminal_panel}")
            
    async def _load_with_session(self) -> None:
        """Load workspace and restore session."""
        # First load default workspace
        await self.load_workspace_file("default.yaml")
        
        # Then restore session state
        await asyncio.sleep(0.5)  # Give panels time to initialize
        self._restore_session()
        
    def _save_session(self) -> None:
        """Save current session state."""
        try:
            state = {
                'workspace': self.current_workspace,
                'panels': {}
            }
            
            # Get state from each panel
            for panel_id, panel in self.panels.items():
                if hasattr(panel, 'get_state'):
                    state['panels'][panel_id] = panel.get_state()
                    
            # Save terminal buffer separately
            terminal_panel = self.panels.get('terminal')
            if terminal_panel and hasattr(terminal_panel, 'terminal_buffer'):
                self.session_manager.save_terminal_buffer(terminal_panel.terminal_buffer)
                
            # Save prompt history separately
            prompt_panel = self.panels.get('prompt')
            if prompt_panel and hasattr(prompt_panel, 'prompt_history'):
                self.session_manager.save_prompt_history(prompt_panel.prompt_history)
                
            # Save main session
            self.session_manager.save_session(state)
            logging.info("Session saved successfully")
            
        except Exception as e:
            logging.error(f"Failed to save session: {e}")
            
    def _restore_session(self) -> None:
        """Restore saved session state."""
        try:
            state = self.session_manager.load_session()
            if not state:
                return
                
            # Restore panel states
            panel_states = state.get('panels', {})
            for panel_id, panel_state in panel_states.items():
                panel = self.panels.get(panel_id)
                if panel and hasattr(panel, 'restore_state'):
                    panel.restore_state(panel_state)
                    
            # Restore terminal buffer
            terminal_panel = self.panels.get('terminal')
            if terminal_panel and hasattr(terminal_panel, 'restore_state'):
                buffer = self.session_manager.load_terminal_buffer()
                if buffer:
                    terminal_panel.terminal_buffer = buffer
                    terminal_panel._update_display()
                    
            # Restore prompt history
            prompt_panel = self.panels.get('prompt')
            if prompt_panel and hasattr(prompt_panel, 'prompt_history'):
                history = self.session_manager.load_prompt_history()
                if history:
                    prompt_panel.prompt_history = history
                    
            self.notify("Session restored", severity="success")
            logging.info("Session restored successfully")
            
        except Exception as e:
            logging.error(f"Failed to restore session: {e}")
            self.notify("Failed to restore session", severity="warning")
            
    def _start_auto_save(self) -> None:
        """Start periodic auto-save timer."""
        def auto_save():
            self._save_session()
            logging.debug("Auto-save completed")
            
        # Save every 30 seconds
        self._auto_save_timer = self.set_timer(30, auto_save, pause=False)
        
    def on_unmount(self) -> None:
        """Clean up when app exits."""
        # Save session before exit
        self._save_session()
        
        # Stop auto-save timer
        if self._auto_save_timer:
            self._auto_save_timer.stop()
            
        # Hot-reloading disabled
        # try:
        #     if hasattr(self, 'observer') and self.observer.is_alive():
        #         self.observer.stop()
        #         self.observer.join(timeout=1.0)
        # except Exception as e:
        #     logging.warning(f"Error stopping file watcher: {e}")

def main():
    """Entry point for Claude Code Morph."""
    # Disable Python bytecode generation for cleaner development
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    
    # Set up logging with more comprehensive error capture
    logging.basicConfig(
        filename='main.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        force=True
    )
    
    # Add console handler for immediate error visibility
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(levelname)s - %(name)s - %(message)s'))
    logging.getLogger().addHandler(console_handler)
    
    # Enable Textual CSS error logging
    logging.getLogger('textual').setLevel(logging.DEBUG)
    logging.getLogger('textual.css').setLevel(logging.DEBUG)
    logging.getLogger('textual.dom').setLevel(logging.DEBUG)
    
    # Suppress specific warnings/errors from the SDK
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    warnings.filterwarnings('ignore', message='Task exception was never retrieved')
    
    logging.info("Starting Claude Code Morph...")
    console.print("[bold cyan]Claude Code Morph[/bold cyan]")
    
    # Don't redirect stderr when running in a terminal to avoid Textual conflicts
    # Only redirect if we're not in an interactive terminal
    if not sys.stderr.isatty():
        try:
            sys.stderr = open('main.log', 'a')
        except Exception as e:
            logging.warning(f"Could not redirect stderr: {e}")
    
    # Set the working directory to the project root directory
    # This allows Claude CLI to edit the app from within itself
    app_dir = Path(__file__).parent
    project_root = app_dir.parent  # Go up one level to project root
    os.chdir(project_root)
    
    # Inform user about self-editing capability
    console.print(f"[bold green]Working directory set to: {project_root}[/bold green]")
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
    except Exception as e:
        logging.error(f"Fatal error in main app: {e}", exc_info=True)
        console.print(f"\n[red]Fatal error: {e}[/red]")
        console.print("[yellow]Check main.log for details[/yellow]")
        sys.exit(1)

if __name__ == "__main__":
    main()