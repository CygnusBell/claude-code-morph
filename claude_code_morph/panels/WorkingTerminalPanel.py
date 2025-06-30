"""Working Terminal Panel - Properly handles Claude CLI interaction."""

import os
import sys
import pty
import select
import fcntl
import termios
import struct
import threading
import signal
import time
import re
from typing import Optional
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.binding import Binding
from textual.reactive import reactive
import logging
import asyncio
from panels.BasePanel import BasePanel

try:
    import pyte
    PYTE_AVAILABLE = True
except ImportError:
    PYTE_AVAILABLE = False

class WorkingTerminalPanel(BasePanel):
    """Terminal panel that properly handles Claude CLI."""
    
    CSS = BasePanel.DEFAULT_CSS + """
    WorkingTerminalPanel {
        layout: vertical;
        height: 100%;
    }
    
    #terminal-output {
        height: 1fr;
        background: #0c0c0c;
        color: #cccccc;
        padding: 1;
        border: solid #444444;
        overflow-y: scroll;
    }
    
    #terminal-output:focus {
        border: solid #00ff00;
    }
    """
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+c", "interrupt", "Interrupt"),
        Binding("ctrl+r", "restart", "Restart Session"),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the terminal panel."""
        super().__init__(**kwargs)
        self.pty_master: Optional[int] = None
        self.pty_pid: Optional[int] = None
        self.read_thread: Optional[threading.Thread] = None
        self.running = False
        self.claude_ready = False
        self.pyte_screen = None
        self.pyte_stream = None
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal", classes="panel-title")
            
            # Terminal output display
            self.output = RichLog(
                highlight=False,
                markup=True,
                wrap=True,
                id="terminal-output",
                auto_scroll=True
            )
            yield self.output
            
            # Status bar
            self.status = Static("Status: Starting...", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        await self.start_claude_cli()
        
    async def start_claude_cli(self) -> None:
        """Start Claude CLI in a pseudo-terminal."""
        try:
            # Terminal size
            rows, cols = 40, 120
            
            # Create pyte screen if available
            if PYTE_AVAILABLE:
                self.pyte_screen = pyte.Screen(cols, rows)
                self.pyte_stream = pyte.ByteStream(self.pyte_screen)
                self.output.write("[dim]Using pyte terminal emulation[/dim]")
            else:
                self.output.write("[dim]Pyte not available, using basic display[/dim]")
            
            # Fork with PTY
            pid, master = pty.fork()
            
            if pid == 0:  # Child process
                os.environ['TERM'] = 'xterm-256color'
                os.environ['LINES'] = str(rows)
                os.environ['COLUMNS'] = str(cols)
                
                try:
                    os.execvp("claude", ["claude", "--dangerously-skip-permissions"])
                except Exception as e:
                    print(f"Failed to start claude: {e}", file=sys.stderr)
                    sys.exit(1)
            else:  # Parent process
                self.pty_pid = pid
                self.pty_master = master
                self.running = True
                
                # Set terminal size
                size = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(master, termios.TIOCSWINSZ, size)
                
                # Make master non-blocking
                flags = fcntl.fcntl(master, fcntl.F_GETFL)
                fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                
                # Start reader thread
                self.read_thread = threading.Thread(
                    target=self._read_output_loop,
                    daemon=True
                )
                self.read_thread.start()
                
                # Wait for Claude to be ready
                await self._wait_for_ready()
                
        except Exception as e:
            self.output.write(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}")
            
    async def _wait_for_ready(self) -> None:
        """Wait for Claude to be ready for input."""
        self.output.write("\n[yellow]Waiting for Claude to initialize...[/yellow]")
        
        # Wait up to 5 seconds for Claude to be ready
        for i in range(50):
            if self.claude_ready:
                self.output.write("[green]Claude is ready![/green]")
                self.status.update("Status: [green]Ready[/green]")
                return
            await asyncio.sleep(0.1)
            
        self.output.write("[yellow]Claude may not be fully ready[/yellow]")
        self.status.update("Status: [yellow]Ready (timeout)[/yellow]")
        
    def _read_output_loop(self) -> None:
        """Read output from PTY and process it."""
        ansi_escape = re.compile(rb'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        buffer = b""
        
        while self.running and self.pty_master is not None:
            try:
                ready, _, _ = select.select([self.pty_master], [], [], 0.1)
                
                if ready:
                    data = os.read(self.pty_master, 4096)
                    if data:
                        buffer += data
                        
                        # Feed to pyte if available
                        if self.pyte_stream:
                            self.pyte_stream.feed(data)
                        
                        # Process for display
                        text = data.decode('utf-8', errors='replace')
                        
                        # Check if Claude is ready
                        if not self.claude_ready and ('> ' in text or 'shortcuts' in text):
                            self.claude_ready = True
                            logging.info("Claude CLI is ready for input")
                        
                        # Clean and display
                        if self.pyte_screen:
                            # Use pyte display
                            self.app.call_from_thread(self._update_pyte_display)
                        else:
                            # Basic cleaning
                            clean = ansi_escape.sub(b'', data).decode('utf-8', errors='replace')
                            if clean.strip():
                                self.app.call_from_thread(self.output.write, clean)
                    else:
                        break
            except BlockingIOError:
                continue
            except OSError as e:
                if e.errno in (5, 9):
                    break
                logging.error(f"Error reading from PTY: {e}")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                break
                
        self.running = False
        self.app.call_from_thread(self._handle_process_exit)
        
    def _update_pyte_display(self) -> None:
        """Update display from pyte screen."""
        if not self.pyte_screen:
            return
            
        # Get screen content
        lines = []
        for line in self.pyte_screen.display:
            if line.rstrip():  # Only include non-empty lines
                lines.append(line.rstrip())
        
        # Clear and update
        self.output.clear()
        for line in lines:
            self.output.write(line)
            
    def _handle_process_exit(self) -> None:
        """Handle Claude CLI process exit."""
        self.output.write("\n[yellow]Claude CLI process terminated.[/yellow]")
        self.status.update("Status: [yellow]Terminated[/yellow]")
        
        if self.pty_master:
            try:
                os.close(self.pty_master)
            except:
                pass
            self.pty_master = None
            
        self.pty_pid = None
        self.running = False
        
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude CLI."""
        logging.info(f"send_prompt called with: {prompt[:100]}... mode={mode}")
        
        if not self.running or not self.pty_master:
            self.output.write("[red]Claude CLI is not running. Press Ctrl+R to restart.[/red]")
            return
            
        # Wait a bit if Claude just started
        if not self.claude_ready:
            self.output.write("[yellow]Waiting for Claude...[/yellow]")
            await asyncio.sleep(1)
            
        # Process based on mode
        if mode.lower() == 'morph':
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            prompt += f"\n\n[IMPORTANT: This is a 'morph' mode command. Work on the Claude Code Morph source at {morph_dir}]"
            
        try:
            # Clear any existing input
            os.write(self.pty_master, b'\x15')  # Ctrl+U
            await asyncio.sleep(0.05)
            
            # Send the prompt
            os.write(self.pty_master, prompt.encode('utf-8'))
            os.write(self.pty_master, b'\n')
            
            self.status.update(f"Status: [yellow]Processing ({len(prompt)} chars)...[/yellow]")
            
            # Schedule status update
            asyncio.create_task(self._update_status_later())
            
        except Exception as e:
            self.output.write(f"[red]Error sending prompt: {e}[/red]")
            logging.error(f"Error sending prompt: {e}")
            
    async def _update_status_later(self) -> None:
        """Update status after a delay."""
        await asyncio.sleep(3)
        if self.running:
            self.status.update("Status: [green]Ready[/green]")
            
    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude CLI."""
        if self.pty_master:
            try:
                os.write(self.pty_master, b'\x03')  # Ctrl+C
                self.output.write("\n[yellow]Sent interrupt signal[/yellow]")
            except Exception as e:
                self.output.write(f"[red]Failed to interrupt: {e}[/red]")
                
    def action_restart(self) -> None:
        """Restart the Claude CLI session."""
        self.running = False
        self.claude_ready = False
        
        if self.pty_pid:
            try:
                os.kill(self.pty_pid, signal.SIGTERM)
                os.waitpid(self.pty_pid, 0)
            except:
                pass
                
        if self.pty_master:
            try:
                os.close(self.pty_master)
            except:
                pass
                
        self.output.clear()
        self.output.write("[yellow]Restarting Claude CLI...[/yellow]")
        self.status.update("Status: Restarting...")
        
        asyncio.create_task(self.start_claude_cli())
        
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel."""
        if self.pyte_screen and PYTE_AVAILABLE:
            return '\n'.join(line.rstrip() for line in self.pyte_screen.display if line.strip())
        return ""
        
    def get_selected_content(self) -> Optional[str]:
        """Get currently selected content."""
        return None
        
    def on_unmount(self) -> None:
        """Clean up when panel is unmounted."""
        self.running = False
        
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.5)
        
        if self.pty_pid:
            try:
                os.kill(self.pty_pid, signal.SIGTERM)
                os.waitpid(self.pty_pid, os.WNOHANG)
            except:
                pass
                
        if self.pty_master:
            try:
                os.close(self.pty_master)
            except:
                pass