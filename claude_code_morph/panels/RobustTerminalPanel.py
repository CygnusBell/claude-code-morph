"""Robust Terminal Panel - Full interactive Claude CLI experience using pexpect."""

import os
import asyncio
import pexpect
import threading
import queue
import logging
from typing import Optional, List
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.binding import Binding
from rich.text import Text
from textual.events import Key
import re

try:
    from .BasePanel import BasePanel
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from BasePanel import BasePanel


class RobustTerminalPanel(BasePanel):
    """Terminal panel with full Claude CLI interactivity using pexpect."""
    
    CSS = BasePanel.DEFAULT_CSS + """
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
        Binding("ctrl+c", "interrupt", "Interrupt"),
        Binding("ctrl+r", "restart", "New Session"),
        Binding("ctrl+d", "send_eof", "Send EOF"),
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
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        with Vertical():
            yield Static("🖥️ Claude Terminal (Interactive)", classes="panel-title")
            
            self.output = RichLog(
                highlight=False,
                markup=True,
                wrap=True,
                id="terminal-output",
                auto_scroll=True
            )
            yield self.output
            
            self.status = Static("Status: Initializing...", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self.output.write("[yellow]Starting Claude CLI...[/yellow]")
        self.output.write(f"[dim]Working directory: {os.getcwd()}[/dim]\n")
        
        # Start Claude CLI process
        await self.start_claude_cli()
        
    async def start_claude_cli(self) -> None:
        """Start the Claude CLI process using pexpect."""
        try:
            # Set up environment
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['COLUMNS'] = '120'
            env['LINES'] = '40'
            
            # Build command with proper flags
            cmd = ['claude']
            if os.environ.get("CLAUDE_SKIP_PERMISSIONS"):
                cmd.append('--dangerously-skip-permissions')
            
            # Start Claude with pexpect
            self.claude_process = pexpect.spawn(
                cmd[0],
                args=cmd[1:],
                encoding='utf-8',
                dimensions=(40, 120),
                env=env,
                timeout=None  # No timeout - Claude can take as long as needed
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
            
        except Exception as e:
            self.output.write(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}", exc_info=True)
            
    def _read_output_loop(self) -> None:
        """Read output from Claude process in a separate thread."""
        try:
            while self.running and self.claude_process and self.claude_process.isalive():
                try:
                    # Read with a small timeout to check running status
                    chunk = self.claude_process.read_nonblocking(size=4096, timeout=0.1)
                    if chunk:
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
        while self.running:
            try:
                # Check queue with short timeout
                if not self.output_queue.empty():
                    msg_type, data = self.output_queue.get_nowait()
                    
                    if msg_type == 'output':
                        # Clean and display output
                        cleaned = self._clean_output(data)
                        if cleaned:
                            self.output.write(cleaned)
                    elif msg_type == 'eof':
                        self.output.write("\n[yellow]Claude CLI session ended.[/yellow]")
                        self.status.update("Status: [yellow]Disconnected[/yellow]")
                        self.running = False
                    elif msg_type == 'error':
                        self.output.write(f"\n[red]Error: {data}[/red]")
                    elif msg_type == 'exit':
                        break
                        
                await asyncio.sleep(0.01)  # Small delay to prevent CPU spinning
                
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logging.error(f"Error processing output queue: {e}")
                
    def _clean_output(self, text: str) -> str:
        """Clean ANSI codes and format output for display."""
        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        cleaned = ansi_escape.sub('', text)
        
        # Handle carriage returns (line overwrites)
        lines = cleaned.split('\n')
        processed_lines = []
        
        for line in lines:
            if '\r' in line:
                # Take the last part after the last \r
                parts = line.split('\r')
                line = parts[-1] if parts[-1] else parts[-2] if len(parts) > 1 else ''
            
            # Skip empty lines that are just whitespace
            if line.strip():
                processed_lines.append(line)
                
        return '\n'.join(processed_lines) if processed_lines else ''
        
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude CLI."""
        if not self.claude_process or not self.claude_process.isalive():
            self.output.write("[red]Claude CLI is not running. Press Ctrl+R to restart.[/red]")
            return
            
        logging.info(f"Sending prompt: {prompt[:50]}... (mode: {mode})")
        
        # Add mode context if needed
        if mode.lower() == 'morph':
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            prompt += f"\n\n[IMPORTANT: Work on Claude Code Morph source at {morph_dir}]"
            
        # Display user prompt
        self.output.write(f"\n[bold cyan]You:[/bold cyan] {prompt}\n")
        self.status.update("Status: [yellow]Processing...[/yellow]")
        
        try:
            # Send the prompt to Claude
            self.claude_process.sendline(prompt)
            
            # Update status after a short delay
            await asyncio.sleep(0.5)
            self.status.update("Status: [green]Active[/green]")
            
            # Add to history
            self.conversation_history.append({"role": "user", "content": prompt})
            
        except Exception as e:
            self.output.write(f"[red]Error sending prompt: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Error sending prompt: {e}")
            
    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude CLI."""
        if self.claude_process and self.claude_process.isalive():
            try:
                self.claude_process.sendcontrol('c')
                self.output.write("\n[yellow]Sent interrupt (Ctrl+C)[/yellow]")
            except Exception as e:
                self.output.write(f"[red]Failed to interrupt: {e}[/red]")
                
    def action_send_eof(self) -> None:
        """Send EOF signal to Claude CLI."""
        if self.claude_process and self.claude_process.isalive():
            try:
                self.claude_process.sendeof()
                self.output.write("\n[yellow]Sent EOF (Ctrl+D)[/yellow]")
            except Exception as e:
                self.output.write(f"[red]Failed to send EOF: {e}[/red]")
                
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
        self.output.clear()
        self.conversation_history.clear()
        
        # Start new session
        self.output.write("[yellow]Restarting Claude CLI...[/yellow]\n")
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
            self.claude_process.send('\n')  # Enter
        elif key == "tab":
            self.claude_process.send('\t')  # Tab
        elif key == "escape":
            self.claude_process.send('\x1b')  # Escape
        elif len(event.character) == 1:
            # Regular character
            self.claude_process.send(event.character)
            
        # Prevent event from bubbling up
        event.stop()
        
    def focus(self) -> None:
        """Focus the terminal panel."""
        super().focus()
        # Make sure we can receive keyboard input
        self.can_focus = True
        
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self.output.write("[yellow]Starting Claude CLI...[/yellow]")
        self.output.write(f"[dim]Working directory: {os.getcwd()}[/dim]\n")
        
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