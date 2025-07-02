"""Fixed Terminal Panel - Properly handles Claude CLI's cursor movements."""

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
from textual.containers import Vertical, ScrollableContainer
from textual.widgets import Static, RichLog
from textual.binding import Binding
import logging
import asyncio
from panels.BasePanel import BasePanel

try:
    import pyte
    PYTE_AVAILABLE = True
except ImportError:
    PYTE_AVAILABLE = False

class FixedTerminalPanel(BasePanel):
    """Terminal panel that properly handles Claude CLI output."""
    
    CSS = BasePanel.DEFAULT_CSS + """
    FixedTerminalPanel {
        layout: vertical;
        height: 100%;
    }
    
    #terminal-display {
        height: 1fr;
        background: #0a0a0a;
        color: #e0e0e0;
        padding: 1;
        border: solid #444444;
        overflow-y: scroll;
    }
    
    #terminal-display:focus {
        border: solid #00ff00;
    }
    """
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+c", "interrupt", "Interrupt", show=False),
        Binding("ctrl+r", "restart", "Restart Session", show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the terminal panel."""
        super().__init__(**kwargs)
        self.pty_master: Optional[int] = None
        self.pty_pid: Optional[int] = None
        self.read_thread: Optional[threading.Thread] = None
        self.running = False
        self.screen = None
        self.stream = None
        self.last_prompt_time = 0
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal", classes="panel-title")
            
            # Use RichLog for better control
            self.display = RichLog(
                highlight=False,
                markup=True,
                wrap=True,
                id="terminal-display",
                auto_scroll=True,
                max_lines=1000
            )
            yield self.display
            
            # Status bar
            self.status = Static("Status: Starting...", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        await self.start_claude_cli()
        
    async def start_claude_cli(self) -> None:
        """Start Claude CLI in a pseudo-terminal."""
        try:
            rows, cols = 40, 120
            
            # Create pyte screen
            if PYTE_AVAILABLE:
                self.screen = pyte.Screen(cols, rows)
                self.stream = pyte.ByteStream(self.screen)
                # Enable LNM mode for better line handling
                self.screen.set_mode(pyte.modes.LNM)
            
            # Fork with PTY
            pid, master = pty.fork()
            
            if pid == 0:  # Child
                os.environ['TERM'] = 'xterm-256color'
                os.environ['LINES'] = str(rows)
                os.environ['COLUMNS'] = str(cols)
                
                try:
                    os.execvp("claude", ["claude", "--dangerously-skip-permissions"])
                except Exception as e:
                    print(f"Failed to start claude: {e}", file=sys.stderr)
                    sys.exit(1)
            else:  # Parent
                self.pty_pid = pid
                self.pty_master = master
                self.running = True
                
                # Set terminal size
                size = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(master, termios.TIOCSWINSZ, size)
                
                # Make non-blocking
                flags = fcntl.fcntl(master, fcntl.F_GETFL)
                fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
                
                # Start reader thread
                self.read_thread = threading.Thread(
                    target=self._read_output_loop,
                    daemon=True
                )
                self.read_thread.start()
                
                self.status.update("Status: [green]Ready[/green]")
                self.display.write("[dim]Claude CLI started[/dim]")
                
        except Exception as e:
            self.display.write(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}")
            
    def _read_output_loop(self) -> None:
        """Read output from PTY."""
        buffer = b""
        last_update = 0
        
        while self.running and self.pty_master is not None:
            try:
                ready, _, _ = select.select([self.pty_master], [], [], 0.1)
                
                if ready:
                    data = os.read(self.pty_master, 4096)
                    if data:
                        buffer += data
                        
                        # Update display periodically or when we have enough data
                        current_time = time.time()
                        if len(buffer) > 1000 or current_time - last_update > 0.1:
                            self._process_buffer(buffer)
                            buffer = b""
                            last_update = current_time
                    else:
                        break
                else:
                    # Process any remaining buffer
                    if buffer:
                        self._process_buffer(buffer)
                        buffer = b""
            except BlockingIOError:
                continue
            except OSError as e:
                if e.errno in (5, 9):
                    break
                logging.error(f"Error reading: {e}")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                break
                
        self.running = False
        self.app.call_from_thread(self._handle_process_exit)
        
    def _process_buffer(self, data: bytes) -> None:
        """Process buffer and update display."""
        if self.stream and PYTE_AVAILABLE:
            # Feed to pyte
            self.stream.feed(data)
            
            # Get display content
            lines = []
            for line in self.screen.display:
                stripped = line.rstrip()
                if stripped:
                    lines.append(stripped)
            
            # Update display
            if lines:
                self.app.call_from_thread(self._update_display, lines)
        else:
            # Fallback: basic processing
            try:
                text = data.decode('utf-8', errors='replace')
                # Remove some ANSI codes
                text = re.sub(r'\x1b\[[0-9;]*[mGKHJ]', '', text)
                text = re.sub(r'\x1b\[[0-9]*[AD]', '\n', text)  # Convert cursor movements to newlines
                
                if text.strip():
                    self.app.call_from_thread(self.display.write, text)
            except:
                pass
                
    def _update_display(self, lines: list) -> None:
        """Update the display with pyte screen content."""
        # Clear and rewrite
        self.display.clear()
        
        # Write all non-empty lines
        for line in lines:
            if line.strip():
                self.display.write(line)
                
        # Check for Claude's response
        content = '\n'.join(lines)
        if time.time() - self.last_prompt_time < 10:  # Within 10 seconds of sending prompt
            if any(word in content.lower() for word in ['hello', 'hi', 'sure', 'help', 'i can']):
                self.status.update("Status: [green]Response received[/green]")
                logging.info("Claude response detected in display")
                
    def _handle_process_exit(self) -> None:
        """Handle process exit."""
        self.display.write("\n[yellow]Claude CLI terminated[/yellow]")
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
        logging.info(f"Sending prompt: {prompt[:50]}...")
        
        if not self.running or not self.pty_master:
            self.display.write("[red]Claude CLI is not running[/red]")
            return
            
        # Add mode context if needed
        if mode.lower() == 'morph':
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            prompt += f"\n\n[Work on Claude Code Morph source at {morph_dir}]"
            
        try:
            # Mark when we send the prompt
            self.last_prompt_time = time.time()
            
            # Clear display to see new response clearly
            self.display.clear()
            self.display.write(f"[dim]>>> {prompt}[/dim]\n")
            
            # Send the prompt
            os.write(self.pty_master, prompt.encode('utf-8'))
            os.write(self.pty_master, b'\n')
            
            self.status.update("Status: [yellow]Processing...[/yellow]")
            
            # Schedule status update
            asyncio.create_task(self._update_status_later())
            
        except Exception as e:
            self.display.write(f"[red]Error: {e}[/red]")
            logging.error(f"Error sending prompt: {e}")
            
    async def _update_status_later(self) -> None:
        """Update status after delay."""
        await asyncio.sleep(5)
        if self.running and time.time() - self.last_prompt_time < 10:
            self.status.update("Status: [green]Ready[/green]")
            
    def action_interrupt(self) -> None:
        """Send interrupt signal."""
        if self.pty_master:
            try:
                os.write(self.pty_master, b'\x03')
                self.display.write("\n[yellow]Interrupt sent[/yellow]")
            except:
                pass
                
    def action_restart(self) -> None:
        """Restart Claude CLI."""
        self.running = False
        
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
                
        self.display.clear()
        self.status.update("Status: Restarting...")
        
        asyncio.create_task(self.start_claude_cli())
        
    def get_copyable_content(self) -> str:
        """Get copyable content."""
        return ""
        
    def get_selected_content(self) -> Optional[str]:
        """Get selected content."""
        return None
        
    def on_unmount(self) -> None:
        """Clean up on unmount."""
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