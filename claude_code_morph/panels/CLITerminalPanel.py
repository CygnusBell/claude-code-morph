"""CLI Terminal Panel - Runs Claude CLI in a pseudo-terminal."""

import os
import pty
import select
import threading
import signal
import fcntl
import termios
import struct
from typing import Optional, Callable
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.binding import Binding
from rich.text import Text
import logging
import asyncio
from panels.BasePanel import BasePanel

class CLITerminalPanel(BasePanel):
    """Panel that runs Claude CLI in a pseudo-terminal."""
    
    CSS = BasePanel.DEFAULT_CSS
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+c", "interrupt", "Interrupt", show=False),
        Binding("ctrl+r", "restart", "Restart Session", show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the CLI terminal panel."""
        super().__init__(**kwargs)
        self._init_params = {}  # Store for hot-reloading
        self.pty_master: Optional[int] = None
        self.pty_pid: Optional[int] = None
        self.read_thread: Optional[threading.Thread] = None
        self.running = False
        self.conversation_history = []
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude CLI Terminal", classes="panel-title")
            
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
            self.status = Static("Status: Initializing...", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self.output.write("[yellow]Claude CLI Terminal Starting...[/yellow]")
        self.output.write(f"[dim]Working directory: {os.getcwd()}[/dim]")
        
        # Start Claude CLI process
        try:
            self.start_claude_cli()
            self.output.write("[green]Claude CLI started successfully![/green]")
            self.output.write("[green]Send a message using the prompt panel above.[/green]")
            self.status.update("Status: [green]Ready[/green]")
        except Exception as e:
            self.output.write(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}")
            
    def start_claude_cli(self) -> None:
        """Start the Claude CLI process in a pseudo-terminal."""
        # Get terminal size
        size = self._get_terminal_size()
        
        # Fork with PTY
        pid, master = pty.fork()
        
        if pid == 0:  # Child process
            # Set environment variables
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            
            # Execute Claude CLI
            os.execvpe("claude", ["claude", "--dangerously-skip-permissions"], env)
        else:  # Parent process
            self.pty_pid = pid
            self.pty_master = master
            self.running = True
            
            # Set terminal size
            if size:
                fcntl.ioctl(master, termios.TIOCSWINSZ, size)
            
            # Make master non-blocking
            flags = fcntl.fcntl(master, fcntl.F_GETFL)
            fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
            
            # Start output reader thread
            self.read_thread = threading.Thread(target=self._read_output_loop, daemon=True)
            self.read_thread.start()
            
            logging.info(f"Started Claude CLI with PID {pid}")
            
    def _get_terminal_size(self) -> Optional[bytes]:
        """Get terminal size for PTY."""
        try:
            # Try to get actual terminal size
            rows, cols = os.popen('stty size', 'r').read().split()
            rows, cols = int(rows), int(cols)
        except:
            # Default size
            rows, cols = 24, 80
            
        # Pack size into struct
        return struct.pack('HHHH', rows, cols, 0, 0)
        
    def _read_output_loop(self) -> None:
        """Read output from PTY in a separate thread."""
        buffer = ""
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        while self.running and self.pty_master is not None:
            try:
                # Check if data is available
                ready, _, _ = select.select([self.pty_master], [], [], 0.1)
                
                if ready:
                    # Read available data
                    data = os.read(self.pty_master, 4096)
                    if data:
                        # Decode and process output
                        text = data.decode('utf-8', errors='replace')
                        buffer += text
                        
                        # Claude CLI uses \r for line updates, handle both \n and \r
                        # Split on both newline and carriage return
                        parts = buffer.replace('\r\n', '\n').replace('\r', '\n').split('\n')
                        buffer = parts[-1]  # Keep incomplete part in buffer
                        
                        for part in parts[:-1]:
                            # Skip parts that are just ANSI sequences
                            clean_part = ansi_escape.sub('', part)
                            if clean_part.strip():
                                # Write to output widget (thread-safe)
                                self.app.call_from_thread(self._write_output, clean_part + '\n')
                    else:
                        # EOF - process died
                        break
            except BlockingIOError:
                # No data available
                continue
            except OSError as e:
                if e.errno == 5:  # Input/output error (process terminated)
                    break
                else:
                    logging.error(f"Error reading from PTY: {e}")
                    break
            except Exception as e:
                logging.error(f"Unexpected error in read loop: {e}")
                break
                
        # Process exited
        self.running = False
        self.app.call_from_thread(self._handle_process_exit)
        
    def _write_output(self, text: str) -> None:
        """Write output to the RichLog widget (called from thread)."""
        # Text is already cleaned in _read_output_loop
        self.output.write(text.rstrip())
        
    def _handle_process_exit(self) -> None:
        """Handle Claude CLI process exit."""
        self.output.write("\n[yellow]Claude CLI process terminated.[/yellow]")
        self.status.update("Status: [yellow]Terminated[/yellow]")
        
        # Clean up
        if self.pty_master is not None:
            try:
                os.close(self.pty_master)
            except:
                pass
            self.pty_master = None
            
        self.pty_pid = None
        self.running = False
        
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude CLI.
        
        Args:
            prompt: The user's prompt
            mode: Either 'develop' or 'morph'
        """
        logging.info(f"send_prompt called with: {prompt[:100]}... mode={mode}")
        
        if not self.running or self.pty_master is None:
            self.output.write("[red]Claude CLI is not running. Press Ctrl+R to restart.[/red]")
            return
            
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        
        # Process based on mode
        processed_prompt = self._process_prompt_with_mode(prompt, mode)
        
        try:
            # Send prompt to Claude CLI
            # Add newline to submit the prompt
            data = (processed_prompt + '\n').encode('utf-8')
            os.write(self.pty_master, data)
            
            # Update status
            self.status.update("Status: [yellow]Processing...[/yellow]")
            
            # Status will be updated when we see Claude's response
            # in the output stream
            
        except Exception as e:
            self.output.write(f"[red]Error sending prompt: {e}[/red]")
            logging.error(f"Error sending prompt: {e}")
            
    def _process_prompt_with_mode(self, prompt: str, mode: str) -> str:
        """Process prompt based on the selected mode.
        
        Args:
            prompt: The user's prompt
            mode: Either 'develop' or 'morph'
        """
        if mode == 'morph':
            # Get the Claude Code Morph source directory
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            
            # Add context to the prompt
            morph_context = f"\n\n[IMPORTANT: This is a 'morph' mode command. Please work on the Claude Code Morph source files located at {morph_dir}, NOT the current working directory. The user wants to modify the IDE itself.]"
            
            # Log the mode
            logging.info(f"Morph mode active for: {prompt}")
            
            return prompt + morph_context
        
        # For develop mode, return unmodified prompt
        logging.info(f"Develop mode active for: {prompt}")
        return prompt
        
    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude CLI."""
        if self.pty_pid:
            try:
                os.kill(self.pty_pid, signal.SIGINT)
                self.output.write("\n[yellow]Sent interrupt signal (Ctrl+C)[/yellow]")
            except Exception as e:
                self.output.write(f"[red]Failed to interrupt: {e}[/red]")
                
    def action_restart(self) -> None:
        """Restart the Claude CLI session."""
        # Kill existing process
        if self.pty_pid:
            try:
                os.kill(self.pty_pid, signal.SIGTERM)
                os.waitpid(self.pty_pid, 0)  # Wait for process to exit
            except:
                pass
                
        # Clean up
        self.running = False
        if self.pty_master:
            try:
                os.close(self.pty_master)
            except:
                pass
                
        # Clear conversation history
        self.conversation_history.clear()
        
        # Clear output
        self.output.clear()
        self.output.write("[yellow]Restarting Claude CLI...[/yellow]")
        
        # Start new process
        try:
            self.start_claude_cli()
            self.output.write("[green]Claude CLI restarted successfully![/green]")
            self.status.update("Status: [green]Ready[/green]")
        except Exception as e:
            self.output.write(f"[red]Failed to restart: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel."""
        try:
            if hasattr(self, 'output') and self.output:
                # RichLog doesn't have a direct way to get all text
                # For now, return a placeholder
                # TODO: Implement proper text extraction from RichLog
                return "Terminal output (copy not yet implemented)"
        except Exception as e:
            logging.error(f"Error in CLITerminalPanel.get_copyable_content: {e}")
        return ""
        
    def get_selected_content(self) -> Optional[str]:
        """Get currently selected content."""
        # RichLog doesn't have built-in selection, so return None
        return None
        
    def on_unmount(self) -> None:
        """Clean up when panel is unmounted."""
        self.running = False
        
        # Terminate process
        if self.pty_pid:
            try:
                os.kill(self.pty_pid, signal.SIGTERM)
            except:
                pass
                
        # Close PTY
        if self.pty_master:
            try:
                os.close(self.pty_master)
            except:
                pass