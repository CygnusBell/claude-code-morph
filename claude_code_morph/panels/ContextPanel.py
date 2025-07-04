"""Context Panel - Display and manage context entries from ChromaDB."""

import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Label, DataTable, Button, Input
from textual.reactive import reactive
from textual.binding import Binding
from rich.text import Text

try:
    from .BasePanel import BasePanel
except ImportError:
    # When loaded dynamically, use absolute import
    import sys
    from pathlib import Path as PathLib
    sys.path.append(str(PathLib(__file__).parent.parent))
    from panels.BasePanel import BasePanel


class ContextPanel(BasePanel):
    """Panel for displaying and managing context entries from ChromaDB."""
    
    DEFAULT_CSS = """
    ContextPanel {
        background: $surface;
        layout: vertical;
    }
    
    ContextPanel .search-container {
        height: 3;
        background: $boost;
        padding: 0 1;
        layout: horizontal;
        align: center middle;
    }
    
    ContextPanel #search-input {
        width: 1fr;
        margin: 0 1;
    }
    
    ContextPanel .refresh-button {
        width: 10;
        margin: 0 1;
    }
    
    ContextPanel .context-table-container {
        height: 1fr;
        background: $surface;
        padding: 1;
    }
    
    ContextPanel DataTable {
        height: 100%;
        background: $surface-lighten-1;
    }
    
    ContextPanel .stats-footer {
        height: 3;
        background: $boost;
        padding: 0 1;
        layout: horizontal;
        align: center middle;
    }
    
    ContextPanel .stats-label {
        width: 1fr;
        text-align: left;
        color: $text-muted;
    }
    """
    
    BINDINGS = [
        Binding("r", "refresh", "Refresh", priority=True),
        Binding("ctrl+f", "focus_search", "Search", priority=True),
        Binding("delete", "delete_selected", "Delete", priority=True),
        Binding("d", "delete_selected", "Delete", priority=True),
        Binding("u", "upvote_selected", "Upvote", priority=True),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the Context panel."""
        super().__init__(**kwargs)
        self.search_query = reactive("")
        self.context_entries: List[Dict[str, Any]] = []
        self.filtered_entries: List[Dict[str, Any]] = []
        self.selected_row: Optional[int] = None
        self.context_integration = None  # Will be set by app
        
        # Initialize with sample data for now (replace with ChromaDB later)
        self._init_sample_data()
        
    def _init_sample_data(self):
        """Initialize with sample context data (temporary until ChromaDB integration)."""
        self.context_entries = [
            {
                "id": "ctx_001",
                "text": "The application uses Textual framework for the TUI interface",
                "source": "README.md",
                "type": "documentation",
                "relevance": 0.95,
                "weight": 1.0,
                "timestamp": datetime.now()
            },
            {
                "id": "ctx_002",
                "text": "BasePanel is the parent class for all panel implementations",
                "source": "BasePanel.py",
                "type": "code",
                "relevance": 0.88,
                "weight": 1.2,
                "timestamp": datetime.now()
            },
            {
                "id": "ctx_003",
                "text": "Claude CLI is used for AI interactions in terminal panels",
                "source": "CLITerminalPanel.py",
                "type": "code",
                "relevance": 0.82,
                "weight": 1.0,
                "timestamp": datetime.now()
            },
            {
                "id": "ctx_004",
                "text": "The app supports hot-reloading panels with F5 key",
                "source": "main.py",
                "type": "feature",
                "relevance": 0.76,
                "weight": 0.8,
                "timestamp": datetime.now()
            },
        ]
        self.filtered_entries = self.context_entries.copy()
        
    def compose_content(self) -> ComposeResult:
        """Compose the context panel layout."""
        # Search container
        with Horizontal(classes="search-container"):
            yield Input(
                placeholder="Search context...",
                id="search-input"
            )
            yield Button("🔄 Refresh", classes="refresh-button", id="refresh-btn")
        
        # Context table
        with VerticalScroll(classes="context-table-container"):
            table = DataTable(id="context-table")
            yield table
        
        # Stats footer
        with Horizontal(classes="stats-footer"):
            yield Label(
                f"Total: {len(self.context_entries)} entries",
                id="stats-label",
                classes="stats-label"
            )
    
    def on_mount(self) -> None:
        """Initialize the data table when mounted."""
        super().on_mount()
        
        # Get the data table
        table = self.query_one("#context-table", DataTable)
        
        # Configure table
        table.cursor_type = "row"
        table.zebra_stripes = True
        
        # Add columns
        table.add_column("Context", width=50)
        table.add_column("Source", width=20)
        table.add_column("Type", width=12)
        table.add_column("Score", width=8)
        table.add_column("Weight", width=8)
        table.add_column("Actions", width=10)
        
        # Load initial data
        self._refresh_table()
        
        # If we have context integration, register for updates
        if self.context_integration:
            self.context_integration.register_ui_update_callback(self._on_context_updated)
        
    def _refresh_table(self) -> None:
        """Refresh the table with current filtered entries."""
        table = self.query_one("#context-table", DataTable)
        
        # Clear existing rows
        table.clear()
        
        # Add filtered entries
        for entry in self.filtered_entries:
            # Truncate text if too long
            text = entry['text']
            if len(text) > 47:
                text = text[:44] + "..."
            
            # Format relevance score
            score = f"{entry['relevance']:.2f}"
            
            # Format weight
            weight = f"{entry['weight']:.1f}x"
            
            # Create action buttons text
            actions = "👍 🗑️"
            
            # Add row
            table.add_row(
                text,
                entry['source'],
                entry['type'],
                score,
                weight,
                actions,
                key=entry['id']
            )
        
        # Update stats
        stats_label = self.query_one("#stats-label", Label)
        stats_label.update(
            f"Total: {len(self.context_entries)} entries | "
            f"Shown: {len(self.filtered_entries)}"
        )
    
    async def load_context_from_chromadb(self) -> None:
        """Load context entries from ChromaDB."""
        if not self.context_integration:
            logging.warning("No context integration available, using sample data")
            return
            
        logging.info("Loading context from ChromaDB")
        
        try:
            # Get all entries from ChromaDB
            self.context_entries = self.context_integration.get_all_context_entries()
            
            # Apply current search filter
            self._apply_search_filter()
            
        except Exception as e:
            logging.error(f"Error loading from ChromaDB: {e}")
            # Fall back to sample data if needed
            if not self.context_entries:
                self._init_sample_data()
                self._apply_search_filter()
        
    def handle_thumbs_up(self, entry_id: str) -> None:
        """Increase weight for a context entry."""
        for entry in self.context_entries:
            if entry['id'] == entry_id:
                # Increase weight by 0.2
                new_weight = min(entry['weight'] + 0.2, 2.0)
                
                # Update in ChromaDB if integration available
                if self.context_integration:
                    if self.context_integration.update_weight(entry_id, new_weight):
                        entry['weight'] = new_weight
                        logging.info(f"Increased weight for {entry_id} to {new_weight}")
                    else:
                        logging.error(f"Failed to update weight in ChromaDB for {entry_id}")
                        return
                else:
                    # Just update locally if no integration
                    entry['weight'] = new_weight
                
                # Refresh display
                self._refresh_table()
                
                # Notify user
                if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                    self.app.notify(f"Weight increased to {entry['weight']:.1f}x", severity="success")
                break
    
    def handle_delete(self, entry_id: str) -> None:
        """Remove a context entry from the database."""
        # Find and remove the entry
        for i, entry in enumerate(self.context_entries):
            if entry['id'] == entry_id:
                # Delete from ChromaDB if integration available
                if self.context_integration:
                    if self.context_integration.delete_entry(entry_id):
                        removed = self.context_entries.pop(i)
                        logging.info(f"Deleted context entry: {entry_id}")
                    else:
                        logging.error(f"Failed to delete from ChromaDB: {entry_id}")
                        if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                            self.app.notify("Failed to delete entry", severity="error")
                        return
                else:
                    # Just remove locally if no integration
                    removed = self.context_entries.pop(i)
                
                # Also remove from filtered entries
                self.filtered_entries = [e for e in self.filtered_entries if e['id'] != entry_id]
                
                # Refresh display
                self._refresh_table()
                
                # Notify user
                if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                    self.app.notify(f"Deleted: {removed['text'][:30]}...", severity="warning")
                break
    
    def search_context(self, query: str) -> None:
        """Search/filter context entries."""
        self.search_query = query
        
        if self.context_integration and query.strip():
            # Use semantic search from ChromaDB
            try:
                self.filtered_entries = self.context_integration.search_context(query)
                self._refresh_table()
            except Exception as e:
                logging.error(f"Error performing semantic search: {e}")
                # Fall back to simple filtering
                self._apply_search_filter()
        else:
            # Use simple filtering for empty query or no integration
            self._apply_search_filter()
    
    def _apply_search_filter(self) -> None:
        """Apply the current search filter to entries."""
        if not self.search_query:
            self.filtered_entries = self.context_entries.copy()
        else:
            self.filtered_entries = [
                entry for entry in self.context_entries
                if (self.search_query in entry['text'].lower() or
                    self.search_query in entry['source'].lower() or
                    self.search_query in entry['type'].lower())
            ]
        
        # Sort by relevance score (descending)
        self.filtered_entries.sort(key=lambda e: e['relevance'], reverse=True)
        
        # Refresh table
        self._refresh_table()
    
    def refresh_display(self) -> None:
        """Refresh the context display."""
        # Reload from database
        asyncio.create_task(self.load_context_from_chromadb())
    
    # Event handlers
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.search_context(event.value)
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh-btn":
            self.refresh_display()
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in the data table."""
        self.selected_row = event.row_key.value if event.row_key else None
    
    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        """Handle cell highlighting for action buttons."""
        # Check if we're in the Actions column (column 5)
        if event.coordinate.column == 5 and event.coordinate.row >= 0:
            # Get the row key
            table = self.query_one("#context-table", DataTable)
            row_key = table.get_row_at(event.coordinate.row)[0]
            
            # Check mouse position within the cell to determine which button
            # This is a simplified version - in a real implementation,
            # you might want to use actual button widgets
            cell_value = event.value
            if "👍" in str(cell_value):
                # Hovering over thumbs up area
                if hasattr(self, 'app') and hasattr(self.app, 'notify'):
                    self.app.notify("Click to increase weight", severity="information", timeout=1)
    
    def on_click(self, event) -> None:
        """Handle click events for action buttons."""
        # Try to determine if click is on a table cell
        table = self.query_one("#context-table", DataTable)
        
        # Convert click coordinates to table cell
        # This is a simplified approach - might need refinement
        if table.region.contains(event.x, event.y):
            # Calculate relative position
            rel_x = event.x - table.region.x
            rel_y = event.y - table.region.y
            
            # Try to get the cell at this position
            # Note: This is approximate and might need adjustment
            try:
                # Get currently highlighted cell
                if hasattr(table, 'cursor_coordinate'):
                    coord = table.cursor_coordinate
                    if coord and coord.column == 5:  # Actions column
                        # Get row key
                        row_data = table.get_row_at(coord.row)
                        if row_data:
                            entry_id = row_data[0]  # First element is the key
                            
                            # Simple position-based detection
                            # Thumbs up is roughly in first half, delete in second half
                            cell_width = table.columns[5].width
                            if rel_x < cell_width // 2:
                                self.handle_thumbs_up(entry_id)
                            else:
                                self.handle_delete(entry_id)
            except Exception as e:
                logging.debug(f"Error handling table click: {e}")
    
    # Action methods
    
    def action_refresh(self) -> None:
        """Refresh the context display."""
        self.refresh_display()
    
    def action_focus_search(self) -> None:
        """Focus the search input."""
        search_input = self.query_one("#search-input", Input)
        search_input.focus()
    
    def action_delete_selected(self) -> None:
        """Delete the selected context entry."""
        if self.selected_row:
            self.handle_delete(self.selected_row)
    
    def action_upvote_selected(self) -> None:
        """Upvote the selected context entry."""
        if self.selected_row:
            self.handle_thumbs_up(self.selected_row)
    
    def _on_context_updated(self) -> None:
        """Called when context is updated externally."""
        # Reload context from ChromaDB
        asyncio.create_task(self.load_context_from_chromadb())
        
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel."""
        lines = ["Context Entries:"]
        lines.append("-" * 80)
        
        for entry in self.filtered_entries:
            lines.append(f"Text: {entry['text']}")
            lines.append(f"Source: {entry['source']} | Type: {entry['type']}")
            lines.append(f"Relevance: {entry['relevance']:.2f} | Weight: {entry['weight']:.1f}x")
            lines.append("-" * 80)
        
        return "\n".join(lines)