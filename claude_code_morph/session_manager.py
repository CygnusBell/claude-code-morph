"""Session Manager - Handles persistent state for Claude Code Morph sessions."""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class SessionManager:
    """Manages session persistence in .morph directory."""
    
    def __init__(self, session_dir: Path = None):
        """Initialize session manager.
        
        Args:
            session_dir: Directory for session data (defaults to .morph in cwd)
        """
        self.session_dir = session_dir or Path.cwd() / ".morph"
        self.session_file = self.session_dir / "session.json"
        self.terminal_buffer_file = self.session_dir / "terminal_buffer.txt"
        self.prompt_history_file = self.session_dir / "prompt_history.json"
        
        # Ensure directory exists
        self.session_dir.mkdir(exist_ok=True)
        
        logging.info(f"SessionManager initialized with directory: {self.session_dir}")
        
    def save_session(self, state: Dict[str, Any]) -> None:
        """Save complete session state.
        
        Args:
            state: Dictionary containing all session state
        """
        try:
            # Add metadata
            state['_metadata'] = {
                'saved_at': datetime.now().isoformat(),
                'version': '1.0',
                'cwd': str(Path.cwd())
            }
            
            # Save main session file
            with open(self.session_file, 'w') as f:
                json.dump(state, f, indent=2, default=str)
                
            logging.info("Session saved successfully")
            
        except Exception as e:
            logging.error(f"Failed to save session: {e}")
            
    def load_session(self) -> Optional[Dict[str, Any]]:
        """Load session state from disk.
        
        Returns:
            Session state dictionary or None if not found
        """
        if not self.session_file.exists():
            logging.info("No session file found")
            return None
            
        try:
            with open(self.session_file, 'r') as f:
                state = json.load(f)
                
            # Check if session is from same directory
            metadata = state.get('_metadata', {})
            saved_cwd = metadata.get('cwd')
            if saved_cwd and saved_cwd != str(Path.cwd()):
                logging.warning(f"Session from different directory: {saved_cwd}")
                
            logging.info(f"Session loaded from {metadata.get('saved_at', 'unknown time')}")
            return state
            
        except Exception as e:
            logging.error(f"Failed to load session: {e}")
            return None
            
    def save_terminal_buffer(self, buffer_lines: list) -> None:
        """Save terminal buffer to file.
        
        Args:
            buffer_lines: List of terminal output lines
        """
        try:
            with open(self.terminal_buffer_file, 'w') as f:
                f.write('\n'.join(buffer_lines))
            logging.debug(f"Saved {len(buffer_lines)} terminal lines")
        except Exception as e:
            logging.error(f"Failed to save terminal buffer: {e}")
            
    def load_terminal_buffer(self) -> list:
        """Load terminal buffer from file.
        
        Returns:
            List of terminal output lines
        """
        if not self.terminal_buffer_file.exists():
            return []
            
        try:
            with open(self.terminal_buffer_file, 'r') as f:
                content = f.read()
            return content.split('\n') if content else []
        except Exception as e:
            logging.error(f"Failed to load terminal buffer: {e}")
            return []
            
    def save_prompt_history(self, history: list) -> None:
        """Save prompt history to file.
        
        Args:
            history: List of prompt history entries
        """
        try:
            with open(self.prompt_history_file, 'w') as f:
                json.dump(history, f, indent=2)
            logging.debug(f"Saved {len(history)} prompt history entries")
        except Exception as e:
            logging.error(f"Failed to save prompt history: {e}")
            
    def load_prompt_history(self) -> list:
        """Load prompt history from file.
        
        Returns:
            List of prompt history entries
        """
        if not self.prompt_history_file.exists():
            return []
            
        try:
            with open(self.prompt_history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Failed to load prompt history: {e}")
            return []
            
    def clear_session(self) -> None:
        """Clear all session data."""
        try:
            if self.session_file.exists():
                self.session_file.unlink()
            if self.terminal_buffer_file.exists():
                self.terminal_buffer_file.unlink()
            if self.prompt_history_file.exists():
                self.prompt_history_file.unlink()
            logging.info("Session cleared")
        except Exception as e:
            logging.error(f"Failed to clear session: {e}")
            
    def get_session_info(self) -> Optional[Dict[str, Any]]:
        """Get session metadata without loading full state.
        
        Returns:
            Session metadata or None
        """
        if not self.session_file.exists():
            return None
            
        try:
            with open(self.session_file, 'r') as f:
                state = json.load(f)
            return state.get('_metadata', {})
        except Exception as e:
            logging.error(f"Failed to get session info: {e}")
            return None