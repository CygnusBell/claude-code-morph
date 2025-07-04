"""
ChromaDB-based context management system for Claude Code Morph.

This module manages project context using ChromaDB for vector storage,
enabling semantic search and retrieval of relevant code and documentation.
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import mimetypes

# Try to import optional dependencies
CHROMADB_AVAILABLE = False
SENTENCE_TRANSFORMERS_AVAILABLE = False
WATCHDOG_AVAILABLE = False
TIKTOKEN_AVAILABLE = False
PYMUPDF_AVAILABLE = False

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None
    Settings = None
    logging.warning("ChromaDB not available - context features will be limited")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    logging.warning("sentence-transformers not available - semantic search disabled")

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    Observer = None
    FileSystemEventHandler = object
    FileSystemEvent = None
    logging.warning("watchdog not available - file watching disabled")

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    tiktoken = None
    logging.warning("tiktoken not available - token counting disabled")

try:
    import pymupdf  # PyMuPDF for PDF processing
    PYMUPDF_AVAILABLE = True
except ImportError:
    pymupdf = None
    logging.warning("PyMuPDF not available - PDF processing disabled")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global constants
MORPH_DIR = Path.home() / ".morph"
META_FILE = MORPH_DIR / "meta.json"
CHROMA_DIR = MORPH_DIR / "chroma"
CLAUDE_DIR = Path.home() / ".claude"
CHUNK_SIZE = 400  # Target tokens per chunk
OVERLAP = 50  # Token overlap between chunks

# Export availability flags
__all__ = ['ContextManager', 'CHROMADB_AVAILABLE', 'SENTENCE_TRANSFORMERS_AVAILABLE', 
           'WATCHDOG_AVAILABLE', 'TIKTOKEN_AVAILABLE', 'PYMUPDF_AVAILABLE',
           'MORPH_DIR', 'META_FILE', 'CHROMA_DIR', 'CLAUDE_DIR', 'CHUNK_SIZE', 'OVERLAP']


if WATCHDOG_AVAILABLE:
    class FileChangeHandler(FileSystemEventHandler):
        """Handle file system events for automatic context updates."""
        
        def __init__(self, context_manager):
            self.context_manager = context_manager
            
        def on_modified(self, event: FileSystemEvent):
            if not event.is_directory:
                self.context_manager._process_file_change(event.src_path, "modified")
                
        def on_created(self, event: FileSystemEvent):
            if not event.is_directory:
                self.context_manager._process_file_change(event.src_path, "created")
                
        def on_deleted(self, event: FileSystemEvent):
            if not event.is_directory:
                self.context_manager._process_file_change(event.src_path, "deleted")
else:
    FileChangeHandler = None


class ContextManager:
    """Manages project context using ChromaDB for vector storage."""
    
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.embedder = None
        self.client = None
        self.collection = None
        self.tokenizer = tiktoken.get_encoding("cl100k_base") if TIKTOKEN_AVAILABLE else None
        self.observer = None
        self.available = CHROMADB_AVAILABLE
        
    def init_context_system(self) -> None:
        """Initialize the context system, creating directories and ChromaDB."""
        # Create directories
        MORPH_DIR.mkdir(exist_ok=True)
        CHROMA_DIR.mkdir(exist_ok=True)
        CLAUDE_DIR.mkdir(exist_ok=True)
        
        # Initialize or load metadata
        if not META_FILE.exists():
            self._prompt_for_metadata()
        
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available - context features will be limited")
            return
            
        # Initialize SentenceTransformer
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.info("Loading embedding model...")
            self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            logger.warning("sentence-transformers not available - semantic search disabled")
            return
        
        # Initialize ChromaDB
        logger.info("Initializing ChromaDB...")
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create or get collection
        try:
            self.collection = self.client.get_collection("context")
            logger.info("Using existing context collection")
        except ValueError:
            self.collection = self.client.create_collection(
                name="context",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Created new context collection")
            
    def _prompt_for_metadata(self) -> None:
        """Create default metadata for first run."""
        # In a TUI app, we can't use input() - use sensible defaults
        project_name = self.project_root.name
        description = "A Claude Code Morph project"
        
        metadata = {
            "project_name": project_name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "project_root": str(self.project_root)
        }
        
        with open(META_FILE, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        logger.info(f"Created project metadata for {project_name}")
        
    def chunk_text(self, text: str, limit: int = CHUNK_SIZE) -> List[str]:
        """Split text into chunks of approximately `limit` tokens."""
        if not self.tokenizer:
            # Fallback to simple character-based chunking
            # Approximate 4 characters per token
            char_limit = limit * 4
            chunks = []
            if len(text) <= char_limit:
                return [text]
            for i in range(0, len(text), char_limit - OVERLAP * 4):
                chunks.append(text[i:i + char_limit])
            return chunks
            
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        if len(tokens) <= limit:
            return [text]
            
        # Create overlapping chunks
        for i in range(0, len(tokens), limit - OVERLAP):
            chunk_tokens = tokens[i:i + limit]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
            
        return chunks
        
    def _generate_chunk_id(self, text: str, source: str, index: int) -> str:
        """Generate a unique ID for a text chunk."""
        content = f"{source}:{index}:{text[:100]}"
        return hashlib.sha1(content.encode()).hexdigest()
        
    def add_to_context(self, text: str, source: str, metadata: Dict[str, Any] = None) -> List[str]:
        """Add text to ChromaDB context, returning chunk IDs."""
        if not self.collection or not self.embedder:
            logger.warning("Context system not fully initialized - cannot add to context")
            return []
            
        metadata = metadata or {}
        metadata["source"] = source
        metadata["added_at"] = datetime.now().isoformat()
        metadata["weight"] = metadata.get("weight", 1.0)
        
        # Chunk the text
        chunks = self.chunk_text(text)
        ids = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = self._generate_chunk_id(chunk, source, i)
            ids.append(chunk_id)
            
            # Create embedding
            embedding = self.embedder.encode(chunk).tolist()
            
            # Store in ChromaDB
            self.collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{**metadata, "chunk_index": i, "total_chunks": len(chunks)}]
            )
            
        logger.info(f"Added {len(chunks)} chunks from {source}")
        return ids
        
    def search_context(self, query: str, n_results: int = 25) -> List[Tuple[str, float, Dict]]:
        """Search context using semantic similarity."""
        if not self.collection or not self.embedder:
            logger.warning("Context system not fully initialized - cannot search")
            return []
            
        # Create query embedding
        query_embedding = self.embedder.encode(query).tolist()
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                distance = results['distances'][0][i] if results['distances'] else 0
                metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                
                # Apply weight to distance
                weighted_distance = distance * (1.0 / metadata.get('weight', 1.0))
                
                formatted_results.append((doc, weighted_distance, metadata))
                
        # Sort by weighted distance
        formatted_results.sort(key=lambda x: x[1])
        
        return formatted_results
        
    def update_weight(self, doc_id: str, weight: float) -> None:
        """Update the weight of a document in the context."""
        if not self.collection:
            logger.warning("Context system not initialized - cannot update weight")
            return
            
        # Get existing document
        result = self.collection.get(ids=[doc_id])
        
        if result['metadatas'] and result['metadatas'][0]:
            metadata = result['metadatas'][0]
            metadata['weight'] = weight
            
            # Update in ChromaDB
            self.collection.update(
                ids=[doc_id],
                metadatas=[metadata]
            )
            
            logger.info(f"Updated weight for {doc_id} to {weight}")
            
    def delete_from_context(self, doc_id: str) -> None:
        """Remove a document from the context."""
        if not self.collection:
            logger.warning("Context system not initialized - cannot delete")
            return
            
        self.collection.delete(ids=[doc_id])
        logger.info(f"Deleted document {doc_id}")
        
    def _is_text_file(self, file_path: Path) -> bool:
        """Check if a file is likely to contain text."""
        # Check common text extensions
        text_extensions = {
            '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h',
            '.hpp', '.cs', '.go', '.rs', '.rb', '.php', '.swift', '.kt', '.scala',
            '.md', '.txt', '.rst', '.json', '.yaml', '.yml', '.xml', '.html',
            '.css', '.scss', '.less', '.sql', '.sh', '.bash', '.zsh', '.fish',
            '.vim', '.conf', '.ini', '.toml', '.env', '.gitignore', '.dockerignore',
            '.log', '.csv', '.tsv'
        }
        
        if file_path.suffix.lower() in text_extensions:
            return True
            
        # Check MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if mime_type and mime_type.startswith('text/'):
            return True
            
        # Check if file has no extension (like Dockerfile, Makefile)
        if not file_path.suffix and file_path.name in ['Dockerfile', 'Makefile', 'README']:
            return True
            
        return False
        
    def _extract_text_from_file(self, file_path: Path) -> Optional[str]:
        """Extract text content from a file."""
        try:
            if file_path.suffix.lower() == '.pdf':
                if not PYMUPDF_AVAILABLE:
                    logger.warning(f"PyMuPDF not available - cannot read PDF file: {file_path}")
                    return None
                # Extract text from PDF
                text = ""
                with pymupdf.open(str(file_path)) as pdf:
                    for page in pdf:
                        text += page.get_text()
                return text
            elif self._is_text_file(file_path):
                # Read text file
                return file_path.read_text(encoding='utf-8', errors='ignore')
            else:
                return None
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
            
    def ingest_project_files(self, patterns: List[str] = None) -> int:
        """Scan and ingest all project files."""
        if not self.collection:
            logger.warning("Context system not initialized - cannot ingest files")
            return 0
            
        # Default patterns
        if not patterns:
            patterns = ['**/*']
            
        # Exclude patterns
        exclude_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 
                       'env', '.env', 'dist', 'build', '.pytest_cache', '.mypy_cache'}
        
        total_files = 0
        
        for pattern in patterns:
            for file_path in self.project_root.glob(pattern):
                # Skip excluded directories
                if any(excluded in file_path.parts for excluded in exclude_dirs):
                    continue
                    
                if file_path.is_file():
                    text = self._extract_text_from_file(file_path)
                    if text:
                        relative_path = file_path.relative_to(self.project_root)
                        metadata = {
                            "file_type": file_path.suffix,
                            "file_size": file_path.stat().st_size,
                            "modified": datetime.fromtimestamp(
                                file_path.stat().st_mtime
                            ).isoformat()
                        }
                        
                        self.add_to_context(text, str(relative_path), metadata)
                        total_files += 1
                        
        logger.info(f"Ingested {total_files} files from project")
        return total_files
        
    def _process_file_change(self, file_path: str, event_type: str) -> None:
        """Process a file change event."""
        path = Path(file_path)
        
        if not path.exists() and event_type != "deleted":
            return
            
        # Skip if not in project
        try:
            relative_path = path.relative_to(self.project_root)
        except ValueError:
            return
            
        logger.info(f"File {event_type}: {relative_path}")
        
        if event_type == "deleted":
            # Remove all chunks from this file
            results = self.collection.get(
                where={"source": str(relative_path)}
            )
            
            if results['ids']:
                for doc_id in results['ids']:
                    self.delete_from_context(doc_id)
        else:
            # Re-ingest the file
            text = self._extract_text_from_file(path)
            if text:
                # Delete old chunks first
                results = self.collection.get(
                    where={"source": str(relative_path)}
                )
                
                if results['ids']:
                    for doc_id in results['ids']:
                        self.delete_from_context(doc_id)
                        
                # Add new chunks
                metadata = {
                    "file_type": path.suffix,
                    "file_size": path.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        path.stat().st_mtime
                    ).isoformat()
                }
                
                self.add_to_context(text, str(relative_path), metadata)
                
    def watch_files(self) -> None:
        """Start monitoring file changes in the project."""
        if not WATCHDOG_AVAILABLE:
            logger.warning("watchdog not available - file watching disabled")
            return
            
        if self.observer:
            logger.warning("File watcher already running")
            return
            
        self.observer = Observer()
        handler = FileChangeHandler(self)
        self.observer.schedule(handler, str(self.project_root), recursive=True)
        self.observer.start()
        
        logger.info(f"Watching for file changes in {self.project_root}")
        
    def stop_watching(self) -> None:
        """Stop monitoring file changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Stopped file watcher")
            
    def process_claude_cache(self) -> None:
        """Process files from ~/.claude/*.txt after each turn."""
        cache_files = list(CLAUDE_DIR.glob("*.txt"))
        
        for cache_file in cache_files:
            try:
                content = cache_file.read_text(encoding='utf-8')
                
                # Add to context as conversation turn
                metadata = {
                    "type": "conversation",
                    "turn": cache_file.stem,
                    "timestamp": datetime.fromtimestamp(
                        cache_file.stat().st_mtime
                    ).isoformat()
                }
                
                self.add_to_context(
                    content, 
                    f"conversation/{cache_file.name}",
                    metadata
                )
                
                # Remove the cache file
                cache_file.unlink()
                logger.info(f"Processed and removed cache file: {cache_file.name}")
                
            except Exception as e:
                logger.error(f"Error processing cache file {cache_file}: {e}")
                
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the context database."""
        if not self.collection:
            logger.warning("Context system not initialized - no stats available")
            return {
                "total_chunks": 0,
                "unique_sources": 0,
                "sources": [],
                "available": False
            }
            
        # Get collection count
        count = self.collection.count()
        
        # Get unique sources
        all_docs = self.collection.get()
        sources = set()
        
        if all_docs['metadatas']:
            for metadata in all_docs['metadatas']:
                if metadata and 'source' in metadata:
                    sources.add(metadata['source'])
                    
        return {
            "total_chunks": count,
            "unique_sources": len(sources),
            "sources": sorted(sources),
            "available": True
        }


# Convenience functions for direct usage
def init_context_system(project_root: Optional[str] = None) -> ContextManager:
    """Initialize the context system."""
    manager = ContextManager(project_root)
    manager.init_context_system()
    return manager


def ingest_project_files(manager: ContextManager, patterns: List[str] = None) -> int:
    """Ingest project files into the context."""
    return manager.ingest_project_files(patterns)


def chunk_text(text: str, limit: int = CHUNK_SIZE) -> List[str]:
    """Split text into chunks."""
    manager = ContextManager()
    return manager.chunk_text(text, limit)


def add_to_context(manager: ContextManager, text: str, source: str, 
                   metadata: Dict[str, Any] = None) -> List[str]:
    """Add text to the context."""
    return manager.add_to_context(text, source, metadata)


def search_context(manager: ContextManager, query: str, 
                   n_results: int = 25) -> List[Tuple[str, float, Dict]]:
    """Search the context."""
    return manager.search_context(query, n_results)


def update_weight(manager: ContextManager, doc_id: str, weight: float) -> None:
    """Update document weight."""
    manager.update_weight(doc_id, weight)


def delete_from_context(manager: ContextManager, doc_id: str) -> None:
    """Delete from context."""
    manager.delete_from_context(doc_id)


def watch_files(manager: ContextManager) -> None:
    """Start watching files."""
    manager.watch_files()


if __name__ == "__main__":
    # Example usage
    print("Initializing context system...")
    manager = init_context_system()
    
    print("\nIngesting project files...")
    count = ingest_project_files(manager)
    print(f"Ingested {count} files")
    
    print("\nContext statistics:")
    stats = manager.get_stats()
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Unique sources: {stats['unique_sources']}")
    
    # Start file watcher
    watch_files(manager)
    
    print("\nContext system initialized and watching for changes.")
    print("Press Ctrl+C to stop.")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop_watching()
        print("\nStopped.")