"""Emulated Terminal Panel - Uses pyte for proper terminal emulation."""

import os
import asyncio
import pexpect
import pyte
import threading
import queue
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.binding import Binding
from textual.events import Key
import re

try:
    from .BasePanel import BasePanel
except ImportError:
    # Fallback for when module is loaded dynamically
    from claude_code_morph.panels.BasePanel import BasePanel


class EmulatedTerminalPanel(BasePanel):
    """Terminal panel with full Claude CLI interactivity using pyte terminal emulation."""
    
    CSS = BasePanel.CSS + """
    EmulatedTerminalPanel {
        layout: vertical;
        height: 100%;
        margin: 0;
        padding: 0;
    }
    
    EmulatedTerminalPanel:focus {
        border: none;
    }
    
    #emulated-terminal-container {
        layout: vertical;
        height: 100%;
        margin: 0;
        padding: 0;
    }
    
    #terminal-screen {
        height: 1fr;
        background: #0c0c0c;
        color: #f0f0f0;
        padding: 0 1;
        border: none;
        overflow-y: scroll;
        font-family: monospace;
        margin: 0;
    }
    
    #terminal-screen:focus {
        border: none;
    }
    
    #terminal-status {
        height: 1;
        background: #1a1a1a;
        color: #888888;
        padding: 0 1;
        margin: 0;
    }
    """
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+c", "interrupt", "Interrupt", show=False),
        Binding("ctrl+r", "restart", "New Session", show=False),
        Binding("ctrl+d", "send_eof", "Send EOF", show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the emulated terminal panel."""
        super().__init__(**kwargs)
        self.claude_process: Optional[pexpect.spawn] = None
        self.output_queue = queue.Queue()
        self.reader_thread: Optional[threading.Thread] = None
        self.running = False
        self.conversation_history = []
        self.can_focus = True
        self._is_processing = False  # Track if Claude is processing
        self._claude_started = False  # Track if Claude has shown initial prompt
        
        # Initialize pyte terminal emulator
        self.terminal_screen = pyte.Screen(120, 40)  # 120 columns, 40 rows
        self.terminal_stream = pyte.ByteStream(self.terminal_screen)
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        logging.debug("EmulatedTerminalPanel.compose_content called")
        with Vertical(id="emulated-terminal-container"):
            # Terminal screen display with scrolling
            self.screen_display = RichLog(
                highlight=False,
                markup=True,
                wrap=True,
                id="terminal-screen",
                auto_scroll=True
            )
            yield self.screen_display
            
            self.status = Static("Status: Initializing...", id="terminal-status")
            yield self.status
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self.screen_display.write("[yellow]Starting Claude CLI...[/yellow]")
        self.screen_display.write(f"[dim]Working directory: {os.getcwd()}[/dim]")
        
        # Start Claude CLI process
        await self.start_claude_cli()
        
        # Focus the panel to receive keyboard input
        self.focus()
        
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
            
            # Get the working directory - use current directory
            working_dir = os.getcwd()
            
            # Start Claude with pexpect
            self.claude_process = pexpect.spawn(
                cmd[0],
                args=cmd[1:],
                dimensions=(40, 120),
                env=env,
                timeout=None,
                echo=False,
                cwd=working_dir
            )
            
            logging.info(f"Started Claude CLI in directory: {working_dir}")
            
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
            logging.info(f"Claude CLI started successfully with terminal emulation")
            
            # After a short delay, assume Claude is ready if we haven't detected the prompt
            async def check_ready():
                await asyncio.sleep(3.0)
                if not self._claude_started:
                    logging.info("Claude startup timeout - assuming ready")
                    self._claude_started = True
                    self._is_processing = False
                    self.status.update("Status: [green]Ready[/green]")
            
            asyncio.create_task(check_ready())
            
        except Exception as e:
            self.screen_display.write(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}", exc_info=True)
            
    def _read_output_loop(self) -> None:
        """Read output from Claude process in a separate thread."""
        try:
            while self.running and self.claude_process and self.claude_process.isalive():
                try:
                    # Read raw bytes for terminal emulator
                    chunk = self.claude_process.read_nonblocking(size=4096, timeout=0.1)
                    if chunk:
                        # Convert to bytes if needed
                        if isinstance(chunk, str):
                            chunk = chunk.encode('utf-8')
                        self.output_queue.put(('output', chunk))
                except pexpect.TIMEOUT:
                    continue
                except pexpect.EOF:
                    self.output_queue.put(('eof', None))
                    break
                except Exception as e:
                    if self.running:
                        logging.error(f"Error reading from Claude: {e}")
                        self.output_queue.put(('error', str(e)))
                    break
                    
        except Exception as e:
            logging.error(f"Reader thread crashed: {e}")
        finally:
            self.running = False
            self.output_queue.put(('exit', None))
            
    async def _process_output_queue(self) -> None:
        """Process output from the queue and update the terminal emulator."""
        while self.running:
            try:
                if not self.output_queue.empty():
                    msg_type, data = self.output_queue.get_nowait()
                    
                    if msg_type == 'output':
                        # Feed data to terminal emulator
                        self.terminal_stream.feed(data)
                        # Update display
                        self._update_display()
                        
                        # Check if Claude is asking for confirmation
                        screen_text = self._get_screen_text()
                        if any(phrase in screen_text.lower() for phrase in ['(y/n)', 'continue?', 'proceed?', 'are you sure']):
                            logging.info("Detected confirmation prompt, auto-confirming...")
                            await asyncio.sleep(0.1)
                            self.claude_process.send('y\r')
                            
                        # Log all Claude output for debugging file operations
                        if isinstance(data, bytes):
                            text_data = data.decode('utf-8', errors='ignore')
                        else:
                            text_data = str(data)
                        if len(text_data) > 10:
                            # Reduce log spam - only log every 10th chunk
                            if not hasattr(self, '_chunk_count'):
                                self._chunk_count = 0
                            self._chunk_count += 1
                            if self._chunk_count % 10 == 0:
                                logging.debug(f"Claude output chunk #{self._chunk_count}: {repr(text_data[:50])}")
                    elif msg_type == 'eof':
                        self.screen_display.write("\n[yellow]Claude CLI session ended.[/yellow]")
                        self.status.update("Status: [yellow]Disconnected[/yellow]")
                        self.running = False
                    elif msg_type == 'error':
                        self.screen_display.write(f"\n[red]Error: {data}[/red]")
                    elif msg_type == 'exit':
                        break
                        
                await asyncio.sleep(0.01)
                
            except queue.Empty:
                await asyncio.sleep(0.01)
            except Exception as e:
                logging.error(f"Error processing output queue: {e}")
                
    def _get_screen_text(self) -> str:
        """Get the current screen content as text."""
        lines = []
        for y in range(self.terminal_screen.lines):
            line = ""
            for x in range(self.terminal_screen.columns):
                char = self.terminal_screen.buffer[y][x]
                line += char.data or " "
            lines.append(line.rstrip())
        return '\n'.join(lines)
        
    def _update_display(self) -> None:
        """Update the display with the current terminal screen content."""
        try:
            # Get the terminal screen as lines
            lines = []
            for y in range(self.terminal_screen.lines):
                line = ""
                for x in range(self.terminal_screen.columns):
                    char = self.terminal_screen.buffer[y][x]
                    line += char.data or " "
                # Strip trailing spaces but preserve content
                lines.append(line.rstrip())
            
            # Remove trailing empty lines
            while lines and not lines[-1]:
                lines.pop()
                
            # Clear and rewrite the display for pyte terminal emulation
            # This is necessary because pyte maintains the full screen state
            self.screen_display.clear()
            for line in lines:
                if line:  # Only write non-empty lines
                    self.screen_display.write(line)
                
            # Check if Claude is ready (showing prompt)
            if lines:
                # Check last few lines for prompt
                for i, line in enumerate(lines[-5:]):
                    line_text = line.strip()
                    # Log what we're seeing in the last lines
                    if i == 0:
                        logging.debug(f"Checking last 5 lines for prompt...")
                    logging.debug(f"  Line {i}: '{line_text[:50]}...'")
                    
                    # Claude shows "Human: " or just "Human:" when ready for input
                    # Also check for the prompt symbol ">"
                    if ("Human:" in line_text or 
                        line_text.endswith("Human:") or 
                        line_text == ">" or 
                        line_text.endswith(" >") or
                        (line_text == "" and i > 0 and lines[-5:][i-1].strip().endswith("Human:"))):
                        self._is_processing = False
                        self._claude_started = True
                        self.status.update("Status: [green]Ready[/green]")
                        logging.info(f"Claude is ready - found prompt indicator: '{line_text}'")
                        break
                    
            # Debug: Log if we see file operation messages (disabled to prevent log flooding)
            # content = '\n'.join(lines)
            # if any(phrase in content.lower() for phrase in ['created', 'updated', 'wrote', 'edit', 'file']):
            #     logging.debug(f"File operation detected in output: {content[-200:]}")
        except Exception as e:
            logging.error(f"Error updating display: {e}")
            
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude CLI."""
        if not self.claude_process or not self.claude_process.isalive():
            self.screen_display.write("[red]Claude CLI is not running. Press Ctrl+R to restart.[/red]")
            return
            
        logging.info(f"Sending prompt: {prompt[:50]}... (mode: {mode})")
        
        # Add mode context if needed
        if mode.lower() == 'morph':
            # Claude is already in the project root, just add context
            prompt = f"Please work on the Claude Code Morph source code in the current directory. {prompt}"
            logging.info(f"Morph mode: Working on Claude Code Morph source")
            
        self.status.update("Status: [yellow]Processing...[/yellow]")
        self._is_processing = True  # Mark as processing
        
        try:
            # Clear any existing input line with Ctrl+U
            self.claude_process.send('\x15')
            
            # Send the prompt text
            self.claude_process.send(prompt)
            
            # Auto-submit with Enter
            await asyncio.sleep(0.1)
            self.claude_process.send('\r')
            
            # Update status
            await asyncio.sleep(0.5)
            self.status.update("Status: [green]Active[/green]")
            
            # Add to history
            self.conversation_history.append({"role": "user", "content": prompt})
            
        except Exception as e:
            self.screen_display.update(f"[red]Error sending prompt: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Error sending prompt: {e}")
            
    def action_interrupt(self) -> None:
        """Send interrupt signal to Claude CLI."""
        if self.claude_process and self.claude_process.isalive():
            try:
                self.claude_process.sendcontrol('c')
                self.screen_display.write("\n[yellow]Sent interrupt (Ctrl+C)[/yellow]")
            except Exception as e:
                self.screen_display.write(f"[red]Failed to interrupt: {e}[/red]")
                
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
            
        # Wait for reader thread
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)
            
        # Clear screen
        self.terminal_screen.reset()
        self.conversation_history.clear()
        self._update_display()
        
        # Start new session
        self.screen_display.write("[yellow]Restarting Claude CLI...[/yellow]")
        await self.start_claude_cli()
        
    async def on_key(self, event: Key) -> None:
        """Handle keyboard input and send to Claude process."""
        if not self.claude_process or not self.claude_process.isalive():
            return
            
        # Get the key
        key = event.key
        
        # Handle special keys
        if key == "up":
            self.claude_process.send('\x1b[A')
        elif key == "down":
            self.claude_process.send('\x1b[B')
        elif key == "left":
            self.claude_process.send('\x1b[D')
        elif key == "right":
            self.claude_process.send('\x1b[C')
        elif key == "home":
            self.claude_process.send('\x01')
        elif key == "end":
            self.claude_process.send('\x05')
        elif key == "backspace":
            self.claude_process.send('\x7f')
        elif key == "delete":
            self.claude_process.send('\x1b[3~')
        elif key == "enter":
            self.claude_process.send('\r')
        elif key == "tab":
            self.claude_process.send('\t')
        elif key == "shift+tab":
            self.claude_process.send('\x1b[Z')
        elif key == "escape":
            self.claude_process.send('\x1b')
        elif event.character and len(event.character) == 1:
            self.claude_process.send(event.character)
            
        event.stop()
        
    def get_state(self) -> Dict[str, Any]:
        """Get current panel state for persistence."""
        # Get screen content as text
        lines = []
        for y in range(self.terminal_screen.lines):
            line = ""
            for x in range(self.terminal_screen.columns):
                char = self.terminal_screen.buffer[y][x]
                line += char.data or " "
            lines.append(line.rstrip())
            
        return {
            'screen_content': lines,
            'conversation_history': self.conversation_history.copy(),
            'working_directory': os.getcwd(),
            'status': self.status.renderable if hasattr(self, 'status') else "Unknown"
        }
        
    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore panel state from saved data."""
        # Note: We can't restore the exact terminal state, but we can show history
        if 'conversation_history' in state:
            self.conversation_history = state['conversation_history']
            
        if 'working_directory' in state:
            saved_wd = state['working_directory']
            if saved_wd != os.getcwd() and os.path.exists(saved_wd):
                try:
                    os.chdir(saved_wd)
                except Exception as e:
                    logging.error(f"Could not restore working directory: {e}")
                    
        self.screen_display.write("[green]Session restored[/green]")
        
    def is_claude_processing(self) -> bool:
        """Check if Claude is currently processing a request."""
        # If Claude hasn't started yet, it's considered "processing"
        if not self._claude_started:
            logging.debug(f"Claude not started yet, returning True")
            return True
        result = self._is_processing
        logging.debug(f"Claude processing state: {result}")
        return result
    
    async def on_unmount(self) -> None:
        """Clean up when panel is unmounted."""
        self.running = False
        
        if self.claude_process:
            try:
                if self.claude_process.isalive():
                    self.claude_process.terminate(force=True)
            except:
                pass
                
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)