"""Terminal Panel - Manages Claude CLI subprocess in a persistent session."""

import os
import sys
import asyncio
import subprocess
import threading
from typing import Optional, List
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.binding import Binding
from rich.text import Text
from rich.console import Console
import pty
import select
import termios
import fcntl

class TerminalPanel(Static):
    """Panel that runs Claude CLI in a subprocess with persistent session."""
    
    BINDINGS = [
        Binding("ctrl+c", "interrupt", "Interrupt"),
        Binding("ctrl+d", "restart", "Restart Claude"),
    ]
    
    def __init__(self, auto_start: bool = True, **kwargs):
        """Initialize the terminal panel.
        
        Args:
            auto_start: Whether to automatically start Claude CLI on mount
        """
        super().__init__(**kwargs)
        self._init_params = {"auto_start": auto_start}  # Store for hot-reloading
        self.auto_start = auto_start
        self.process: Optional[subprocess.Popen] = None
        self.master_fd: Optional[int] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.command_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
        
    def compose(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal", classes="panel-title")
            
            # Terminal output display
            self.output = RichLog(
                highlight=True,
                markup=True,
                wrap=True,
                id="terminal-output"
            )
            self.output.styles.height = "100%"
            yield self.output
            
            # Status bar
            self.status = Static("Status: Not started", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        if self.auto_start:
            await self.start_claude()
            
    async def on_unmount(self) -> None:
        """Clean up when panel is removed."""
        await self.stop_claude()
        
    async def start_claude(self) -> None:
        """Start Claude CLI subprocess."""
        if self._is_running:
            self.output.write("[yellow]Claude CLI is already running[/yellow]")
            return
            
        try:
            # Create pseudo-terminal
            self.master_fd, slave_fd = pty.openpty()
            
            # Make master non-blocking
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Set terminal size
            winsize = struct.pack('HHHH', 40, 120, 0, 0)  # rows, cols, xpixel, ypixel
            fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
            
            # Start Claude CLI process
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            
            self.process = subprocess.Popen(
                ['claude', 'code'],
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                env=env,
                preexec_fn=os.setsid,  # Create new session
                cwd=os.getcwd()  # Use app directory as working directory
            )
            
            # Close slave fd in parent
            os.close(slave_fd)
            
            self._is_running = True
            self.status.update("Status: [green]Running[/green]")
            self.output.write("[green]Claude CLI started![/green]")
            self.output.write(f"[dim]Working directory: {os.getcwd()}[/dim]")
            
            # Start reader thread
            self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
            self.reader_thread.start()
            
            # Start command processor
            asyncio.create_task(self._process_commands())
            
        except Exception as e:
            self.output.write(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            self._is_running = False
            
    async def stop_claude(self) -> None:
        """Stop Claude CLI subprocess."""
        if not self._is_running:
            return
            
        self._is_running = False
        
        if self.process:
            try:
                # Send exit command
                os.write(self.master_fd, b"exit\n")
                self.process.wait(timeout=2)
            except:
                # Force terminate if needed
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except:
                    self.process.kill()
                    
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass
                
        self.process = None
        self.master_fd = None
        self.status.update("Status: [yellow]Stopped[/yellow]")
        self.output.write("[yellow]Claude CLI stopped[/yellow]")
        
    def _read_output(self) -> None:
        """Read output from Claude CLI (runs in separate thread)."""
        buffer = b""
        
        while self._is_running and self.master_fd:
            try:
                # Use select to wait for data
                r, _, _ = select.select([self.master_fd], [], [], 0.1)
                
                if r:
                    data = os.read(self.master_fd, 4096)
                    if data:
                        buffer += data
                        
                        # Try to decode and display
                        try:
                            text = buffer.decode('utf-8', errors='replace')
                            buffer = b""
                            
                            # Send to UI thread
                            self.app.call_from_thread(self._display_output, text)
                        except UnicodeDecodeError:
                            # Wait for more data
                            if len(buffer) > 10000:
                                # Force decode if buffer is too large
                                text = buffer.decode('utf-8', errors='replace')
                                buffer = b""
                                self.app.call_from_thread(self._display_output, text)
                                
            except OSError:
                # Pipe closed
                break
            except Exception as e:
                self.app.call_from_thread(
                    self.output.write, 
                    f"[red]Read error: {e}[/red]"
                )
                break
                
    def _display_output(self, text: str) -> None:
        """Display output in the terminal (UI thread)."""
        # Process ANSI codes and display
        lines = text.split('\n')
        for line in lines:
            if line.strip():
                self.output.write(line)
                
    async def send_prompt(self, prompt: str) -> None:
        """Send a prompt to Claude CLI."""
        if not self._is_running:
            self.output.write("[red]Claude CLI is not running. Starting...[/red]")
            await self.start_claude()
            # Wait a bit for startup
            await asyncio.sleep(1)
            
        if self._is_running and self.master_fd:
            # Add to command queue
            await self.command_queue.put(prompt)
            
    async def _process_commands(self) -> None:
        """Process commands from the queue."""
        while self._is_running:
            try:
                # Get command from queue
                command = await asyncio.wait_for(
                    self.command_queue.get(), 
                    timeout=0.1
                )
                
                # Send to Claude
                self._send_to_process(command)
                
                # Small delay between commands
                await asyncio.sleep(0.1)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.output.write(f"[red]Command error: {e}[/red]")
                
    def _send_to_process(self, text: str) -> None:
        """Send text to the Claude process."""
        if self.master_fd:
            try:
                # Ensure text ends with newline
                if not text.endswith('\n'):
                    text += '\n'
                    
                # Convert to bytes and send
                data = text.encode('utf-8')
                os.write(self.master_fd, data)
                
                # Echo the command
                self.output.write(f"[blue]> {text.strip()}[/blue]")
                
            except Exception as e:
                self.output.write(f"[red]Failed to send command: {e}[/red]")
                
    def action_interrupt(self) -> None:
        """Send interrupt signal (Ctrl+C) to Claude."""
        if self._is_running and self.master_fd:
            try:
                # Send Ctrl+C
                os.write(self.master_fd, b'\x03')
                self.output.write("[yellow]Sent interrupt signal[/yellow]")
            except Exception as e:
                self.output.write(f"[red]Failed to send interrupt: {e}[/red]")
                
    def action_restart(self) -> None:
        """Restart Claude CLI."""
        self.app.call_from_thread(self._restart_async)
        
    async def _restart_async(self) -> None:
        """Restart Claude CLI asynchronously."""
        self.output.write("[yellow]Restarting Claude CLI...[/yellow]")
        await self.stop_claude()
        await asyncio.sleep(0.5)
        await self.start_claude()

# Import struct for terminal size setting
import struct