#!/usr/bin/env python3
"""Tests specifically for ContextPanel DOMQuery issues."""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from textual.widgets import DataTable, Label, Input
from claude_code_morph.panels.ContextPanel import ContextPanel


class MockApp:
    """Mock app for testing panels in isolation."""
    def notify(self, message, severity="info", timeout=3):
        pass


class TestContextPanelDOMQueries:
    """Test ContextPanel's DOM query error handling."""
    
    @pytest.mark.asyncio
    async def test_context_panel_handles_missing_widgets(self):
        """Test that ContextPanel handles missing widgets gracefully."""
        # Create panel with mocked dependencies
        panel = ContextPanel()
        panel.context_available = True
        panel._app = MockApp()  # Use _app instead of app
        
        # Mock query_one to raise exception (widget not found)
        with patch.object(panel, 'query_one', side_effect=Exception("No widget found")):
            # These should not crash
            panel._refresh_table()
            panel.action_focus_search()
            panel.on_click(MagicMock(x=10, y=10))
            
            # Panel should handle the errors gracefully
            assert True  # If we get here, no crash occurred
    
    @pytest.mark.asyncio
    async def test_on_mount_missing_table(self):
        """Test on_mount handles missing context table."""
        panel = ContextPanel()
        panel.context_available = True
        panel._app = MockApp()  # Use _app instead of app
        
        # Mock the parent on_mount
        with patch('claude_code_morph.panels.BasePanel.BasePanel.on_mount', new_callable=AsyncMock):
            # Mock query_one to fail
            with patch.object(panel, 'query_one', side_effect=Exception("No table")):
                # Should not crash
                panel.on_mount()
    
    def test_refresh_table_with_no_entries(self):
        """Test _refresh_table with empty entries."""
        panel = ContextPanel()
        panel.context_available = True
        panel.filtered_entries = []
        
        # Create a mock table
        mock_table = MagicMock(spec=DataTable)
        
        with patch.object(panel, 'query_one', return_value=mock_table):
            panel._refresh_table()
            
            # Should have cleared the table
            mock_table.clear.assert_called_once()
    
    def test_update_stats_with_mock_label(self):
        """Test stats update doesn't crash with mock label."""
        panel = ContextPanel()
        panel.context_available = True
        panel.context_entries = [{"id": "1", "text": "Entry 1", "source": "test", "type": "test", "relevance": 0.9, "weight": 1.0}, 
                                  {"id": "2", "text": "Entry 2", "source": "test", "type": "test", "relevance": 0.8, "weight": 1.0}]
        panel.filtered_entries = [{"id": "1", "text": "Entry 1", "source": "test", "type": "test", "relevance": 0.9, "weight": 1.0}]
        
        # Mock the table and label separately
        mock_table = MagicMock(spec=DataTable)
        mock_label = MagicMock(spec=Label)
        
        def mock_query_one(selector, widget_type=None):
            if selector == "#context-table":
                return mock_table
            elif selector == "#stats-label":
                return mock_label
            raise Exception(f"No widget found: {selector}")
        
        with patch.object(panel, 'query_one', side_effect=mock_query_one):
            # Call the refresh which updates stats
            panel._refresh_table()
            
            # Should have cleared the table and updated stats
            mock_table.clear.assert_called_once()
            mock_label.update.assert_called()
    
    def test_cell_highlighted_event_handling(self):
        """Test cell highlighted event doesn't crash on errors."""
        panel = ContextPanel()
        panel.context_available = True
        
        # Create mock event
        mock_event = MagicMock()
        mock_event.coordinate.column = 5
        mock_event.coordinate.row = 0
        
        # Mock query_one to fail
        with patch.object(panel, 'query_one', side_effect=Exception("No table")):
            # Should not crash
            panel.on_data_table_cell_highlighted(mock_event)
    
    def test_click_event_outside_table(self):
        """Test click events outside table don't crash."""
        panel = ContextPanel()
        panel.context_available = True
        
        # Create mock event
        mock_event = MagicMock()
        mock_event.x = 100
        mock_event.y = 100
        
        # Mock table that doesn't contain the click
        mock_table = MagicMock()
        mock_table.region.contains.return_value = False
        
        with patch.object(panel, 'query_one', return_value=mock_table):
            # Should handle gracefully
            panel.on_click(mock_event)
            
            # Should have checked if click was in table
            mock_table.region.contains.assert_called_with(100, 100)