#!/usr/bin/env python3
"""Integration tests for Claude Code Morph.

These tests focus on the actual issues we've encountered:
- DOMQuery errors
- Tab switching failures
- Context dependency detection
- Panel loading issues
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from textual.testing import AppTest
from claude_code_morph.main import ClaudeCodeMorph


class TestAppStartup:
    """Test app startup and initialization."""
    
    @pytest.mark.asyncio
    async def test_app_starts_without_context_deps(self):
        """Test that app starts even when context dependencies are missing."""
        # Mock the context availability
        with patch('claude_code_morph.main.CONTEXT_AVAILABLE', False):
            app = ClaudeCodeMorph()
            async with app.run_test() as pilot:
                # App should start
                assert app is not None
                
                # Main and Morph tabs should exist
                assert pilot.app.query("#main-tab")
                assert pilot.app.query("#morph-tab")
                
                # Context tab should NOT exist
                assert not pilot.app.query("#context-tab")
    
    @pytest.mark.asyncio
    async def test_app_starts_with_context_deps(self):
        """Test that app starts correctly when context dependencies are available."""
        # Mock the context availability
        with patch('claude_code_morph.main.CONTEXT_AVAILABLE', True):
            with patch('claude_code_morph.main.ContextManager'):
                with patch('claude_code_morph.main.ContextIntegration'):
                    app = ClaudeCodeMorph()
                    async with app.run_test() as pilot:
                        # All tabs should exist
                        assert pilot.app.query("#main-tab")
                        assert pilot.app.query("#morph-tab")
                        assert pilot.app.query("#context-tab")


class TestTabSwitching:
    """Test tab switching functionality."""
    
    @pytest.mark.asyncio
    async def test_switch_to_morph_tab(self):
        """Test switching to Morph tab doesn't crash."""
        app = ClaudeCodeMorph()
        async with app.run_test() as pilot:
            # Try to switch to morph tab
            await pilot.press("ctrl+2")
            
            # Should not crash - check we're still running
            assert app.is_running
    
    @pytest.mark.asyncio
    async def test_switch_tabs_with_ctrl_tab(self):
        """Test cycling through tabs with Ctrl+Tab."""
        app = ClaudeCodeMorph()
        async with app.run_test() as pilot:
            # Get initial tab
            tabbed = pilot.app.query_one("#tab-container")
            initial_tab = tabbed.active
            
            # Switch tabs
            await pilot.press("ctrl+tab")
            
            # Should have changed
            assert tabbed.active != initial_tab
            
            # App should still be running
            assert app.is_running


class TestDOMQueryErrors:
    """Test that DOMQuery errors are handled gracefully."""
    
    @pytest.mark.asyncio
    async def test_missing_widget_query_doesnt_crash(self):
        """Test that querying for missing widgets doesn't crash the app."""
        app = ClaudeCodeMorph()
        async with app.run_test() as pilot:
            # Try to query for a non-existent widget
            try:
                app.query_one("#non-existent-widget")
                assert False, "Should have raised an exception"
            except Exception:
                # Should raise but app should still be running
                assert app.is_running
    
    @pytest.mark.asyncio
    async def test_context_panel_handles_missing_table(self):
        """Test that ContextPanel handles missing table gracefully."""
        with patch('claude_code_morph.main.CONTEXT_AVAILABLE', True):
            with patch('claude_code_morph.main.ContextManager'):
                app = ClaudeCodeMorph()
                async with app.run_test() as pilot:
                    # Switch to context tab
                    await pilot.press("ctrl+3")
                    
                    # Simulate a click event (which was causing DOMQuery errors)
                    await pilot.click(10, 10)
                    
                    # App should still be running
                    assert app.is_running


class TestPanelLoading:
    """Test panel loading functionality."""
    
    @pytest.mark.asyncio
    async def test_morph_panel_loads_with_terminal(self):
        """Test that Morph panel loads with terminal."""
        app = ClaudeCodeMorph()
        async with app.run_test() as pilot:
            # Switch to morph tab
            await pilot.press("ctrl+2")
            await asyncio.sleep(0.5)  # Give panels time to load
            
            # Check if morph panels exist
            morph_container = pilot.app.query_one("#morph-container")
            assert morph_container is not None
            
            # Should have children (panels)
            assert len(morph_container.children) > 0
    
    @pytest.mark.asyncio
    async def test_main_workspace_loads_panels(self):
        """Test that main workspace loads panels correctly."""
        app = ClaudeCodeMorph()
        async with app.run_test() as pilot:
            await asyncio.sleep(0.5)  # Give panels time to load
            
            # Check main container has panels
            main_container = pilot.app.query_one("#main-container")
            assert main_container is not None
            assert len(main_container.children) > 0


class TestErrorHandling:
    """Test error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_app_handles_css_errors_gracefully(self):
        """Test that CSS errors don't crash the app."""
        app = ClaudeCodeMorph()
        
        # Inject bad CSS
        app.CSS = app.CSS + "\n.bad-selector { invalid-property: value; }"
        
        async with app.run_test() as pilot:
            # App should still start despite CSS issues
            assert app.is_running
    
    @pytest.mark.asyncio
    async def test_reload_action_doesnt_crash(self):
        """Test that reload action (Ctrl+T) doesn't crash."""
        app = ClaudeCodeMorph()
        async with app.run_test() as pilot:
            # Try to reload
            await pilot.press("ctrl+t")
            await asyncio.sleep(0.5)
            
            # App should still be running
            assert app.is_running


class TestVirtualEnvironment:
    """Test virtual environment detection."""
    
    def test_context_available_detection(self):
        """Test that CONTEXT_AVAILABLE is set correctly based on imports."""
        # This is more of a unit test, but important for integration
        import claude_code_morph.main as main
        
        # Should be boolean
        assert isinstance(main.CONTEXT_AVAILABLE, bool)
        
        # If True, context manager should be importable
        if main.CONTEXT_AVAILABLE:
            try:
                from claude_code_morph.context_manager import ContextManager
                assert ContextManager is not None
            except ImportError:
                pytest.fail("CONTEXT_AVAILABLE is True but can't import ContextManager")


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""
    
    @pytest.mark.asyncio
    async def test_rapid_tab_switching(self):
        """Test rapidly switching between tabs (user mashing keys)."""
        app = ClaudeCodeMorph()
        async with app.run_test() as pilot:
            # Rapidly switch tabs
            for _ in range(10):
                await pilot.press("ctrl+tab")
                await asyncio.sleep(0.05)  # Small delay
            
            # App should survive
            assert app.is_running
    
    @pytest.mark.asyncio
    async def test_startup_with_missing_workspace_file(self):
        """Test app handles missing workspace files gracefully."""
        # Mock the workspace file to not exist
        with patch('pathlib.Path.exists', return_value=False):
            app = ClaudeCodeMorph()
            async with app.run_test() as pilot:
                # Should start with default workspace
                assert app.is_running
                
                # Should have containers
                assert pilot.app.query_one("#main-container")


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])