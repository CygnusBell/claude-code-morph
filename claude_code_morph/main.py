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
from textual.widgets import Header, Footer, Static, TabbedContent, TabPane, ContentSwitcher
from textual.binding import Binding
from rich.console import Console
from rich.prompt import Prompt
from datetime import datetime
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
        overflow-y: auto;
    }
    
    #tab-container {
        height: 1fr;
        width: 100%;
        min-height: 20;
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
        height: 100%;
        width: 100%;
        background: $surface;
        overflow: auto;
    }
    
    #morph-container {
        height: 100%;
        width: 100%;
        background: $surface;
        overflow: auto;
    }
    
    TabPane {
        height: 100%;
        width: 100%;
        layout: vertical;
        padding: 0;
        margin: 0;
    }
    
    TabPane > * {
        height: 1fr !important;
        width: 100%;
    }
    
    ContentSwitcher {
        height: 1fr !important;
        width: 100%;
    }
    
    TabbedContent > ContentSwitcher {
        height: 1fr !important;
    }
    
    TabbedContent ContentTabs {
        height: 3;
        dock: top;
    }
    
    .panel-container {
        height: 1fr;
        min-height: 5;
    }
    
    .panel {
        border: none;
        height: 100%;
        width: 100%;
        margin: 0;
        padding: 0;
        overflow: auto;
        background: $surface;
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
        
        # Set up error logging
        self._setup_error_logging()
        
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
        
    def _setup_error_logging(self) -> None:
        """Set up error logging to file."""
        # Create logs directory if it doesn't exist
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # Set up error log file
        error_log_path = log_dir / "error.log"
        
        # Create a file handler for errors
        error_handler = logging.FileHandler(error_log_path, mode='a')
        error_handler.setLevel(logging.WARNING)  # Capture warnings too
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d'
        )
        error_handler.setFormatter(formatter)
        
        # Add handler to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(error_handler)
        root_logger.setLevel(logging.INFO)
        
        # Log startup
        logging.info(f"Error logging initialized at {error_log_path}")
        
        # Write a test entry to ensure it's working
        with open(error_log_path, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"Application started at {datetime.now()}\n")
            f.write(f"{'='*60}\n")
        
    def notify(
        self,
        message: str,
        *,
        title: str = "",
        severity: str = "information",
        timeout: float = 3.0,
    ) -> None:
        """Override notify to log errors to file."""
        # Log errors and warnings to file
        if severity in ("error", "warning"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] {severity.upper()}: {message}"
            if title:
                log_message = f"[{timestamp}] {severity.upper()} - {title}: {message}"
            
            # Write to error log
            try:
                log_path = Path.cwd() / "logs" / "error.log"
                log_path.parent.mkdir(exist_ok=True)
                with open(log_path, 'a') as f:
                    f.write(log_message + "\n")
                    f.flush()
            except Exception as e:
                # Fallback to standard logging if file write fails
                logging.error(f"Failed to write to error.log: {e}")
                logging.error(log_message)
        
        # Call parent notify to show the notification
        super().notify(message, title=title, severity=severity, timeout=timeout)
    
    def _handle_exception(self, error: Exception) -> None:
        """Handle unhandled exceptions and log them."""
        import traceback
        
        # Get full traceback
        tb_str = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        
        # Log to error.log
        try:
            log_path = Path.cwd() / "logs" / "error.log"
            log_path.parent.mkdir(exist_ok=True)
            with open(log_path, 'a') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"UNHANDLED EXCEPTION at {datetime.now()}\n")
                f.write(f"{'='*60}\n")
                f.write(tb_str)
                f.write(f"{'='*60}\n\n")
                f.flush()
        except Exception as e:
            logging.error(f"Failed to write exception to error.log: {e}")
        
        # Also log using standard logging
        logging.error(f"Unhandled exception: {error}", exc_info=True)
        
        # Show notification to user
        self.notify(f"Error: {str(error)}", severity="error")
        
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
        logging.info("=== compose() called ===")
        yield Header()
        
        from .widgets.resizable import ResizableContainer
        
        # Store references to containers
        self.main_container = ResizableContainer(id="main-container")
        self.morph_container = ResizableContainer(id="morph-container")
        logging.info(f"Created containers: main={self.main_container}, morph={self.morph_container}")
        
        # Create the tabbed content with context managers
        with TabbedContent(id="tab-container"):
            with TabPane("Main", id="main-tab"):
                yield self.main_container
            with TabPane("Morph", id="morph-tab"):
                yield self.morph_container
        
        yield Footer()
        logging.info("=== compose() completed ===")
        
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
        
    async def on_mount(self) -> None:
        """Called when the app starts."""
        logging.info("=== on_mount called ===")
        
        # Log the widget tree
        self._log_widget_tree()
        
        # Hot-reloading disabled - use F5 for manual reload
        # try:
        #     self.observer.schedule(self.panel_reloader, str(self.panels_dir), recursive=False)
        #     self.observer.start()
        # except Exception as e:
        #     logging.warning(f"Could not start file watcher for hot-reloading: {e}")
        #     # Continue without hot-reloading
        
        # Load workspace immediately
        try:
            # Check for existing session
            session_info = self.session_manager.get_session_info()
            if session_info:
                logging.info(f"Found session info: {session_info}")
                self.notify(f"Found session from {session_info.get('saved_at', 'unknown time')}")
                # Load with session
                logging.info("Calling _load_with_session...")
                await self._load_with_session()
            else:
                logging.info("No session found, loading default workspace")
                # Load default workspace
                logging.info("Calling load_workspace_file...")
                await self.load_workspace_file("default.yaml")
                
            # Connect the panels after loading
            logging.info("Calling _connect_panels...")
            self._connect_panels()
            
            # Log widget tree after loading
            logging.info("=== Widget tree after loading ===")
            self._log_widget_tree()
            
            # Check tab visibility and container sizes
            logging.info("=== Checking tab visibility after loading ===")
            try:
                tabbed = self.query_one("#tab-container", TabbedContent)
                logging.info(f"TabbedContent active: {tabbed.active}")
                logging.info(f"TabbedContent size: {tabbed.size}")
                logging.info(f"TabbedContent region: {tabbed.region}")
                
                # Check ContentSwitcher
                content_switcher = tabbed.query_one(ContentSwitcher)
                logging.info(f"ContentSwitcher size: {content_switcher.size}")
                logging.info(f"ContentSwitcher region: {content_switcher.region}")
                
                # Check TabPane
                main_tab = tabbed.query_one("#main-tab", TabPane)
                logging.info(f"Main TabPane size: {main_tab.size}")
                logging.info(f"Main TabPane region: {main_tab.region}")
                logging.info(f"Main TabPane visible: {main_tab.visible}")
                logging.info(f"Main TabPane display: {main_tab.display}")
                
                # Check main container
                logging.info(f"Main container size: {self.main_container.size}")
                logging.info(f"Main container region: {self.main_container.region}")
                logging.info(f"Main container visible: {self.main_container.visible}")
                logging.info(f"Main container display: {self.main_container.display}")
                logging.info(f"Main container children: {len(self.main_container.children)}")
                
                # Check actual panel sizes
                for i, child in enumerate(self.main_container.children):
                    logging.info(f"Container child {i}: {child} - size: {child.size}, region: {child.region}")
                
                # Force refresh and apply sizes
                self.main_container.refresh(layout=True)
                tabbed.refresh(layout=True)
                
                # Manually trigger size application for ResizableContainer after refresh
                from .widgets.resizable import ResizableContainer
                if isinstance(self.main_container, ResizableContainer):
                    logging.info("Scheduling _apply_sizes on main container")
                    self.call_after_refresh(self.main_container._apply_sizes)
                
            except Exception as e:
                logging.error(f"Error checking tab visibility: {e}", exc_info=True)
            
        except Exception as e:
            logging.error(f"Error during mount: {e}", exc_info=True)
            self.notify(f"Error loading workspace: {e}", severity="error")
        
        # Start auto-save timer (30 seconds)
        self._start_auto_save()
        
        # Add placeholder content to Morph tab
        try:
            logging.info("Adding MorphPanel to morph container")
            await self.add_panel("MorphPanel", "morph", {}, self.morph_container)
            logging.info("MorphPanel added successfully")
        except Exception as e:
            logging.error(f"Error adding MorphPanel: {e}", exc_info=True)
        
        # Schedule a full refresh after a short delay to ensure everything is laid out
        self.set_timer(0.5, self._force_full_refresh)
        
        logging.info("=== on_mount completed ===")
    
        
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
        logging.info(f"=== load_workspace_file called with: {filename} ===")
        logging.info(f"workspaces_dir: {self.workspaces_dir}")
        workspace_path = self.workspaces_dir / filename
        logging.info(f"Workspace path: {workspace_path}")
        logging.info(f"Workspace exists: {workspace_path.exists()}")
        
        if not workspace_path.exists():
            logging.error(f"Workspace file not found: {workspace_path}")
            self.notify(f"Workspace {filename} not found, loading minimal layout", severity="warning")
            await self.load_minimal_layout()
            return
            
        try:
            with open(workspace_path, 'r') as f:
                config = yaml.safe_load(f)
            
            logging.info(f"Loaded config: {config}")
            await self.load_workspace(config)
            self.current_workspace = filename
            self.notify(f"Loaded workspace: {filename}")
            
        except Exception as e:
            logging.error(f"Error loading workspace file: {e}", exc_info=True)
            self.notify(f"Error loading workspace: {e}", severity="error")
            await self.load_minimal_layout()
            
    async def load_workspace(self, config: dict) -> None:
        """Load a workspace configuration into the main tab."""
        logging.info("=== load_workspace called ===")
        logging.info(f"Config: {config}")
        
        # Use the stored reference to main container
        if not hasattr(self, 'main_container'):
            logging.error("Main container not initialized yet")
            self.notify("Error: Main container not ready", severity="error")
            return
            
        container = self.main_container
        logging.info(f"Using main container: {container}")
        logging.info(f"Container is mounted: {container.is_mounted}")
        logging.info(f"Container parent: {container.parent}")
        logging.info(f"Container children before clear: {len(container.children)}")
        
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
            
            logging.info(f"Loading panel: {panel_type} (id: {panel_id}) with params: {params}")
            self.notify(f"Loading panel: {panel_type} (id: {panel_id})")
            
            if panel_type:
                try:
                    await self.add_panel(panel_type, panel_id, params, container)
                    logging.info(f"Successfully added panel {panel_id}")
                except Exception as e:
                    logging.error(f"Failed to add panel {panel_id}: {e}", exc_info=True)
                    self.notify(f"Failed to add panel {panel_id}: {e}", severity="error")
        
        # Force a refresh of the container after all panels are loaded
        logging.info("Refreshing container after loading all panels")
        container.refresh(layout=True)
        
        # Debug - log container info
        logging.info(f"Container children count: {len(container.children)}")
        logging.info(f"Container panels count: {len(container.panels)}")
        logging.info(f"Container is mounted: {container.is_mounted}")
        logging.info(f"Container size: {container.size}")
        logging.info(f"Container region: {container.region}")
        logging.info(f"Container styles.display: {container.styles.display}")
        logging.info(f"Container styles.visibility: {container.styles.visibility}")
        for i, child in enumerate(container.children):
            logging.info(f"Child {i}: {child} (visible: {child.visible if hasattr(child, 'visible') else 'N/A'})")
            # Check if it's a wrapper container and log its children
            if isinstance(child, Container) and hasattr(child, 'children'):
                logging.info(f"  Wrapper children count: {len(child.children)}")
                for j, grandchild in enumerate(child.children):
                    logging.info(f"  Grandchild {j}: {grandchild} (visible: {grandchild.visible if hasattr(grandchild, 'visible') else 'N/A'})")
                if len(child.children) == 0:
                    logging.warning(f"  WARNING: Wrapper container {i} has no children!")
        
        # Force container to recalculate layout
        container.refresh(layout=True, repaint=True)
        
        # Also refresh the tab pane that contains this container
        try:
            # Find the tab pane that contains this container
            tabbed = self.query_one("#tab-container", TabbedContent)
            logging.info(f"TabbedContent found: {tabbed}")
            logging.info(f"TabbedContent active tab: {tabbed.active}")
            
            # Get all tab panes
            tab_panes = list(tabbed.query(TabPane))
            logging.info(f"Found {len(tab_panes)} tab panes")
            
            for tab_pane in tab_panes:
                logging.info(f"Tab pane {tab_pane.id}: visible={tab_pane.visible}, display={tab_pane.display}")
                if container in tab_pane.children:
                    logging.info(f"Container found in tab pane: {tab_pane.id}")
                    logging.info(f"Refreshing tab pane: {tab_pane.id}")
                    tab_pane.refresh(layout=True, repaint=True)
            tabbed.refresh(layout=True, repaint=True)
            # Force full app refresh
            self.refresh(layout=True, repaint=True)
        except Exception as e:
            logging.warning(f"Could not refresh tab pane: {e}")
                
    async def load_minimal_layout(self) -> None:
        """Load minimal layout with just terminal panel."""
        config = {
            "layout": [
                {"type": "TerminalPanel", "id": "terminal", "params": {}}
            ]
        }
        await self.load_workspace(config)
        
    async def load_morph_workspace(self, morph_panel) -> None:
        """Load the workspace configuration for morph mode."""
        logging.info("=== load_morph_workspace called ===")
        
        try:
            # Get the container from the morph panel
            container = morph_panel.query_one("#morph-workspace-container", Vertical)
            
            # Remove loading message
            loading_msg = container.query_one("#morph-loading-message")
            if loading_msg:
                await loading_msg.remove()
            
            # Import panel classes
            from .panels.PromptPanel import PromptPanel
            from .panels.EmulatedTerminalPanel import EmulatedTerminalPanel
            
            # Get morph source directory
            morph_source_dir = morph_panel.morph_source_dir
            logging.info(f"Loading morph workspace with source dir: {morph_source_dir}")
            
            # Create prompt panel
            prompt_panel = PromptPanel(id="morph-prompt-panel")
            morph_panel.sub_panels['prompt'] = prompt_panel
            
            # Create terminal panel with morph source directory
            terminal_panel = EmulatedTerminalPanel(
                id="morph-terminal-panel",
                working_dir=str(morph_source_dir)
            )
            morph_panel.sub_panels['terminal'] = terminal_panel
            
            # Mount panels
            await container.mount(prompt_panel)
            await container.mount(terminal_panel)
            
            # Connect panels
            if hasattr(prompt_panel, 'set_terminal_panel'):
                prompt_panel.set_terminal_panel(terminal_panel)
            
            logging.info("Morph workspace loaded successfully")
            self.notify("Morph workspace loaded", severity="information")
            
        except Exception as e:
            logging.error(f"Error loading morph workspace: {e}", exc_info=True)
            self.notify(f"Error loading morph workspace: {e}", severity="error")
            # Show error in the morph panel
            await container.mount(
                Static(f"[red]Error loading morph workspace: {e}[/red]")
            )
        
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
                # Use the stored main container reference
                if hasattr(self, 'main_container'):
                    container = self.main_container
                else:
                    logging.error("Main container not available in add_panel")
                    self.notify("Error: Main container not ready", severity="error")
                    return
            await container.mount(panel)
            
            # Store reference in app's panels dict
            self.panels[panel_id] = panel
            
            # Also check if the panel was successfully added to the container
            if hasattr(container, 'panels') and panel in container.panels:
                logging.info(f"Panel {panel_id} successfully added to container panels list")
                # Force a refresh of the container
                container.refresh(layout=True)
            else:
                logging.warning(f"Panel {panel_id} may not have been properly added to container")
            
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
                    # Use the stored main container reference
                    container = self.main_container if hasattr(self, 'main_container') else None
                    if not container:
                        logging.error("Main container not available in reload_panel")
                        return
                    
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
                
    def action_main_tab(self) -> None:
        """Switch to Main tab."""
        try:
            tabbed = self.query_one("#tab-container", TabbedContent)
            tabbed.active = "main-tab"
            logging.info("Switched to Main tab")
        except Exception as e:
            logging.error(f"Error switching to Main tab: {e}")
    
    def action_morph_tab(self) -> None:
        """Switch to Morph tab."""
        try:
            tabbed = self.query_one("#tab-container", TabbedContent)
            tabbed.active = "morph-tab"
            logging.info("Switched to Morph tab")
        except Exception as e:
            logging.error(f"Error switching to Morph tab: {e}")
    
    def action_switch_tab(self) -> None:
        """Switch between tabs."""
        try:
            tabbed = self.query_one("#tab-container", TabbedContent)
            if tabbed.active == "main-tab":
                tabbed.active = "morph-tab"
            else:
                tabbed.active = "main-tab"
        except Exception as e:
            logging.error(f"Error switching tabs: {e}")
    
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
        # Use stored morph container reference
        if not hasattr(self, 'morph_container'):
            logging.error("Morph container not initialized")
            self.notify("Error: Morph container not ready", severity="error")
            return
            
        container = self.morph_container
        
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
        logging.info("=== _connect_panels called ===")
        logging.info(f"Current panels in self.panels: {list(self.panels.keys())}")
        
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
            # Try again after a delay if panels aren't ready yet
            if not prompt_panel or not terminal_panel:
                logging.info("Panels not ready, scheduling retry in 0.5 seconds")
                self.set_timer(0.5, self._connect_panels)
            
    async def _load_with_session(self) -> None:
        """Load workspace and restore session."""
        logging.info("=== _load_with_session called ===")
        # First load default workspace
        await self.load_workspace_file("default.yaml")
        
        # Then restore session state
        await asyncio.sleep(0.5)  # Give panels time to initialize
        logging.info("Calling _restore_session")
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
        
    def _log_widget_tree(self, widget=None, level=0):
        """Log the widget tree for debugging."""
        if widget is None:
            widget = self
            
        indent = "  " * level
        widget_info = f"{widget.__class__.__name__}"
        if hasattr(widget, 'id') and widget.id:
            widget_info += f"(id='{widget.id}')"
        if hasattr(widget, 'display') and not widget.display:
            widget_info += " [HIDDEN]"
        if hasattr(widget, 'visible') and not widget.visible:
            widget_info += " [INVISIBLE]"
            
        logging.info(f"{indent}{widget_info}")
        
        if hasattr(widget, 'children'):
            for child in widget.children:
                self._log_widget_tree(child, level + 1)
    
    def _force_full_refresh(self):
        """Force a full refresh of the UI."""
        logging.info("=== Forcing full refresh ===")
        self.refresh(layout=True, repaint=True)
        if hasattr(self, 'main_container'):
            self.main_container.refresh(layout=True, repaint=True)
            self.main_container._apply_sizes()
        if hasattr(self, 'morph_container'):
            self.morph_container.refresh(layout=True, repaint=True)
            self.morph_container._apply_sizes()
        
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