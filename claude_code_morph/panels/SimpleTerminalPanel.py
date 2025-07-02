"""Simple Terminal Panel - Basic terminal for Claude CLI without pyte."""

import os
import sys
import pty
import select
import fcntl
import termios
import struct
import threading
import signal
from typing import Optional
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, TextArea
from textual.binding import Binding
from textual.reactive import reactive
import logging
import asyncio
from panels.BasePanel import BasePanel

class SimpleTerminalPanel(BasePanel):
    """Simple terminal panel that runs Claude CLI."""
    
    CSS = BasePanel.DEFAULT_CSS + """
    SimpleTerminalPanel TextArea {
        height: 100%;
        background: #1a1a1a;
        color: #ffffff;
    }
    
    SimpleTerminalPanel .panel-title {
        text-align: center;
        background: $primary;
        padding: 1;
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
        self.output_buffer = []
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal (Simple)", classes="panel-title")
            
            # Use TextArea for display
            self.display = TextArea(
                "",
                id="terminal-display",
                read_only=True,
                show_line_numbers=False
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
            # Fork with PTY
            pid, master = pty.fork()
            
            if pid == 0:  # Child process
                # Set up the environment
                os.environ['TERM'] = 'xterm-256color'
                os.environ['LINES'] = '40'
                os.environ['COLUMNS'] = '120'
                
                # Execute Claude CLI
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
                size = struct.pack('HHHH', 40, 120, 0, 0)
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
                
                self.status.update("Status: [green]Ready[/green]")
                logging.info(f"Started Claude CLI with PID {pid}")
                
        except Exception as e:
            self.display.text = f"Failed to start Claude CLI: {e}"
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}")
            
    def _read_output_loop(self) -> None:
        """Read output from PTY in a separate thread."""
        import re
        # Simple ANSI stripping
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        while self.running and self.pty_master is not None:
            try:
                # Check if data is available
                ready, _, _ = select.select([self.pty_master], [], [], 0.1)
                
                if ready:
                    # Read available data
                    data = os.read(self.pty_master, 4096)
                    if data:
                        # Decode and clean
                        text = data.decode('utf-8', errors='replace')
                        
                        # Remove ANSI escape sequences
                        clean_text = ansi_escape.sub('', text)
                        
                        # Add to buffer
                        self.output_buffer.append(clean_text)
                        
                        # Keep only last 1000 lines
                        all_text = ''.join(self.output_buffer)
                        lines = all_text.split('\n')
                        if len(lines) > 1000:
                            lines = lines[-1000:]
                            self.output_buffer = ['\n'.join(lines)]
                        
                        # Update display
                        self.app.call_from_thread(self._update_display)
                    else:
                        # EOF - process died
                        break
            except BlockingIOError:
                continue
            except OSError as e:
                if e.errno in (5, 9):  # I/O error or bad file descriptor
                    break
                else:
                    logging.error(f"Error reading from PTY: {e}")
                    break
            except Exception as e:
                logging.error(f"Unexpected error in read loop: {e}")
                break
                
        self.running = False
        self.app.call_from_thread(self._handle_process_exit)
        
    def _update_display(self) -> None:
        """Update the display with current buffer content."""
        content = ''.join(self.output_buffer)
        self.display.text = content
        
        # Scroll to bottom
        if hasattr(self.display, 'scroll_end'):
            self.display.scroll_end()
        
    def _handle_process_exit(self) -> None:
        """Handle Claude CLI process exit."""
        self.output_buffer.append("\n[Process terminated]\n")
        self._update_display()
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
        """Send a prompt to Claude CLI."""
        logging.info(f"send_prompt called with: {prompt[:100]}... mode={mode}")
        
        if not self.running or self.pty_master is None:
            self.output_buffer.append("\nClaude CLI is not running. Press Ctrl+R to restart.\n")
            self._update_display()
            return
            
        # Process based on mode
        if mode.lower() == 'morph':
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            prompt += f"\n\n[IMPORTANT: This is a 'morph' mode command. Work on the Claude Code Morph source at {morph_dir}]"
            
        try:
            # Log what we're sending
            self.output_buffer.append(f"\n>>> Sending: {prompt}\n")
            self._update_display()
            
            # Clear line and send prompt
            os.write(self.pty_master, b'\x15')  # Ctrl+U
            await asyncio.sleep(0.1)
            
            # Send the prompt
            os.write(self.pty_master, prompt.encode('utf-8'))
            os.write(self.pty_master, b'\n')
            
            # Update status
            self.status.update("Status: [yellow]Processing...[/yellow]")
            
        except Exception as e:
            self.output_buffer.append(f"\nError sending prompt: {e}\n")
            self._update_display()
            logging.error(f"Error sending prompt: {e}")
            
    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude CLI."""
        if self.pty_master:
            try:
                os.write(self.pty_master, b'\x03')  # Ctrl+C
                self.output_buffer.append("\n[Sent Ctrl+C]\n")
                self._update_display()
            except Exception as e:
                self.output_buffer.append(f"\nFailed to send interrupt: {e}\n")
                self._update_display()
                
    def action_restart(self) -> None:
        """Restart the Claude CLI session."""
        # Stop the running process
        self.running = False
        
        if self.pty_pid:
            try:
                os.kill(self.pty_pid, signal.SIGTERM)
                os.waitpid(self.pty_pid, 0)
            except:
                pass
                
        # Close PTY
        if self.pty_master:
            try:
                os.close(self.pty_master)
            except:
                pass
                
        # Clear display
        self.output_buffer = []
        self.display.text = ""
        
        # Restart
        self.status.update("Status: Restarting...")
        asyncio.create_task(self.start_claude_cli())
        
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel."""
        return self.display.text if hasattr(self, 'display') else ""
        
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
            self.pty_master = None