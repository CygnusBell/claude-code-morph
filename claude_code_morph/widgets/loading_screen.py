"""Loading screen widget for Claude Code Morph."""

from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.widgets import Static, LoadingIndicator, Label
from textual.reactive import reactive
from rich.text import Text
from rich.align import Align


class LoadingScreen(Vertical):
    """A loading screen with progress indicator and status messages."""
    
    DEFAULT_CSS = """
    LoadingScreen {
        width: 100%;
        height: 100%;
        background: $surface;
        align: center middle;
        layer: overlay;
    }
    
    LoadingScreen Center {
        width: 60;
        height: auto;
        padding: 2 4;
        background: $panel;
        border: thick $primary;
    }
    
    LoadingScreen .title {
        text-align: center;
        text-style: bold;
        color: $primary;
        margin-bottom: 2;
    }
    
    LoadingScreen LoadingIndicator {
        margin: 1 0;
        color: $accent;
    }
    
    LoadingScreen .status {
        text-align: center;
        color: $text-muted;
        margin-top: 1;
    }
    
    LoadingScreen .progress {
        text-align: center;
        color: $text;
        margin-top: 1;
    }
    """
    
    status_message = reactive("Initializing...")
    progress = reactive(0)
    total_steps = reactive(5)
    
    def compose(self) -> ComposeResult:
        """Compose the loading screen layout."""
        with Center():
            with Vertical():
                # Title
                title = Static("Claude Code Morph", classes="title")
                title.update(Text("Claude Code Morph", style="bold cyan"))
                yield title
                
                # Loading indicator
                yield LoadingIndicator()
                
                # Status message
                self.status_label = Label(self.status_message, classes="status")
                yield self.status_label
                
                # Progress indicator
                self.progress_label = Label("", classes="progress")
                yield self.progress_label
                
    def on_mount(self) -> None:
        """Update progress display when mounted."""
        self._update_progress()
    
    def update_status(self, message: str, progress: int = None) -> None:
        """Update the loading status and optionally the progress."""
        self.status_message = message
        if progress is not None:
            self.progress = progress
            self._update_progress()
    
    def _update_progress(self) -> None:
        """Update the progress display."""
        if self.total_steps > 0:
            percentage = int((self.progress / self.total_steps) * 100)
            self.progress_label.update(f"Step {self.progress} of {self.total_steps} ({percentage}%)")
    
    def watch_status_message(self, message: str) -> None:
        """Update status label when message changes."""
        if hasattr(self, 'status_label'):
            self.status_label.update(message)
    
    def watch_progress(self, progress: int) -> None:
        """Update progress display when progress changes."""
        if hasattr(self, 'progress_label'):
            self._update_progress()