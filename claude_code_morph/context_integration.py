"""
Context Integration Module - Connects ContextPanel UI with context_manager backend.

This module provides a clean interface between the UI components and the ChromaDB
backend, handling context loading, searching, updating, and automatic processing
of Claude conversations.
"""

import os
import asyncio
import logging
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Callable
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    Observer = None
    FileSystemEventHandler = object
    FileSystemEvent = None
    logger.warning("watchdog not available - file watching disabled")
    
try:
    import tiktoken
except ImportError:
    tiktoken = None
    logger.warning("tiktoken not available - token counting disabled")

from .context_manager import ContextManager, CLAUDE_DIR


if WATCHDOG_AVAILABLE:
    class ClaudeConversationWatcher(FileSystemEventHandler):
        """Watch for new Claude conversation files and process them automatically."""
        
        def __init__(self, context_integration: 'ContextIntegration'):
            self.context_integration = context_integration
            self.processed_files = set()
            
        def on_created(self, event: FileSystemEvent):
            """Handle new file creation in ~/.claude/ directory."""
            if not event.is_directory and event.src_path.endswith('.txt'):
                file_path = Path(event.src_path)
                if file_path not in self.processed_files:
                    logger.info(f"New Claude conversation file detected: {file_path.name}")
                    # Process asynchronously
                    asyncio.create_task(
                        self.context_integration.process_conversation_file(file_path)
                    )
                    self.processed_files.add(file_path)
                    
        def on_modified(self, event: FileSystemEvent):
            """Handle file modifications in ~/.claude/ directory."""
            if not event.is_directory and event.src_path.endswith('.txt'):
                file_path = Path(event.src_path)
                # Only process if we haven't seen this file before
                if file_path not in self.processed_files:
                    logger.info(f"Modified Claude conversation file: {file_path.name}")
                    asyncio.create_task(
                        self.context_integration.process_conversation_file(file_path)
                    )
                    self.processed_files.add(file_path)
else:
    ClaudeConversationWatcher = None


class ContextIntegration:
    """
    Main integration class that connects the UI with the context management backend.
    
    This class handles:
    - Loading context entries from ChromaDB
    - Updating weights and deleting entries
    - Performing semantic search
    - Processing Claude conversations automatically
    - Managing token budgets for prompts
    """
    
    def __init__(self, project_root: Optional[str] = None):
        """Initialize the context integration system."""
        self.context_manager = ContextManager(project_root)
        self.tokenizer = tiktoken.get_encoding("cl100k_base") if tiktoken else None
        self.conversation_observer = None
        self.ui_update_callbacks = []
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize the context system and start watching for conversations."""
        if self._initialized:
            return
            
        # Initialize context manager
        self.context_manager.init_context_system()
        
        # Start watching Claude conversation directory
        self.start_conversation_watcher()
        
        # Start watching project files
        self.context_manager.watch_files()
        
        self._initialized = True
        logger.info("Context integration system initialized")
        
    def register_ui_update_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to be called when the UI should be updated."""
        self.ui_update_callbacks.append(callback)
        
    def _notify_ui_update(self) -> None:
        """Notify all registered UI components to update."""
        for callback in self.ui_update_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error calling UI update callback: {e}")
                
    def start_conversation_watcher(self) -> None:
        """Start watching the Claude conversation directory."""
        if not WATCHDOG_AVAILABLE:
            logger.warning("Watchdog not available - conversation watching disabled")
            return
            
        if self.conversation_observer:
            logger.warning("Conversation watcher already running")
            return
            
        # Ensure Claude directory exists
        CLAUDE_DIR.mkdir(exist_ok=True)
        
        # Create and start observer
        self.conversation_observer = Observer()
        if ClaudeConversationWatcher:
            handler = ClaudeConversationWatcher(self)
            self.conversation_observer.schedule(
                handler, 
                str(CLAUDE_DIR), 
                recursive=False
            )
            self.conversation_observer.start()
        else:
            logger.error("ClaudeConversationWatcher not available")
        
        logger.info(f"Started watching Claude conversations at {CLAUDE_DIR}")
        
    def stop_conversation_watcher(self) -> None:
        """Stop watching the Claude conversation directory."""
        if self.conversation_observer:
            self.conversation_observer.stop()
            self.conversation_observer.join()
            self.conversation_observer = None
            logger.info("Stopped conversation watcher")
            
    async def process_conversation_file(self, file_path: Path) -> None:
        """Process a Claude conversation file and add to context."""
        try:
            # Read the conversation content
            content = file_path.read_text(encoding='utf-8')
            
            # Extract conversation metadata
            metadata = {
                "type": "conversation",
                "turn": file_path.stem,
                "timestamp": datetime.fromtimestamp(
                    file_path.stat().st_mtime
                ).isoformat(),
                "file_name": file_path.name
            }
            
            # Add to context
            self.context_manager.add_to_context(
                content,
                f"conversation/{file_path.name}",
                metadata
            )
            
            # Remove the processed file
            file_path.unlink()
            logger.info(f"Processed and removed conversation file: {file_path.name}")
            
            # Notify UI to update
            self._notify_ui_update()
            
        except Exception as e:
            logger.error(f"Error processing conversation file {file_path}: {e}")
            
    def get_all_context_entries(self) -> List[Dict[str, Any]]:
        """
        Get all context entries from ChromaDB formatted for the UI.
        
        Returns a list of dictionaries with keys:
        - id: Document ID
        - text: The text content (truncated for display)
        - source: Source file/location
        - type: Type of content
        - relevance: Relevance score (0-1)
        - weight: Current weight multiplier
        - timestamp: When added
        """
        if not self.context_manager.collection:
            return []
            
        try:
            # Get all documents from ChromaDB
            results = self.context_manager.collection.get()
            
            entries = []
            if results['ids']:
                for i, doc_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i] if results['metadatas'] else {}
                    document = results['documents'][i] if results['documents'] else ""
                    
                    # Format entry for UI
                    entry = {
                        "id": doc_id,
                        "text": document[:200],  # Truncate for display
                        "source": metadata.get("source", "Unknown"),
                        "type": metadata.get("type", "text"),
                        "relevance": 1.0,  # Default relevance for all entries
                        "weight": metadata.get("weight", 1.0),
                        "timestamp": metadata.get("added_at", datetime.now().isoformat())
                    }
                    entries.append(entry)
                    
            # Sort by timestamp (newest first)
            entries.sort(key=lambda x: x['timestamp'], reverse=True)
            
            return entries
            
        except Exception as e:
            logger.error(f"Error getting context entries: {e}")
            return []
            
    def search_context(self, query: str, max_results: int = 25) -> List[Dict[str, Any]]:
        """
        Perform semantic search on the context.
        
        Returns results formatted for the UI with relevance scores.
        """
        if not query.strip():
            # Return all entries if no query
            return self.get_all_context_entries()[:max_results]
            
        try:
            # Perform semantic search
            results = self.context_manager.search_context(query, n_results=max_results)
            
            entries = []
            for doc, distance, metadata in results:
                # Convert distance to relevance score (0-1, where 1 is most relevant)
                # Assuming distances are typically 0-2, with 0 being identical
                relevance = max(0, 1 - (distance / 2))
                
                entry = {
                    "id": metadata.get("__id__", ""),  # ChromaDB stores ID in metadata
                    "text": doc[:200],  # Truncate for display
                    "source": metadata.get("source", "Unknown"),
                    "type": metadata.get("type", "text"),
                    "relevance": relevance,
                    "weight": metadata.get("weight", 1.0),
                    "timestamp": metadata.get("added_at", datetime.now().isoformat())
                }
                entries.append(entry)
                
            return entries
            
        except Exception as e:
            logger.error(f"Error searching context: {e}")
            return []
            
    def update_weight(self, doc_id: str, new_weight: float) -> bool:
        """
        Update the weight of a context entry.
        
        Returns True if successful, False otherwise.
        """
        try:
            self.context_manager.update_weight(doc_id, new_weight)
            self._notify_ui_update()
            return True
        except Exception as e:
            logger.error(f"Error updating weight for {doc_id}: {e}")
            return False
            
    def delete_entry(self, doc_id: str) -> bool:
        """
        Delete a context entry from ChromaDB.
        
        Returns True if successful, False otherwise.
        """
        try:
            self.context_manager.delete_from_context(doc_id)
            self._notify_ui_update()
            return True
        except Exception as e:
            logger.error(f"Error deleting entry {doc_id}: {e}")
            return False
            
    def get_context_for_prompt(self, query: str, token_budget: int = 4000) -> str:
        """
        Get relevant context for a prompt within a token budget.
        
        Args:
            query: The user's prompt/query
            token_budget: Maximum tokens to use for context
            
        Returns:
            Formatted context string to include in the prompt
        """
        if token_budget <= 0:
            return ""
            
        try:
            # Search for relevant context
            results = self.context_manager.search_context(query, n_results=50)
            
            # Build context within token budget
            context_parts = []
            used_tokens = 0
            
            for doc, distance, metadata in results:
                # Estimate tokens for this document
                if self.tokenizer:
                    doc_tokens = len(self.tokenizer.encode(doc))
                else:
                    # Rough estimate: 1 token ~= 4 chars
                    doc_tokens = len(doc) // 4
                
                # Check if we can fit this document
                if used_tokens + doc_tokens > token_budget:
                    # Try to fit a truncated version
                    remaining_budget = token_budget - used_tokens
                    if remaining_budget > 100:  # Only include if we have reasonable space
                        truncated = self._truncate_to_tokens(doc, remaining_budget - 50)
                        if truncated:
                            source = metadata.get("source", "Unknown")
                            context_parts.append(f"[From {source}]\n{truncated}\n")
                            break
                else:
                    # Add full document
                    source = metadata.get("source", "Unknown")
                    weight = metadata.get("weight", 1.0)
                    
                    # Format based on weight
                    if weight > 1.5:
                        context_parts.append(f"[IMPORTANT - From {source}]\n{doc}\n")
                    else:
                        context_parts.append(f"[From {source}]\n{doc}\n")
                        
                    used_tokens += doc_tokens
                    
            if context_parts:
                context_header = "=== Relevant Context ===\n"
                context_footer = "\n=== End Context ===\n"
                return context_header + "\n".join(context_parts) + context_footer
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Error getting context for prompt: {e}")
            return ""
            
    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token budget."""
        if self.tokenizer:
            tokens = self.tokenizer.encode(text)
            if len(tokens) <= max_tokens:
                return text
                
            # Truncate and decode
            truncated_tokens = tokens[:max_tokens]
            return self.tokenizer.decode(truncated_tokens) + "..."
        else:
            # Simple character-based truncation
            max_chars = max_tokens * 4  # Rough estimate
            if len(text) <= max_chars:
                return text
            return text[:max_chars] + "..."
        
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the context database."""
        return self.context_manager.get_stats()
        
    def ingest_project_files(self, patterns: Optional[List[str]] = None) -> int:
        """
        Ingest project files into the context system.
        
        Returns the number of files ingested.
        """
        count = self.context_manager.ingest_project_files(patterns)
        self._notify_ui_update()
        return count
        
    async def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_conversation_watcher()
        self.context_manager.stop_watching()
        

# Integration with EmulatedTerminalPanel
class TerminalContextHelper:
    """Helper class for EmulatedTerminalPanel to use context in prompts."""
    
    def __init__(self, context_integration: ContextIntegration):
        self.context_integration = context_integration
        
    def enhance_prompt_with_context(self, prompt: str, mode: str = "develop") -> str:
        """
        Enhance a user prompt with relevant context.
        
        Args:
            prompt: The user's original prompt
            mode: The current mode (develop/morph)
            
        Returns:
            Enhanced prompt with context included
        """
        # Don't add context for very short prompts
        if len(prompt) < 10:
            return prompt
            
        # Get relevant context
        # Reserve tokens for the prompt itself and response
        if self.context_integration.tokenizer:
            prompt_tokens = len(self.context_integration.tokenizer.encode(prompt))
        else:
            prompt_tokens = len(prompt) // 4  # Rough estimate
        available_budget = 4000 - prompt_tokens  # Leave room for prompt
        
        context = self.context_integration.get_context_for_prompt(
            prompt, 
            token_budget=available_budget
        )
        
        if context:
            # Add context before the prompt
            enhanced = f"{context}\nUser request: {prompt}"
            
            # Log context usage
            if self.context_integration.tokenizer:
                context_tokens = len(self.context_integration.tokenizer.encode(context))
            else:
                context_tokens = len(context) // 4  # Rough estimate
            logger.info(f"Added {context_tokens} tokens of context to prompt")
            
            return enhanced
        else:
            return prompt
            

# Convenience function for initialization
async def create_context_integration(project_root: Optional[str] = None) -> ContextIntegration:
    """Create and initialize a context integration instance."""
    integration = ContextIntegration(project_root)
    await integration.initialize()
    return integration