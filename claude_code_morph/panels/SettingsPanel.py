"""Settings Panel - Edit Claude Code CLI configuration files."""

import os
import json
import yaml
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Union
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Label, Tree, Button, TextArea
from textual.widgets.tree import TreeNode
from textual.reactive import reactive
from textual.binding import Binding
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


class ConfigFile:
    """Represents a configuration file."""
    
    def __init__(self, path: Path, display_name: str, description: str = "", 
                 file_type: str = "json", schema: Optional[Dict] = None):
        self.path = path
        self.display_name = display_name
        self.description = description
        self.file_type = file_type
        self.schema = schema
        self.exists = path.exists() if path else False
        self.is_readable = os.access(path, os.R_OK) if self.exists else False
        self.is_writable = os.access(path, os.W_OK) if self.exists else True
        

class SettingsPanel(BasePanel):
    """Panel for editing Claude Code CLI configuration files."""
    
    CSS = BasePanel.CSS + """
    SettingsPanel {
        background: $surface;
        layout: horizontal;
        height: 100%;
    }
    
    SettingsPanel .file-browser {
        width: 35%;
        min-width: 30;
        height: 100%;
        background: $panel;
        border-right: solid $primary;
        padding: 1 2;
    }
    
    SettingsPanel .file-browser Label.header {
        text-style: bold;
        color: $text;
        margin: 0 0 1 0;
        padding: 1 0;
    }
    
    SettingsPanel .editor-container {
        width: 65%;
        height: 100%;
        padding: 1 2;
        layout: vertical;
    }
    
    SettingsPanel .editor-header {
        height: auto;
        background: transparent;
        padding: 0;
        margin-bottom: 1;
        layout: vertical;
    }
    
    SettingsPanel #current-file-label {
        text-style: bold;
        color: $text;
        margin: 0 0 1 0;
    }
    
    SettingsPanel .editor-description {
        color: $text-muted;
        margin: 0 0 1 0;
        text-style: italic;
    }
    
    SettingsPanel .code-editor {
        height: 1fr;
        background: $surface-lighten-1;
        border: tall $primary;
        padding: 1;
    }
    
    SettingsPanel Tree {
        height: 1fr;
        background: transparent;
        padding: 0;
        color: $text;
    }
    
    SettingsPanel Tree > TreeNode {
        color: $text;
    }
    
    SettingsPanel .action-buttons {
        height: auto;
        layout: horizontal;
        margin: 1 0;
        align: right;
        dock: bottom;
    }
    
    SettingsPanel .action-buttons Button {
        margin: 0 0 0 1;
        min-width: 12;
    }
    
    SettingsPanel .status-bar {
        height: 1;
        background: transparent;
        padding: 0;
        margin: 1 0 0 0;
        color: $text-muted;
        dock: bottom;
    }
    
    SettingsPanel .error-message {
        color: $error;
        margin: 1 0;
    }
    
    SettingsPanel .success-message {
        color: $success;
        margin: 1 0;
    }
    """
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+s", "save_file", "Save", show=True),
        Binding("ctrl+r", "reload_file", "Reload", show=True),
        Binding("ctrl+shift+b", "backup_file", "Backup", show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the Settings panel."""
        super().__init__(**kwargs)
        self.current_file: Optional[ConfigFile] = None
        self.original_content: Optional[str] = None
        self.has_changes = False
        self.config_files: Dict[str, ConfigFile] = self._build_config_tree()
        
    def _build_config_tree(self) -> Dict[str, ConfigFile]:
        """Build the configuration file tree structure."""
        home = Path.home()
        claude_dir = home / ".claude"
        morph_app_dir = home / ".claude-code-morph"
        project_dir = Path.cwd()
        project_claude_dir = project_dir / ".claude"
        project_morph_dir = project_dir / ".morph"
        
        files = {
            # Global Claude settings
            "global/config.json": ConfigFile(
                claude_dir / "config.json",
                "config.json",
                "MCP (Model Context Protocol) server configurations",
                "json"
            ),
            "global/settings.json": ConfigFile(
                claude_dir / "settings.json",
                "settings.json",
                "Global permission settings",
                "json"
            ),
            "global/settings.local.json": ConfigFile(
                claude_dir / "settings.local.json",
                "settings.local.json",
                "User-specific permission overrides",
                "json"
            ),
            "global/CLAUDE.md": ConfigFile(
                claude_dir / "CLAUDE.md",
                "CLAUDE.md",
                "Global memory file - instructions for all projects",
                "markdown"
            ),
            "global/claude_desktop_config.json": ConfigFile(
                claude_dir / "claude_desktop_config.json",
                "claude_desktop_config.json",
                "Claude Desktop MCP server configurations",
                "json"
            ),
            
            # Application settings
            "app/config.yaml": ConfigFile(
                morph_app_dir / "config.yaml",
                "config.yaml",
                "Claude Code Morph application settings",
                "yaml"
            ),
            
            # Project settings
            "project/settings.local.json": ConfigFile(
                project_claude_dir / "settings.local.json",
                "settings.local.json",
                f"Project-specific permissions for {project_dir.name}",
                "json"
            ),
            "project/meta.json": ConfigFile(
                project_morph_dir / "meta.json",
                "meta.json",
                "Project metadata and configuration",
                "json"
            ),
            "project/session.json": ConfigFile(
                project_morph_dir / "session.json",
                "session.json",
                "Current session state",
                "json"
            ),
        }
        
        return files
        
    def compose_content(self) -> ComposeResult:
        """Compose the settings panel layout."""
        with Horizontal():
            # File browser
            with Vertical(classes="file-browser"):
                yield Label("⚙️  Configuration Files", classes="header")
                with VerticalScroll():
                    yield Tree("Settings", id="config-tree")
            
            # Editor
            with Vertical(classes="editor-container"):
                with Vertical(classes="editor-header"):
                    yield Label("Select a configuration file", id="current-file-label")
                    yield Static("", id="file-description", classes="editor-description")
                
                yield TextArea(
                    "Select a configuration file from the tree to edit",
                    language="json",
                    theme="monokai",
                    id="config-editor",
                    classes="code-editor",
                    tab_behavior="indent",
                    show_line_numbers=True
                )
                
                # Action buttons
                with Horizontal(classes="action-buttons"):
                    yield Button("↻ Reload", id="reload-btn", variant="default")
                    yield Button("💾 Save", id="save-btn", variant="primary")
                    yield Button("🔧 Validate", id="validate-btn", variant="default")
                    yield Button("📋 Backup", id="backup-btn", variant="default")
                
                # Status bar
                yield Static("Ready", id="status-bar", classes="status-bar")
                
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        await super().on_mount()
        
        # Build the file tree
        tree = self.query_one("#config-tree", Tree)
        tree.clear()
        
        # Add global settings
        global_node = tree.root.add("🌍 Global Settings (~/.claude/)")
        for key, config in self.config_files.items():
            if key.startswith("global/"):
                icon = "📄" if config.exists else "⚠️"
                node = global_node.add(f"{icon} {config.display_name}", data=key)
                if not config.exists:
                    node.label = Text(f"{icon} {config.display_name} (not found)", style="dim")
                elif not config.is_readable:
                    node.label = Text(f"{icon} {config.display_name} (no read permission)", style="red")
        
        # Add application settings
        app_node = tree.root.add("🚀 Application Settings")
        for key, config in self.config_files.items():
            if key.startswith("app/"):
                icon = "📄" if config.exists else "⚠️"
                node = app_node.add(f"{icon} {config.display_name}", data=key)
                if not config.exists:
                    node.label = Text(f"{icon} {config.display_name} (not found)", style="dim")
        
        # Add project settings
        project_node = tree.root.add(f"📁 Project Settings ({Path.cwd().name})")
        for key, config in self.config_files.items():
            if key.startswith("project/"):
                icon = "📄" if config.exists else "⚠️"
                node = project_node.add(f"{icon} {config.display_name}", data=key)
                if not config.exists:
                    node.label = Text(f"{icon} {config.display_name} (not found)", style="dim")
        
        # Expand all nodes
        for node in tree.root.children:
            node.expand()
            
    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        if event.node.data:
            await self.load_config_file(event.node.data)
            
    async def load_config_file(self, file_key: str) -> None:
        """Load a configuration file into the editor."""
        config = self.config_files.get(file_key)
        if not config:
            return
            
        self.current_file = config
        editor = self.query_one("#config-editor", TextArea)
        file_label = self.query_one("#current-file-label", Label)
        description = self.query_one("#file-description", Static)
        status = self.query_one("#status-bar", Static)
        
        # Update header
        file_label.update(f"📝 {config.path}")
        description.update(config.description)
        
        # Load file content
        if config.exists and config.is_readable:
            try:
                content = config.path.read_text()
                self.original_content = content
                
                # Set appropriate language for syntax highlighting
                if config.file_type == "json":
                    editor.language = "json"
                elif config.file_type == "yaml":
                    editor.language = "yaml"
                elif config.file_type == "markdown":
                    editor.language = "markdown"
                else:
                    editor.language = None
                    
                editor.text = content
                editor.read_only = not config.is_writable
                
                if not config.is_writable:
                    status.update("⚠️ File is read-only")
                else:
                    status.update(f"✓ Loaded {len(content)} bytes")
                    
                self.has_changes = False
                
            except Exception as e:
                editor.text = f"Error loading file: {e}"
                editor.read_only = True
                status.update(f"❌ Error: {e}")
                logging.error(f"Error loading config file {config.path}: {e}")
        else:
            # File doesn't exist - show template
            template = self._get_file_template(config)
            editor.text = template
            editor.read_only = False
            self.original_content = ""
            status.update("📝 New file - will be created on save")
            self.has_changes = True
            
    def _get_file_template(self, config: ConfigFile) -> str:
        """Get a template for a new configuration file."""
        templates = {
            "config.json": """{
  "mcpServers": {
    "example-server": {
      "command": "node",
      "args": ["/path/to/server.js"]
    }
  }
}""",
            "settings.json": """{
  "permissions": {
    "allow": [],
    "deny": []
  }
}""",
            "settings.local.json": """{
  "permissions": {
    "allow": [],
    "deny": []
  }
}""",
            "CLAUDE.md": """## 📖 COMMANDS:
- **/context** - Read all context files
- **/help** - Show available commands

## 🚨 CRITICAL RULES:
- Always follow user instructions exactly
- Never make assumptions without asking

## 📋 PROJECT NOTES:
- Add project-specific notes here
""",
            "config.yaml": """# Claude Code Morph Configuration
theme: dark
auto_save_workspace: true
hot_reload_enabled: true
startup_workspace: default.yaml

# Claude CLI Settings
claude_auto_start: true

# Optimizer Settings
optimizer_enabled: true
optimizer_model: llama-4-maverick-17Bx128E
optimizer_api: groq
""",
            "meta.json": """{
  "name": "Project Name",
  "description": "Project description",
  "created_at": "2024-01-01T00:00:00Z",
  "root_path": "."
}""",
            "session.json": """{
  "workspace": "default.yaml",
  "panels": {},
  "saved_at": "2024-01-01T00:00:00Z"
}"""
        }
        
        return templates.get(config.display_name, "{}")
        
    async def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle text changes in the editor."""
        if self.current_file and self.original_content is not None:
            editor = self.query_one("#config-editor", TextArea)
            self.has_changes = editor.text != self.original_content
            
            status = self.query_one("#status-bar", Static)
            if self.has_changes:
                status.update("✏️ Modified - press Ctrl+S to save")
            else:
                status.update("✓ No changes")
                
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save-btn":
            await self.action_save_file()
        elif event.button.id == "reload-btn":
            await self.action_reload_file()
        elif event.button.id == "validate-btn":
            await self.validate_current_file()
        elif event.button.id == "backup-btn":
            await self.action_backup_file()
            
    async def action_save_file(self) -> None:
        """Save the current file."""
        if not self.current_file:
            self.notify("No file selected", severity="warning")
            return
            
        editor = self.query_one("#config-editor", TextArea)
        status = self.query_one("#status-bar", Static)
        content = editor.text
        
        # Validate before saving
        is_valid, error = self._validate_content(content, self.current_file.file_type)
        if not is_valid:
            status.update(f"❌ Validation error: {error}")
            self.notify(f"Cannot save: {error}", severity="error")
            return
            
        try:
            # Create backup if file exists
            if self.current_file.exists:
                backup_path = self.current_file.path.with_suffix(
                    self.current_file.path.suffix + ".backup"
                )
                shutil.copy2(self.current_file.path, backup_path)
                
            # Ensure parent directory exists
            self.current_file.path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            self.current_file.path.write_text(content)
            self.original_content = content
            self.has_changes = False
            
            # Update file status
            self.current_file.exists = True
            self.current_file.is_readable = True
            self.current_file.is_writable = True
            
            status.update(f"✅ Saved at {datetime.now().strftime('%H:%M:%S')}")
            self.notify(f"Saved {self.current_file.display_name}", severity="success")
            
            # Refresh tree to update icons
            await self.on_mount()
            
        except Exception as e:
            status.update(f"❌ Save failed: {e}")
            self.notify(f"Failed to save: {e}", severity="error")
            logging.error(f"Error saving config file: {e}")
            
    async def action_reload_file(self) -> None:
        """Reload the current file from disk."""
        if not self.current_file:
            self.notify("No file selected", severity="warning")
            return
            
        if self.has_changes:
            # TODO: Add confirmation dialog
            pass
            
        await self.load_config_file(
            next(k for k, v in self.config_files.items() if v == self.current_file)
        )
        self.notify("File reloaded", severity="information")
        
    async def action_backup_file(self) -> None:
        """Create a backup of the current file."""
        if not self.current_file or not self.current_file.exists:
            self.notify("No file to backup", severity="warning")
            return
            
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.current_file.path.with_name(
                f"{self.current_file.path.stem}_{timestamp}{self.current_file.path.suffix}"
            )
            shutil.copy2(self.current_file.path, backup_path)
            self.notify(f"Backup created: {backup_path.name}", severity="success")
        except Exception as e:
            self.notify(f"Backup failed: {e}", severity="error")
            
    async def validate_current_file(self) -> None:
        """Validate the current file content."""
        if not self.current_file:
            return
            
        editor = self.query_one("#config-editor", TextArea)
        status = self.query_one("#status-bar", Static)
        
        is_valid, error = self._validate_content(editor.text, self.current_file.file_type)
        if is_valid:
            status.update("✅ Validation passed")
            self.notify("File is valid", severity="success")
        else:
            status.update(f"❌ Validation error: {error}")
            self.notify(f"Validation error: {error}", severity="error")
            
    def _validate_content(self, content: str, file_type: str) -> tuple[bool, Optional[str]]:
        """Validate file content based on type."""
        if not content.strip():
            return True, None  # Empty content is valid
            
        try:
            if file_type == "json":
                json.loads(content)
            elif file_type == "yaml":
                yaml.safe_load(content)
            # Markdown doesn't need validation
            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {e}"
        except yaml.YAMLError as e:
            return False, f"Invalid YAML: {e}"
        except Exception as e:
            return False, str(e)