"""File Editor Panel - Browse and edit source files."""

import os
import logging
from pathlib import Path
from typing import Optional, Callable
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Label, Tree, Button, TextArea
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from rich.syntax import Syntax
from rich.text import Text

try:
    from .BasePanel import BasePanel
except ImportError:
    # When loaded dynamically, use absolute import
    import sys
    from pathlib import Path as PathLib
    sys.path.append(str(PathLib(__file__).parent.parent))
    from panels.BasePanel import BasePanel


class FileEditorPanel(BasePanel):
    """Panel for browsing and editing source code files."""
    
    DEFAULT_CSS = """
    FileEditorPanel {
        background: $surface;
        layout: horizontal;
    }
    
    FileEditorPanel .file-browser {
        width: 30%;
        min-width: 20;
        height: 100%;
        background: $panel;
        border-right: solid $primary;
        padding: 1;
    }
    
    FileEditorPanel .editor-container {
        width: 70%;
        height: 100%;
        padding: 1;
    }
    
    FileEditorPanel .editor-header {
        height: 3;
        background: $boost;
        padding: 0 1;
        margin-bottom: 1;
    }
    
    FileEditorPanel .code-editor {
        height: 1fr;
        background: $surface-lighten-1;
    }
    
    FileEditorPanel Tree {
        height: 100%;
        background: transparent;
    }
    
    FileEditorPanel .action-buttons {
        height: 3;
        layout: horizontal;
        margin-top: 1;
    }
    
    FileEditorPanel Button {
        margin: 0 1;
    }
    """
    
    def __init__(self, **kwargs):
        """Initialize the File Editor panel."""
        super().__init__(**kwargs)
        self._init_params = kwargs
        self.current_file = None
        self.source_root = Path.cwd()  # Default to current directory
        self.on_edit_request: Optional[Callable] = None
        
    def compose(self) -> ComposeResult:
        """Compose the file editor panel layout."""
        with Horizontal():
            # File browser
            with VerticalScroll(classes="file-browser"):
                yield Label("📁 Source Files", classes="header")
                yield Tree("Source", id="file-tree")
            
            # Editor
            with Vertical(classes="editor-container"):
                with Horizontal(classes="editor-header"):
                    yield Label("No file selected", id="current-file-label")
                
                yield TextArea(
                    "",
                    language="python",
                    theme="monokai",
                    id="code-editor",
                    classes="code-editor"
                )
                
                with Horizontal(classes="action-buttons"):
                    yield Button("💾 Save", id="save-btn", variant="primary")
                    yield Button("🤖 Ask Claude", id="claude-btn", variant="success")
                    yield Button("🔄 Reload", id="reload-btn")
                    yield Button("↩️ Undo", id="undo-btn")
    
    def on_mount(self) -> None:
        """Initialize the file tree when mounted."""
        tree = self.query_one("#file-tree", Tree)
        tree.guide_depth = 4
        tree.show_root = True
        
        # Build the file tree
        self._build_file_tree(tree.root, self.source_root)
        
    def _build_file_tree(self, node: TreeNode, path: Path) -> None:
        """Recursively build the file tree."""
        try:
            # Skip certain directories
            skip_dirs = {'.git', '__pycache__', 'venv', '.venv', 'node_modules', '.mypy_cache', 'logs'}
            
            for item in sorted(path.iterdir()):
                if item.name.startswith('.') and item.name not in {'.morph'}:
                    continue
                    
                if item.is_dir():
                    if item.name in skip_dirs:
                        continue
                    dir_node = node.add(f"📁 {item.name}", expand=False)
                    dir_node.data = item
                    # Add children lazily
                    self._build_file_tree(dir_node, item)
                else:
                    # Only show Python files and config files
                    if item.suffix in {'.py', '.yaml', '.yml', '.toml', '.json', '.md'}:
                        icon = "🐍" if item.suffix == '.py' else "📄"
                        file_node = node.add(f"{icon} {item.name}")
                        file_node.data = item
                        
        except PermissionError:
            logging.warning(f"Permission denied accessing {path}")
    
    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle file selection in the tree."""
        node = event.node
        if hasattr(node, 'data') and node.data and node.data.is_file():
            await self._load_file(node.data)
    
    async def _load_file(self, file_path: Path) -> None:
        """Load a file into the editor."""
        try:
            self.current_file = file_path
            
            # Update header
            label = self.query_one("#current-file-label", Label)
            relative_path = file_path.relative_to(self.source_root)
            label.update(f"📝 {relative_path}")
            
            # Load content
            content = file_path.read_text(encoding='utf-8')
            editor = self.query_one("#code-editor", TextArea)
            editor.load_text(content)
            
            # Set language based on file extension
            if file_path.suffix == '.py':
                editor.language = "python"
            elif file_path.suffix in {'.yaml', '.yml'}:
                editor.language = "yaml"
            elif file_path.suffix == '.json':
                editor.language = "json"
            elif file_path.suffix == '.md':
                editor.language = "markdown"
            else:
                editor.language = None
                
            logging.info(f"Loaded file: {file_path}")
            
        except Exception as e:
            logging.error(f"Error loading file {file_path}: {e}")
            self.app.notify(f"Error loading file: {e}", severity="error")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "save-btn":
            await self._save_current_file()
        elif button_id == "claude-btn":
            await self._ask_claude_about_code()
        elif button_id == "reload-btn":
            await self._reload_current_file()
        elif button_id == "undo-btn":
            await self._undo_changes()
        else:
            # Let BasePanel handle other buttons
            await super().on_button_pressed(event)
    
    async def _save_current_file(self) -> None:
        """Save the current file."""
        if not self.current_file:
            self.app.notify("No file selected", severity="warning")
            return
            
        try:
            editor = self.query_one("#code-editor", TextArea)
            content = editor.text
            
            # Write to file
            self.current_file.write_text(content, encoding='utf-8')
            
            self.app.notify(f"Saved {self.current_file.name}", severity="information")
            logging.info(f"Saved file: {self.current_file}")
            
            # If this is a panel file, offer to reload it
            if self.current_file.parent.name == "panels":
                self.app.notify("Panel saved! Press F5 to reload panels.", severity="information")
                
        except Exception as e:
            logging.error(f"Error saving file: {e}")
            self.app.notify(f"Error saving file: {e}", severity="error")
    
    async def _ask_claude_about_code(self) -> None:
        """Send the current code to Claude for analysis/modification."""
        if not self.current_file:
            self.app.notify("No file selected", severity="warning")
            return
            
        editor = self.query_one("#code-editor", TextArea)
        code = editor.text
        
        if not code.strip():
            self.app.notify("No code to analyze", severity="warning")
            return
        
        # Create a prompt for Claude
        relative_path = self.current_file.relative_to(self.source_root)
        prompt = f"I'm looking at the file {relative_path}. Here's the current code:\n\n```python\n{code}\n```\n\nPlease help me understand or improve this code."
        
        # Send to main prompt panel if available
        try:
            # Find the prompt panel in the main tab
            main_app = self.app
            if hasattr(main_app, 'panels') and 'prompt' in main_app.panels:
                prompt_panel = main_app.panels['prompt']
                if hasattr(prompt_panel, 'set_prompt'):
                    prompt_panel.set_prompt(prompt)
                    # Switch to main tab
                    main_app.action_main_tab()
                    self.app.notify("Prompt sent to main panel", severity="information")
                else:
                    self.app.notify("Could not send to prompt panel", severity="error")
            else:
                # Just copy to clipboard as fallback
                import pyperclip
                pyperclip.copy(prompt)
                self.app.notify("Prompt copied to clipboard", severity="information")
        except Exception as e:
            logging.error(f"Error sending to Claude: {e}")
            self.app.notify(f"Error: {e}", severity="error")
    
    async def _reload_current_file(self) -> None:
        """Reload the current file from disk."""
        if self.current_file:
            await self._load_file(self.current_file)
            self.app.notify("File reloaded", severity="information")
    
    async def _undo_changes(self) -> None:
        """Undo changes in the editor."""
        editor = self.query_one("#code-editor", TextArea)
        # TextArea doesn't have built-in undo yet, so just reload
        if self.current_file:
            await self._reload_current_file()
            self.app.notify("Changes reverted", severity="information")