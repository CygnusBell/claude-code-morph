#!/usr/bin/env python3
"""Debug script to capture DOMQuery errors in Claude Code Morph."""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Set up comprehensive logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure root logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d',
    handlers=[
        logging.FileHandler(log_dir / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Disable bracketed paste mode
sys.stdout.write('\033[?2004l')
sys.stdout.flush()

# Set debug environment variables
os.environ['TEXTUAL_LOG'] = str(log_dir / "textual_debug.log")
os.environ['TEXTUAL_LOG_LEVEL'] = "DEBUG"

# Import after setting up logging
try:
    from textual.app import App
    from textual.dom import DOMError, NoMatches
    from textual.css.query import InvalidQueryFormat
    
    # Monkey patch query_one to add better error handling
    original_query_one = App.query_one
    
    def patched_query_one(self, selector=None, expect_type=None):
        """Patched query_one with better error reporting."""
        try:
            return original_query_one(self, selector, expect_type)
        except (DOMError, NoMatches, InvalidQueryFormat) as e:
            logging.error(f"DOMQuery error in query_one: selector='{selector}', error='{e}'")
            logging.error(f"Widget tree at error: {self._get_widget_tree_summary()}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error in query_one: selector='{selector}', error='{e}'", exc_info=True)
            raise
    
    def _get_widget_tree_summary(self):
        """Get a summary of the widget tree."""
        try:
            def _walk(widget, depth=0):
                info = f"{'  ' * depth}{widget.__class__.__name__}"
                if hasattr(widget, 'id') and widget.id:
                    info += f" (id={widget.id})"
                yield info
                if hasattr(widget, 'children'):
                    for child in widget.children:
                        yield from _walk(child, depth + 1)
            
            return "\n".join(_walk(self))
        except:
            return "Unable to generate widget tree"
    
    App.query_one = patched_query_one
    App._get_widget_tree_summary = _get_widget_tree_summary
    
    logging.info("Monkey patches applied successfully")
    
except Exception as e:
    logging.error(f"Error setting up debug patches: {e}", exc_info=True)

# Now run the main app
try:
    logging.info("Starting Claude Code Morph with debug logging...")
    from claude_code_morph.main import main
    main()
except Exception as e:
    logging.error(f"Fatal error running Claude Code Morph: {e}", exc_info=True)
    print(f"\n\nFATAL ERROR: {e}")
    print(f"Check logs in {log_dir} for details")
    sys.exit(1)