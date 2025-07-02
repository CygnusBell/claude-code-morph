"""Terminal Panel - Full terminal emulator for Claude CLI."""

import os
import sys
import pty
import select
import fcntl
import termios
import struct
import threading
import signal
from typing import Optional, List
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static
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

class TerminalWidget(Static):
    """Custom terminal widget that displays terminal screen."""
    
    can_focus = True  # Make the widget focusable
    
    def __init__(self, rows: int = 50, cols: int = 150, **kwargs):
        super().__init__("", **kwargs)
        self.rows = rows
        self.cols = cols
        self.buffer = []  # Simple line buffer for fallback
        self.pty_master = None  # Will be set by parent
        self.add_class("terminal-content")  # Ensure monospace font
        
        if PYTE_AVAILABLE:
            # Create virtual terminal screen - renamed to avoid conflict with Textual's screen property
            self.term_screen = pyte.Screen(cols, rows)
            self.term_stream = pyte.ByteStream(self.term_screen)
            # Set mode for better compatibility
            self.term_screen.set_mode(pyte.modes.LNM)  # Line feed/new line mode
        else:
            self.term_screen = None
            self.term_stream = None
            
    def feed(self, data: bytes) -> None:
        """Feed data to the terminal emulator."""
        if self.term_stream:
            # Feed data to pyte
            self.term_stream.feed(data)
            # Refresh display immediately
            self.refresh_display()
            
            # Log significant content for debugging
            if len(data) < 500:  # Only log small chunks
                try:
                    text = data.decode('utf-8', errors='replace')
                    # Check for actual content (not just escape sequences)
                    import re
                    cleaned = re.sub(r'\x1b\[[0-9;]*[mGKHJ]', '', text)
                    if cleaned.strip() and len(cleaned) > 10:
                        logging.debug(f"Terminal content: {cleaned[:100]}")
                except:
                    pass
        else:
            # Fallback: Simple text display
            text = data.decode('utf-8', errors='replace')
            # Basic ANSI stripping
            import re
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            clean_text = ansi_escape.sub('', text)
            
            # Handle carriage returns and newlines
            lines = clean_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
            
            for i, line in enumerate(lines):
                if i == len(lines) - 1 and not line.endswith('\n'):
                    # Incomplete line - append to last buffer line
                    if self.buffer:
                        self.buffer[-1] += line
                    else:
                        self.buffer.append(line)
                else:
                    if line:  # Only add non-empty lines
                        self.buffer.append(line)
                        
            # Keep only last N lines
            max_lines = self.rows * 2
            if len(self.buffer) > max_lines:
                self.buffer = self.buffer[-max_lines:]
                
            # Update display
            self.update('\n'.join(self.buffer))
            
    def refresh_display(self) -> None:
        """Update the display with current terminal content."""
        if not self.term_screen:
            return
            
        # Get the entire screen content
        lines = []
        
        # Use pyte's display method which handles the buffer properly
        for line in self.term_screen.display:
            lines.append(line)
        
        # Find last non-empty line
        last_line = len(lines) - 1
        while last_line >= 0 and not lines[last_line].strip():
            last_line -= 1
        
        # Keep content up to last line plus some padding
        if last_line >= 0:
            lines = lines[:last_line + 2]
        
        # Join and update
        content = "\n".join(lines)
        self.update(content)
        
        # Log for debugging if we see interesting content
        if any(keyword in content.lower() for keyword in ['hello', 'claude:', 'error', 'response']):
            logging.info(f"Terminal shows interesting content: {content[-200:]}")
        
    def clear(self) -> None:
        """Clear the terminal."""
        if self.term_screen:
            self.term_screen.reset()
            self.refresh_display()
        else:
            self.buffer = []
            self.update("")
    
    def on_key(self, event) -> None:
        """Handle key events - pass them to the PTY."""
        if not self.pty_master:
            return
            
        try:
            key = event.key
            
            # Handle special keys
            if key == "enter":
                os.write(self.pty_master, b'\n')
            elif key == "backspace":
                os.write(self.pty_master, b'\x7f')
            elif key == "tab":
                os.write(self.pty_master, b'\t')
            elif key == "shift+tab":
                os.write(self.pty_master, b'\x1b[Z')  # Reverse tab
            elif key == "escape":
                os.write(self.pty_master, b'\x1b')
            elif key == "up":
                os.write(self.pty_master, b'\x1b[A')
            elif key == "down":
                os.write(self.pty_master, b'\x1b[B')
            elif key == "left":
                os.write(self.pty_master, b'\x1b[D')
            elif key == "right":
                os.write(self.pty_master, b'\x1b[C')
            elif key == "ctrl+c":
                os.write(self.pty_master, b'\x03')  # Ctrl+C
            elif len(key) == 1:
                # Regular character
                os.write(self.pty_master, key.encode('utf-8'))
        except:
            pass

class TerminalPanel(BasePanel):
    """Panel that runs Claude CLI in a full terminal emulator."""
    
    CSS = BasePanel.DEFAULT_CSS + """
    TerminalWidget {
        height: 100%;
        background: #0a0a0a;
        color: #00ff00;
        padding: 1;
        border: solid #444444;
        overflow-y: scroll;
        font-family: monospace;
        font-size: 14px;
        line-height: 1.2;
    }
    
    TerminalWidget:focus {
        border: solid #00ff00;
    }
    
    .terminal-content {
        font-family: "Courier New", "Monaco", "Consolas", monospace;
        white-space: pre;
        word-wrap: break-word;
    }
    
    #terminal-status {
        dock: bottom;
        height: 1;
        background: #1a1a1a;
        color: #888;
        padding: 0 1;
    }
    """
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+c", "interrupt", "Interrupt", priority=True, show=False),
        Binding("ctrl+r", "restart", "Restart Session", show=False),
        Binding("shift+tab", "pass_through", "Pass to Claude", priority=True),
        Binding("escape", "pass_through_escape", "Pass Escape", priority=True),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the terminal panel."""
        super().__init__(**kwargs)
        self._init_params = {}
        self.pty_master: Optional[int] = None
        self.pty_pid: Optional[int] = None
        self.read_thread: Optional[threading.Thread] = None
        self.running = False
        self.terminal_widget: Optional[TerminalWidget] = None
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal", classes="panel-title")
            
            # Terminal widget - works with or without pyte
            # Use larger size for better visibility
            self.terminal_widget = TerminalWidget(rows=50, cols=150, id="terminal-output")
            yield self.terminal_widget
            
            # Status bar
            self.status = Static("Status: Starting...", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        await self.start_claude_cli()
            
    async def start_claude_cli(self) -> None:
        """Start Claude CLI in a pseudo-terminal."""
        try:
            # Get terminal size
            rows = self.terminal_widget.rows if self.terminal_widget else 50
            cols = self.terminal_widget.cols if self.terminal_widget else 150
            
            # Fork with PTY
            pid, master = pty.fork()
            
            if pid == 0:  # Child process
                # Set up the environment
                os.environ['TERM'] = 'xterm-256color'
                os.environ['LINES'] = str(rows)
                os.environ['COLUMNS'] = str(cols)
                
                # Execute Claude CLI
                try:
                    os.execvp("claude", ["claude", "--dangerously-skip-permissions"])
                except Exception as e:
                    # If claude fails to start, print error and exit
                    print(f"Failed to start claude: {e}", file=sys.stderr)
                    sys.exit(1)
            else:  # Parent process
                self.pty_pid = pid
                self.pty_master = master
                self.running = True
                
                # Connect the PTY to the terminal widget for keyboard input
                if self.terminal_widget:
                    self.terminal_widget.pty_master = master
                
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
                
                self.status.update("Status: [green]Ready[/green]")
                logging.info(f"Started Claude CLI with PID {pid}")
                
                # Check if process is actually running
                import time
                time.sleep(0.5)  # Give it more time to fully initialize
                try:
                    os.kill(pid, 0)  # Check if process exists
                    logging.info(f"Claude CLI process {pid} is running")
                    # Force a refresh after initialization
                    if self.terminal_widget:
                        # Add initial message to show terminal is ready
                        self.terminal_widget.feed(b"Claude CLI started successfully. Waiting for initialization...\r\n")
                        self.terminal_widget.refresh_display()
                except ProcessLookupError:
                    logging.error(f"Claude CLI process {pid} died immediately")
                    self.terminal_widget.update("Claude CLI failed to start properly")
                
        except Exception as e:
            if self.terminal_widget:
                self.terminal_widget.update(f"Failed to start Claude CLI: {e}")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}")
            
    def _read_output_loop(self) -> None:
        """Read output from PTY and feed to terminal emulator."""
        while self.running and self.pty_master is not None:
            try:
                # Check if data is available
                ready, _, _ = select.select([self.pty_master], [], [], 0.1)
                
                if ready:
                    # Read available data
                    data = os.read(self.pty_master, 4096)
                    if data:
                        # Feed to terminal emulator
                        self.app.call_from_thread(self._update_terminal, data)
                    else:
                        # EOF - process died
                        break
            except BlockingIOError:
                # No data available
                continue
            except OSError as e:
                if e.errno == 5:  # Input/output error
                    break
                elif e.errno == 9:  # Bad file descriptor - PTY was closed
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
        
    def _update_terminal(self, data: bytes) -> None:
        """Update terminal display with new data."""
        if self.terminal_widget:
            self.terminal_widget.feed(data)
            # Log all outputs to debug display issues
            logging.debug(f"Terminal output (len={len(data)}): {repr(data[:200])}")
            # Also log the cleaned text to see what users should see
            if hasattr(self.terminal_widget, 'term_screen') and self.terminal_widget.term_screen:
                # Get last line from pyte screen
                last_line = ""
                for x in range(self.terminal_widget.term_screen.columns):
                    char = self.terminal_widget.term_screen.buffer[self.terminal_widget.term_screen.cursor.y][x]
                    last_line += char.data or " "
                logging.debug(f"Terminal screen cursor line: {repr(last_line.rstrip())}")
            
    def _handle_process_exit(self) -> None:
        """Handle Claude CLI process exit."""
        if self.terminal_widget:
            self.terminal_widget.feed(b"\r\n[Process terminated]\r\n")
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
            if self.terminal_widget:
                self.terminal_widget.feed(b"\r\nClaude CLI is not running. Press Ctrl+R to restart.\r\n")
            return
            
        # Process based on mode
        processed_prompt = self._process_prompt_with_mode(prompt, mode)
        
        try:
            # Clear any existing input line first
            os.write(self.pty_master, b'\x15')  # Ctrl+U to clear line
            
            # Send prompt to Claude CLI
            data = processed_prompt.encode('utf-8')
            
            # Send the prompt character by character with small delays
            # This mimics human typing which might help Claude recognize input
            for char in data:
                os.write(self.pty_master, bytes([char]))
                await asyncio.sleep(0.001)  # 1ms between chars
            
            # Now send newline to submit
            os.write(self.pty_master, b'\n')
            
            # Update status
            self.status.update(f"Status: [yellow]Processing...[/yellow] ({len(prompt)} chars)")
            
            # Log that we sent the prompt
            logging.info(f"Sent prompt to Claude CLI: {prompt[:50]}...")
            
            # Force multiple display refreshes to catch the response
            for i in range(10):
                await asyncio.sleep(0.5)
                if self.terminal_widget:
                    self.terminal_widget.refresh_display()
            
        except Exception as e:
            if self.terminal_widget:
                self.terminal_widget.feed(f"\r\nError sending prompt: {e}\r\n".encode())
            logging.error(f"Error sending prompt: {e}")
            
    async def _delayed_refresh(self) -> None:
        """Refresh the display after a short delay."""
        await asyncio.sleep(0.5)
        if self.terminal_widget:
            self.terminal_widget.refresh_display()
            
    def _process_prompt_with_mode(self, prompt: str, mode: str) -> str:
        """Process prompt based on the selected mode."""
        if mode.lower() == 'morph':
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            morph_context = f"\n\n[IMPORTANT: This is a 'morph' mode command. Please work on the Claude Code Morph source files located at {morph_dir}, NOT the current working directory. The user wants to modify the IDE itself.]"
            logging.info(f"Morph mode active for: {prompt}")
            return prompt + morph_context
        
        logging.info(f"Develop mode active for: {prompt}")
        return prompt
        
    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude CLI."""
        if self.pty_master:
            try:
                # Send Ctrl+C directly through PTY
                os.write(self.pty_master, b'\x03')  # Ctrl+C
            except Exception as e:
                if self.terminal_widget:
                    self.terminal_widget.feed(f"\r\nFailed to send interrupt: {e}\r\n".encode())
                    
    def action_pass_through(self) -> None:
        """Pass through Shift+Tab to Claude."""
        if self.pty_master:
            try:
                # Send Shift+Tab (reverse tab)
                os.write(self.pty_master, b'\x1b[Z')
            except:
                pass
                
    def action_pass_through_escape(self) -> None:
        """Pass through Escape key to Claude."""
        if self.pty_master:
            try:
                # Send ESC
                os.write(self.pty_master, b'\x1b')
            except:
                pass
                
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
                
        # Clear terminal
        if self.terminal_widget:
            self.terminal_widget.clear()
        
        # Restart
        self.status.update("Status: Restarting...")
        asyncio.create_task(self.start_claude_cli())
        
    def on_key(self, event) -> None:
        """Handle key events - let TerminalWidget handle most keys when focused."""
        # Only handle our specific bindings at the panel level
        # The TerminalWidget will handle key input when it has focus
        pass
            
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel."""
        if self.terminal_widget and self.terminal_widget.term_screen:
            lines = []
            for y in range(self.terminal_widget.term_screen.lines):
                line = ""
                for x in range(self.terminal_widget.term_screen.columns):
                    char = self.terminal_widget.term_screen.buffer[y][x]
                    line += char.data or " "
                lines.append(line.rstrip())
            return "\n".join(lines)
        return ""
        
    def get_selected_content(self) -> Optional[str]:
        """Get currently selected content."""
        return None
        
    def on_unmount(self) -> None:
        """Clean up when panel is unmounted."""
        # Stop the read thread first
        self.running = False
        
        # Wait a bit for thread to stop
        if self.read_thread and self.read_thread.is_alive():
            self.read_thread.join(timeout=0.5)
        
        # Terminate process
        if self.pty_pid:
            try:
                os.kill(self.pty_pid, signal.SIGTERM)
                os.waitpid(self.pty_pid, os.WNOHANG)
            except:
                pass
                
        # Close PTY
        if self.pty_master:
            try:
                os.close(self.pty_master)
            except:
                pass
            self.pty_master = None