"""Pipe Terminal Panel - Uses pipe mode for reliable Claude CLI interaction."""

import os
import subprocess
import threading
import queue
import signal
import concurrent.futures
from typing import Optional
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.binding import Binding
import logging
import asyncio
try:
    from .BasePanel import BasePanel
except ImportError:
    # Fallback for when module is loaded dynamically
    from claude_code_morph.panels.BasePanel import BasePanel

class PipeTerminalPanel(BasePanel):
    """Terminal panel that uses pipe mode for Claude CLI - more reliable."""
    
    CSS = BasePanel.DEFAULT_CSS + """
    PipeTerminalPanel {
        layout: vertical;
        height: 100%;
    }
    
    #terminal-output {
        height: 1fr;
        background: #0a0a0a;
        color: #e0e0e0;
        padding: 1;
        border: solid #444444;
        overflow-y: scroll;
    }
    """
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+c", "interrupt", "Interrupt"),
        Binding("ctrl+r", "restart", "New Session"),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the terminal panel."""
        super().__init__(**kwargs)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal (Pipe Mode)", classes="panel-title")
            
            self.output = RichLog(
                highlight=False,
                markup=True,
                wrap=True,
                id="terminal-output",
                auto_scroll=True
            )
            yield self.output
            
            self.status = Static("Status: Ready", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self.output.write("[dim]Claude CLI in pipe mode - reliable but non-interactive[/dim]")
        self.output.write("[dim]Submit prompts using the prompt panel above[/dim]")
        
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude CLI."""
        logging.info(f"Sending prompt: {prompt[:50]}...")
        
        # Add mode context
        if mode.lower() == 'morph':
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            prompt += f"\n\n[IMPORTANT: Work on Claude Code Morph source at {morph_dir}]"
            
        # Show prompt
        self.output.write(f"\n[bold cyan]>>> {prompt}[/bold cyan]\n")
        self.output.write("[dim]Running: claude --print ...[/dim]\n")
        self.status.update("Status: [yellow]Processing...[/yellow]")
        
        # Run in thread pool to avoid async issues
        def run_claude():
            try:
                # Use --print flag for non-interactive mode
                cmd = ["claude", "--print"]
                
                # Add skip permissions flag if needed (e.g., in containers)
                if os.environ.get("CLAUDE_SKIP_PERMISSIONS"):
                    cmd.append("--dangerously-skip-permissions")
                
                cmd.append(prompt)
                
                # Log the command for debugging
                logging.info(f"Running command: {' '.join(cmd[:-1])} [prompt...]")
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.stdout, result.stderr, None
            except subprocess.TimeoutExpired:
                return None, None, "Claude CLI timed out (30s)"
            except Exception as e:
                return None, None, str(e)
        
        # Run in executor
        future = self.executor.submit(run_claude)
        
        try:
            # Wait for result
            stdout, stderr, error = await asyncio.get_event_loop().run_in_executor(
                None, future.result, 35  # Give it 35 seconds total
            )
            
            if error:
                self.output.write(f"[red]Error: {error}[/red]")
                self.status.update("Status: [red]Error[/red]")
            else:
                # Display response
                if stdout and stdout.strip():
                    self.output.write(stdout)
                else:
                    self.output.write("[yellow]No response received[/yellow]")
                
                if stderr and stderr.strip():
                    self.output.write(f"[red]Error: {stderr}[/red]")
                
                self.status.update("Status: [green]Ready[/green]")
                
        except Exception as e:
            self.output.write(f"[red]Error: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Error running Claude: {e}", exc_info=True)
            
    def action_interrupt(self) -> None:
        """Interrupt current operation."""
        self.output.write("\n[yellow]Pipe mode doesn't support interruption[/yellow]")
        
    def action_restart(self) -> None:
        """Start a new session."""
        self.output.clear()
        self.output.write("[dim]Ready for new prompts[/dim]")
        self.status.update("Status: [green]Ready[/green]")
        
    def get_copyable_content(self) -> str:
        """Get copyable content."""
        return ""
        
    def get_selected_content(self) -> Optional[str]:
        """Get selected content."""
        return None
        
    def on_unmount(self) -> None:
        """Clean up when unmounted."""
        self.executor.shutdown(wait=False)