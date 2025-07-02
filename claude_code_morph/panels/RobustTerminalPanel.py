"""Robust Terminal Panel - Full interactive Claude CLI experience using pexpect."""

import os
import asyncio
import pexpect
import threading
import queue
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog, TextArea
from textual.binding import Binding
from rich.text import Text
from textual.events import Key
import re

try:
    from .BasePanel import BasePanel
except ImportError:
    # Fallback for when module is loaded dynamically
    from claude_code_morph.panels.BasePanel import BasePanel


class RobustTerminalPanel(BasePanel):
    """Terminal panel with full Claude CLI interactivity using pexpect."""
    
    # Combine BasePanel CSS with our additional styles
    CSS = BasePanel.CSS + """
    RobustTerminalPanel {
        layout: vertical;
        height: 100%;
    }
    
    RobustTerminalPanel:focus {
        border: solid $accent;
    }
    
    #terminal-output {
        height: 1fr;
        background: #0c0c0c;
        color: #f0f0f0;
        padding: 1;
        border: solid #333333;
        overflow-y: scroll;
    }
    
    #terminal-output:focus {
        border: solid $accent;
    }
    
    #terminal-status {
        height: 1;
        background: #1a1a1a;
        color: #888888;
        padding: 0 1;
    }
    """
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+c", "interrupt", "Interrupt", show=False),
        Binding("ctrl+r", "restart", "New Session", show=False),
        Binding("ctrl+d", "send_eof", "Send EOF", show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the robust terminal panel."""
        super().__init__(**kwargs)
        self.claude_process: Optional[pexpect.spawn] = None
        self.output_queue = queue.Queue()
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self.conversation_history = []
        self.can_focus = True  # Allow this panel to receive focus
        self.terminal_buffer = []  # Store terminal lines
        self.max_lines = 1000  # Maximum lines to keep in buffer
        self.last_full_output = ""  # Track the full terminal state
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal (Interactive)", classes="panel-title")
            
            # Use Static widget that we can update in place
            self.output = Static("", id="terminal-output")
            yield self.output
            
            self.status = Static("Status: Initializing...", id="terminal-status")
            yield self.status
            
    async def start_claude_cli(self) -> None:
        """Start the Claude CLI process using pexpect."""
        try:
            # Set up environment
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['COLUMNS'] = '120'
            env['LINES'] = '40'
            
            # Build command with proper flags
            cmd = ['claude', '--dangerously-skip-permissions']
            
            # Start Claude with pexpect
            self.claude_process = pexpect.spawn(
                cmd[0],
                args=cmd[1:],
                encoding='utf-8',
                dimensions=(40, 120),
                env=env,
                timeout=None,  # No timeout - Claude can take as long as needed
                echo=False  # Don't echo input back
            )
            
            # Set up delaybeforesend to handle prompt timing
            self.claude_process.delaybeforesend = 0.1
            
            self.running = True
            
            # Start output reader thread
            self.reader_thread = threading.Thread(
                target=self._read_output_loop,
                daemon=True
            )
            self.reader_thread.start()
            
            # Process output updates
            asyncio.create_task(self._process_output_queue())
            
            self.status.update("Status: [green]Connected[/green]")
            logging.info("Claude CLI started successfully with pexpect")
            
            # Wait a bit for Claude to initialize and show welcome message
            await asyncio.sleep(1.0)
            
            # Check if Claude is actually responding
            if not self.claude_process.isalive():
                raise Exception("Claude process died immediately after starting")
                
            # Claude CLI is interactive and uses ANSI escape codes
            logging.info("Claude CLI is running in interactive mode")
            
        except Exception as e:
            self._append_line(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}", exc_info=True)
            
    def _read_output_loop(self) -> None:
        """Read output from Claude process in a separate thread."""
        try:
            logging.debug("Starting output reader thread")
            while self.running and self.claude_process and self.claude_process.isalive():
                try:
                    # Read with a small timeout to check running status
                    chunk = self.claude_process.read_nonblocking(size=4096, timeout=0.1)
                    if chunk:
                        logging.debug(f"Got chunk: {repr(chunk[:50])}")
                        self.output_queue.put(('output', chunk))
                except pexpect.TIMEOUT:
                    # Normal - no data available
                    continue
                except pexpect.EOF:
                    self.output_queue.put(('eof', None))
                    break
                except Exception as e:
                    if self.running:  # Only log if we're still supposed to be running
                        logging.error(f"Error reading from Claude: {e}")
                        self.output_queue.put(('error', str(e)))
                    break
                    
        except Exception as e:
            logging.error(f"Reader thread crashed: {e}")
        finally:
            self.running = False
            self.output_queue.put(('exit', None))
            
    async def _process_output_queue(self) -> None:
        """Process output from the queue and update the UI."""
        current_line = ""
        in_streaming_response = False
        
        while self.running:
            try:
                # Check queue with short timeout
                if not self.output_queue.empty():
                    msg_type, data = self.output_queue.get_nowait()
                    
                    if msg_type == 'output':
                        # Log large chunks to debug streaming behavior
                        if len(data) > 100:
                            logging.debug(f"Large output chunk: {len(data)} chars")
                        # Process the output character by character
                        current_line = self._process_terminal_output(data, current_line)
                    elif msg_type == 'eof':
                        if current_line:
                            self._append_line(current_line)
                            current_line = ""
                        self._append_line("\n[yellow]Claude CLI session ended.[/yellow]")
                        self.status.update("Status: [yellow]Disconnected[/yellow]")
                        self.running = False
                    elif msg_type == 'error':
                        if current_line:
                            self._append_line(current_line)
                            current_line = ""
                        self._append_line(f"\n[red]Error: {data}[/red]")
                    elif msg_type == 'exit':
                        break
                        
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logging.error(f"Error processing output queue: {e}")
                
    def _process_terminal_output(self, data: str, current_line: str) -> str:
        """Process terminal output handling special characters and in-place updates."""
        # Enhanced ANSI escape sequence pattern to handle more cases
        ansi_escape = re.compile(r'''
            \x1B  # ESC
            (?:   # Start non-capturing group
                \[  # CSI sequences
                [0-9;]*  # Parameters
                [A-Za-z]  # Command
            |     # OR
                [()][B0UK]  # Character set sequences
            |     # OR
                [>=]  # Other single char sequences
            |     # OR
                \]  # OSC sequences
                [^\x07]*  # Until BEL
                \x07?  # Optional BEL
            )
        ''', re.VERBOSE)
        
        # Debug logging for terminal updates
        if '\r' in data and not '\n' in data:
            logging.debug(f"In-place update detected: {repr(data[:50])}")
            
        # Check if this looks like streaming text (no newlines, just content)
        if not '\n' in data and not '\r' in data and data.strip():
            # This is likely streaming content that should update the current line
            logging.debug(f"Streaming text detected: {repr(data[:30])}")
        
        i = 0
        while i < len(data):
            char = data[i]
            
            # Check for ANSI escape sequence
            if char == '\x1B' and i + 1 < len(data):
                # Skip the entire ANSI sequence
                match = ansi_escape.match(data[i:])
                if match:
                    seq = match.group(0)
                    # Handle some specific sequences
                    if seq == '\x1B[2K':  # Clear entire line
                        current_line = ""
                    elif seq == '\x1B[K':  # Clear to end of line
                        # Keep current line as is
                        pass
                    elif seq.endswith('A'):  # Cursor up
                        # For now, just skip
                        pass
                    i += len(seq)
                    continue
                    
            if char == '\r':  # Carriage return - move to beginning of line
                # For in-place updates, we need to update the last line
                if self.terminal_buffer and current_line:
                    # Update the last line with what we have so far
                    self.terminal_buffer[-1] = current_line
                    self._update_display()
                # Reset current line to start overwriting
                current_line = ""
            elif char == '\n':  # Newline
                # Complete the current line and start a new one
                # But only if we have content or this is a genuine newline
                if current_line or (i == 0 or data[i-1] != '\r'):
                    self._append_line(current_line)
                    current_line = ""
            elif char == '\b':  # Backspace
                if current_line:
                    current_line = current_line[:-1]
            elif ord(char) >= 32:  # Printable character
                current_line += char
                
            i += 1
                    
        # Update the display with current line progress
        # Always update if we have content, to handle streaming
        if current_line != "" or (self.terminal_buffer and data.endswith('\r')):
            if self.terminal_buffer and not data.endswith('\n'):
                # Update the last line in place for streaming content
                self.terminal_buffer[-1] = current_line
            elif current_line:
                # No buffer yet or ended with newline, add new line
                if not self.terminal_buffer or self.terminal_buffer[-1] != current_line:
                    self.terminal_buffer.append(current_line)
            self._update_display()
                
        return current_line
        
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude CLI."""
        if not self.claude_process or not self.claude_process.isalive():
            self._append_line("[red]Claude CLI is not running. Press Ctrl+R to restart.[/red]")
            return
            
        logging.info(f"Sending prompt: {prompt[:50]}... (mode: {mode})")
        
        # Add mode context if needed
        if mode.lower() == 'morph':
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            prompt += f"\n\n[IMPORTANT: Work on Claude Code Morph source at {morph_dir}]"
            
        # Display user prompt in our output (not sent to Claude)
        self._append_line(f"\n[bold cyan]>>> Sending prompt from panel[/bold cyan]")
        self.status.update("Status: [yellow]Processing...[/yellow]")
        
        try:
            # First clear any existing input line with Ctrl+U
            self.claude_process.send('\x15')  # Ctrl+U to clear line
            
            # Send the prompt text
            self.claude_process.send(prompt)
            
            # Auto-submit with Enter
            await asyncio.sleep(0.1)  # Small delay to ensure text is processed
            self.claude_process.send('\r')  # Send Enter to submit
            
            # Update status after a short delay
            await asyncio.sleep(0.5)
            self.status.update("Status: [green]Active[/green]")
            
            # Add to history
            self.conversation_history.append({"role": "user", "content": prompt})
            
        except Exception as e:
            self._append_line(f"[red]Error sending prompt: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Error sending prompt: {e}")
            
    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude CLI."""
        if self.claude_process and self.claude_process.isalive():
            try:
                self.claude_process.sendcontrol('c')
                self._append_line("\n[yellow]Sent interrupt (Ctrl+C)[/yellow]")
            except Exception as e:
                self._append_line(f"[red]Failed to interrupt: {e}[/red]")
                
    def action_send_eof(self) -> None:
        """Send EOF signal to Claude CLI."""
        if self.claude_process and self.claude_process.isalive():
            try:
                self.claude_process.sendeof()
                self._append_line("\n[yellow]Sent EOF (Ctrl+D)[/yellow]")
            except Exception as e:
                self._append_line(f"[red]Failed to send EOF: {e}[/red]")
                
    async def action_restart(self) -> None:
        """Restart the Claude CLI session."""
        # Stop current session
        self.running = False
        
        if self.claude_process:
            try:
                if self.claude_process.isalive():
                    self.claude_process.terminate(force=True)
            except:
                pass
            self.claude_process = None
            
        # Wait for reader thread to finish
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)
            
        # Clear output and history
        self.terminal_buffer.clear()
        self.conversation_history.clear()
        self._update_display()
        
        # Start new session
        self._append_line("[yellow]Restarting Claude CLI...[/yellow]")
        await self.start_claude_cli()
        
    def get_copyable_content(self) -> str:
        """Get copyable content."""
        # TODO: Implement proper text extraction from RichLog
        return ""
        
    def get_selected_content(self) -> Optional[str]:
        """Get selected content."""
        return None
        
    async def on_key(self, event: Key) -> None:
        """Handle keyboard input and send to Claude process."""
        if not self.claude_process or not self.claude_process.isalive():
            return
            
        # Check if this is an app-level binding we should let through
        app_bindings = {
            "ctrl+s",       # Save Workspace
            "ctrl+l",       # Load Workspace  
            "ctrl+q",       # Quit
            "ctrl+shift+f", # Safe Mode
            "f5",           # Reload All
        }
        
        if event.key in app_bindings:
            # Let the event bubble up to the app
            return
            
        # Get the key character or name
        key = event.key
        
        # Handle special keys
        if key == "up":
            self.claude_process.send('\x1b[A')  # Up arrow
        elif key == "down":
            self.claude_process.send('\x1b[B')  # Down arrow
        elif key == "left":
            self.claude_process.send('\x1b[D')  # Left arrow
        elif key == "right":
            self.claude_process.send('\x1b[C')  # Right arrow
        elif key == "home":
            self.claude_process.send('\x01')  # Ctrl+A (beginning of line)
        elif key == "end":
            self.claude_process.send('\x05')  # Ctrl+E (end of line)
        elif key == "backspace":
            self.claude_process.send('\x7f')  # Backspace
        elif key == "delete":
            self.claude_process.send('\x1b[3~')  # Delete
        elif key == "enter":
            self.claude_process.send('\r')  # Enter (carriage return)
        elif key == "tab":
            self.claude_process.send('\t')  # Tab
        elif key == "shift+tab":
            self.claude_process.send('\x1b[Z')  # Shift+Tab (reverse tab)
        elif key == "escape":
            self.claude_process.send('\x1b')  # Escape
        elif event.character and len(event.character) == 1:
            # Regular character - check it exists before sending
            self.claude_process.send(event.character)
            
        # Prevent event from bubbling up
        event.stop()
        
    def focus(self) -> None:
        """Focus the terminal panel."""
        super().focus()
        # Make sure we can receive keyboard input
        self.can_focus = True
        
    def _append_line(self, text: str) -> None:
        """Append a line to the terminal buffer."""
        self.terminal_buffer.append(text)
        if len(self.terminal_buffer) > self.max_lines:
            self.terminal_buffer.pop(0)
        self._update_display()
        
    def _update_display(self) -> None:
        """Update the terminal display with current buffer content."""
        # Safety check - make sure output widget exists
        if not hasattr(self, 'output') or not self.output:
            return
            
        # Get visible area (last N lines that fit in the widget)
        if hasattr(self.output, 'size') and self.output.size:
            visible_lines = self.output.size.height - 2  # Account for padding
            if visible_lines > 0:
                display_lines = self.terminal_buffer[-visible_lines:]
            else:
                display_lines = self.terminal_buffer
        else:
            display_lines = self.terminal_buffer
            
        # Join lines and update display
        content = '\n'.join(display_lines)
        try:
            self.output.update(content)
        except Exception as e:
            logging.error(f"Error updating display: {e}")
        
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self._append_line("[yellow]Starting Claude CLI...[/yellow]")
        self._append_line(f"[dim]Working directory: {os.getcwd()}[/dim]")
        
        # Start Claude CLI process
        await self.start_claude_cli()
        
        # Focus the terminal to receive keyboard input
        self.focus()
        
    async def on_unmount(self) -> None:
        """Clean up when panel is unmounted."""
        self.running = False
        
        if self.claude_process:
            try:
                if self.claude_process.isalive():
                    self.claude_process.terminate(force=True)
            except:
                pass
                
        # Wait for reader thread
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)
            
    def get_state(self) -> Dict[str, Any]:
        """Get current panel state for persistence.
        
        Returns:
            Dictionary containing panel state
        """
        return {
            'terminal_buffer': self.terminal_buffer.copy(),
            'conversation_history': self.conversation_history.copy(),
            'working_directory': os.getcwd(),
            'status': self.status.renderable if hasattr(self, 'status') else "Unknown"
        }
        
    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore panel state from saved data.
        
        Args:
            state: Dictionary containing saved panel state
        """
        # Restore terminal buffer
        if 'terminal_buffer' in state:
            self.terminal_buffer = state['terminal_buffer']
            self._update_display()
            
        # Restore conversation history
        if 'conversation_history' in state:
            self.conversation_history = state['conversation_history']
            
        # Change to saved working directory if different
        if 'working_directory' in state:
            saved_wd = state['working_directory']
            if saved_wd != os.getcwd() and os.path.exists(saved_wd):
                try:
                    os.chdir(saved_wd)
                    self._append_line(f"[yellow]Restored working directory: {saved_wd}[/yellow]")
                except Exception as e:
                    self._append_line(f"[red]Could not restore working directory: {e}[/red]")
                    
        # Show restoration info
        self._append_line("[green]Session restored from previous state[/green]")
        if self.terminal_buffer:
            self._append_line(f"[dim]Restored {len(self.terminal_buffer)} lines of history[/dim]")