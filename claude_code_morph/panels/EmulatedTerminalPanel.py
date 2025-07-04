"""Emulated Terminal Panel - Uses pyte for proper terminal emulation."""

import os
import asyncio
import pexpect
import pyte
import threading
import queue
import logging
import time
from typing import Optional, List, Dict, Any
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog, TextArea
from textual.binding import Binding
from textual.events import Key
import re

try:
    from .BasePanel import BasePanel
    from .BasePanel import CLIPBOARD_AVAILABLE
except ImportError:
    # Fallback for when module is loaded dynamically
    from claude_code_morph.panels.BasePanel import BasePanel
    from claude_code_morph.panels.BasePanel import CLIPBOARD_AVAILABLE


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
    
    EmulatedTerminalPanel TextArea {
        scrollbar-size: 1 1;
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
        padding: 1;
        border: none;
        margin: 0;
    }
    
    #terminal-screen:focus {
        border: none;
    }
    
    #terminal-screen .text-area--cursor {
        background: #f0f0f0;
        color: #0c0c0c;
    }
    
    #terminal-screen .text-area--selection {
        background: #4a4a4a;
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
        Binding("ctrl+shift+c", "copy_terminal", "Copy", show=False),
        Binding("ctrl+shift+v", "paste_terminal", "Paste", show=False),
    ]
    
    def __init__(self, working_dir: Optional[str] = None, **kwargs):
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
        self.working_dir = working_dir  # Store the working directory
        self.context_helper = None  # Will be set by app if context integration is available
        
        # Initialize pyte terminal emulator  
        self.terminal_columns = 120
        self.terminal_rows = 40
        self.terminal_screen = pyte.Screen(self.terminal_columns, self.terminal_rows)
        self.terminal_stream = pyte.ByteStream(self.terminal_screen)
        
        # Performance optimization: cache frequently accessed properties
        self._screen_lines = self.terminal_rows
        self._screen_columns = self.terminal_columns
        self._cached_screen_text = ""
        self._screen_dirty = True
        
    def compose_content(self) -> ComposeResult:
        """Create the terminal panel layout."""
        logging.debug("EmulatedTerminalPanel.compose_content called")
        try:
            with Vertical(id="emulated-terminal-container"):
                # Use TextArea for better selection support
                self.screen_display = TextArea(
                    "",
                    language=None,
                    theme="monokai",
                    id="terminal-screen",
                    read_only=True,
                    show_line_numbers=False,
                    tab_behavior="focus"
                )
                # Set can_focus after creation
                self.screen_display.can_focus = False
                # Store original write method
                self._textarea_set_text = self.screen_display.load_text
                # Add write method for compatibility
                self.screen_display.write = self._write_to_textarea
                yield self.screen_display
                
                self.status = Static("Status: Initializing...", id="terminal-status")
                yield self.status
        except Exception as e:
            logging.error(f"Error in compose_content: {e}", exc_info=True)
            # Fallback to simple static widget
            yield Static(f"Error creating terminal: {e}")
            
    def _write_to_textarea(self, text: str) -> None:
        """Write text to TextArea, appending to existing content."""
        # This is only used for initial messages, the real terminal content
        # comes from _update_display which uses the pyte screen
        pass  # We'll update the display through _update_display instead
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        logging.info("EmulatedTerminalPanel.on_mount called")
        try:
            # Show initial message
            self.screen_display.load_text("Starting Claude CLI...\n")
            working_dir = self.working_dir if self.working_dir else os.getcwd()
            self.screen_display.load_text(f"Starting Claude CLI...\nWorking directory: {working_dir}\n")
            
            # Start Claude CLI process
            await self.start_claude_cli()
            
            # Focus the panel to receive keyboard input
            self.focus()
        except Exception as e:
            logging.error(f"Error in EmulatedTerminalPanel.on_mount: {e}", exc_info=True)
            if hasattr(self, 'screen_display'):
                self.screen_display.load_text(f"Error starting terminal: {e}")
    
    def cleanup(self) -> None:
        """Clean up resources when panel is being destroyed."""
        logging.info("EmulatedTerminalPanel cleanup called")
        
        # Stop the reading thread
        self.running = False
        
        # Terminate the Claude process
        if self.claude_process:
            try:
                if self.claude_process.isalive():
                    # Send exit command first
                    try:
                        self.claude_process.sendline('/exit')
                        time.sleep(0.1)
                    except:
                        pass
                    
                    # Then terminate
                    self.claude_process.terminate(force=True)
                    self.claude_process = None
            except Exception as e:
                logging.error(f"Error terminating Claude process: {e}")
        
        # Wait for reader thread to finish
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.0)
            
        # Clear the output queue
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except:
                break
        
    async def start_claude_cli(self) -> None:
        """Start the Claude CLI process using pexpect."""
        try:
            # Set up environment
            env = os.environ.copy()
            env['TERM'] = 'xterm-256color'
            env['COLUMNS'] = str(self.terminal_columns)
            env['LINES'] = str(self.terminal_rows)
            
            # Build command with proper flags
            cmd = ['claude', '--dangerously-skip-permissions']
            
            # Get the working directory - use provided or current directory
            working_dir = self.working_dir if self.working_dir else os.getcwd()
            
            # Start Claude with pexpect
            self.claude_process = pexpect.spawn(
                cmd[0],
                args=cmd[1:],
                dimensions=(self.terminal_rows, self.terminal_columns),
                env=env,
                timeout=None,
                echo=False,
                cwd=working_dir
            )
            
            logging.info(f"Started Claude CLI in directory: {working_dir}")
            
            self.claude_process.delaybeforesend = 0
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
            
            # After a delay, assume Claude is ready if we haven't detected the prompt
            async def check_ready():
                await asyncio.sleep(5.0)  # Give Claude more time to show initial prompt
                if not self._claude_started:
                    logging.info("Claude startup timeout - assuming ready after 5 seconds")
                    self._claude_started = True
                    self._is_processing = False
                    self.status.update("Status: [green]Ready[/green]")
            
            asyncio.create_task(check_ready())
            
        except Exception as e:
            self.screen_display.write(f"[red]Failed to start Claude CLI: {e}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Failed to start Claude CLI: {e}", exc_info=True)
            
    def _read_output_loop(self) -> None:
        """Read output from Claude process in a separate thread with optimized batching."""
        consecutive_timeouts = 0
        max_consecutive_timeouts = 50  # Allow up to 5 seconds of no data before increasing timeout
        base_timeout = 0.01  # Start with very short timeout for responsiveness
        max_timeout = 0.5    # Max timeout when no data is available
        
        try:
            while self.running and self.claude_process and self.claude_process.isalive():
                batch_data = []
                batch_start_time = threading.Event()
                current_timeout = base_timeout
                
                # Adaptive timeout based on recent activity
                if consecutive_timeouts > max_consecutive_timeouts:
                    current_timeout = min(max_timeout, base_timeout * (consecutive_timeouts // 10))
                
                try:
                    # First read - use adaptive timeout
                    chunk = self.claude_process.read_nonblocking(size=8192, timeout=current_timeout)
                    if chunk:
                        consecutive_timeouts = 0  # Reset timeout counter on successful read
                        # Convert to bytes if needed
                        if isinstance(chunk, str):
                            chunk = chunk.encode('utf-8')
                        batch_data.append(chunk)
                        
                        # Try to read more data immediately if available (batching)
                        # This improves throughput when Claude is producing lots of output
                        batch_attempts = 0
                        max_batch_attempts = 10  # Limit batching to prevent blocking too long
                        
                        while batch_attempts < max_batch_attempts:
                            try:
                                # Very short timeout for batching additional data
                                extra_chunk = self.claude_process.read_nonblocking(size=8192, timeout=0.001)
                                if extra_chunk:
                                    if isinstance(extra_chunk, str):
                                        extra_chunk = extra_chunk.encode('utf-8')
                                    batch_data.append(extra_chunk)
                                    batch_attempts += 1
                                else:
                                    break
                            except pexpect.TIMEOUT:
                                break  # No more data available for batching
                            except (pexpect.EOF, Exception):
                                break  # Stop batching on errors
                        
                        # Send batched data as a single message
                        if len(batch_data) == 1:
                            self.output_queue.put(('output', batch_data[0]))
                        else:
                            # Combine multiple chunks for more efficient processing
                            combined_data = b''.join(batch_data)
                            self.output_queue.put(('output', combined_data))
                            
                            # Log batching efficiency for debugging
                            if len(batch_data) > 1:
                                logging.debug(f"Batched {len(batch_data)} chunks into {len(combined_data)} bytes")
                    
                except pexpect.TIMEOUT:
                    consecutive_timeouts += 1
                    continue
                except pexpect.EOF:
                    logging.info("Claude process ended (EOF)")
                    self.output_queue.put(('eof', None))
                    break
                except Exception as e:
                    if self.running:
                        # More robust error handling
                        if "Input/output error" in str(e) or "Bad file descriptor" in str(e):
                            logging.warning(f"Claude process likely terminated: {e}")
                            self.output_queue.put(('eof', None))
                            break
                        else:
                            logging.error(f"Error reading from Claude: {e}")
                            self.output_queue.put(('error', str(e)))
                            # Don't break immediately on non-fatal errors, try to recover
                            consecutive_timeouts += 1
                            if consecutive_timeouts > 100:  # Give up after too many errors
                                logging.error("Too many consecutive errors, terminating reader thread")
                                break
                    else:
                        break
                    
        except Exception as e:
            logging.error(f"Reader thread crashed: {e}", exc_info=True)
        finally:
            self.running = False
            self.output_queue.put(('exit', None))
            logging.info("Reader thread exiting")
            
    async def _process_output_queue(self) -> None:
        """Process output from the queue and update the terminal emulator."""
        while self.running:
            try:
                if not self.output_queue.empty():
                    msg_type, data = self.output_queue.get_nowait()
                    
                    if msg_type == 'output':
                        # Feed data to terminal emulator
                        self.terminal_stream.feed(data)
                        # Mark screen as dirty for next update
                        self._screen_dirty = True
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
                        
                await asyncio.sleep(0.005)
                
            except queue.Empty:
                await asyncio.sleep(0.005)
            except Exception as e:
                logging.error(f"Error processing output queue: {e}")
                
    def _get_screen_text(self) -> str:
        """Get the current screen content as text with optimized string operations."""
        # Use cached result if screen hasn't changed
        if not self._screen_dirty:
            return self._cached_screen_text
            
        # Pre-allocate list for better memory efficiency
        lines = [None] * self._screen_lines
        
        # Optimize by processing entire rows at once
        buffer = self.terminal_screen.buffer
        for y in range(self._screen_lines):
            # Extract character data with better handling of character types
            row = buffer[y]
            char_list = []
            for x in range(self._screen_columns):
                char = row.get(x)
                if char is not None:
                    # Handle different character data types properly
                    if hasattr(char, 'data') and char.data:
                        char_list.append(char.data)
                    else:
                        # Use space for empty or None characters
                        char_list.append(" ")
                else:
                    char_list.append(" ")
            # Don't rstrip() to preserve terminal formatting
            lines[y] = ''.join(char_list)
        
        # Cache the result
        self._cached_screen_text = '\n'.join(lines)
        self._screen_dirty = False
        return self._cached_screen_text
        
    def _update_display(self) -> None:
        """Update the display with optimized screen rendering."""
        try:
            # Mark screen as dirty for next _get_screen_text call
            self._screen_dirty = True
            
            # Use optimized screen text extraction
            screen_content = self._get_screen_text()
            
            # Update TextArea with the full screen content
            self.screen_display.load_text(screen_content)
            
            # Scroll to bottom
            self.screen_display.cursor_location = (self.screen_display.document.line_count - 1, 0)
            
            # Get lines for prompt detection
            lines = screen_content.split('\n')
            
            # Remove trailing empty lines efficiently
            while lines and not lines[-1]:
                lines.pop()
                
            # Optimize prompt detection by checking only last few lines
            if lines:
                # Only check last 5 lines for performance
                last_lines = lines[-5:] if len(lines) >= 5 else lines
                
                for i, line in enumerate(last_lines):
                    line_text = line.strip()
                    # Log what we're seeing in the last lines (only first line to reduce spam)
                    if i == 0:
                        logging.debug(f"Checking last {len(last_lines)} lines for prompt...")
                    logging.debug(f"  Line {i}: '{line_text[:50]}...'")
                    
                    # Pre-compiled prompt detection patterns for better performance
                    if self._is_claude_prompt(line_text, i, last_lines):
                        self._is_processing = False
                        self._claude_started = True
                        self.status.update("Status: [green]Ready[/green]")
                        logging.info(f"Claude is ready - found prompt indicator: '{line_text}'")
                        break
                    
        except Exception as e:
            logging.error(f"Error updating display: {e}")
            
    def _is_claude_prompt(self, line_text: str, line_index: int, last_lines: List[str]) -> bool:
        """Optimized Claude prompt detection."""
        # Claude shows "Human: " or just "Human:" when ready for input
        # Also check for the prompt symbol ">"
        if ("Human:" in line_text or 
            line_text.endswith("Human:") or 
            line_text == ">" or 
            line_text.endswith(" >")):
            return True
            
        # Check for empty line following Human: prompt
        if (line_text == "" and line_index > 0 and 
            line_index < len(last_lines) and 
            last_lines[line_index - 1].strip().endswith("Human:")):
            return True
            
        return False
            
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude CLI."""
        if not self.claude_process or not self.claude_process.isalive():
            self.screen_display.write("[red]Claude CLI is not running. Press Ctrl+R to restart.[/red]")
            return
            
        logging.info(f"Sending prompt: {prompt[:50]}... (mode: {mode})")
        
        # Enhance prompt with context if available
        if self.context_helper:
            prompt = self.context_helper.enhance_prompt_with_context(prompt, mode)
        
        # Add mode context if needed
        if mode.lower() == 'morph':
            # Get the morph source directory
            morph_dir = Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute()
            
            # Create a more explicit morph mode prompt
            morph_prompt = f"""[MORPH MODE ACTIVE]
You are now editing the Claude Code Morph IDE itself.
Source directory: {morph_dir}
Key files:
- Main app: {morph_dir}/main.py
- Panels: {morph_dir}/panels/
- Current panel: {morph_dir}/panels/EmulatedTerminalPanel.py

User request: {prompt}

Please make the requested changes to the Claude Code Morph source code."""
            
            prompt = morph_prompt
            logging.info(f"Morph mode: Working on Claude Code Morph source at {morph_dir}")
            
        self.status.update("Status: [yellow]Processing...[/yellow]")
        self._is_processing = True  # Mark as processing
        
        try:
            # Clear any existing input line with Ctrl+U
            self.claude_process.send('\x15')
            logging.debug("Sent Ctrl+U to clear input line")
            
            # Send the prompt text
            self.claude_process.send(prompt)
            logging.debug(f"Sent prompt text: {len(prompt)} characters")
            
            # Small delay to ensure text is fully processed before Enter
            await asyncio.sleep(0.1)
            
            # Auto-submit with Enter
            self.claude_process.send('\r')
            logging.debug("Sent Enter to submit prompt")
            
            # Update status immediately
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
            
        # Clear screen and reset cache
        self.terminal_screen.reset()
        self.conversation_history.clear()
        self._screen_dirty = True
        self._cached_screen_text = ""
        self._update_display()
        
        # Start new session
        self.screen_display.write("[yellow]Restarting Claude CLI...[/yellow]")
        await self.start_claude_cli()
        
    def action_send_eof(self) -> None:
        """Send EOF (Ctrl+D) to the terminal."""
        if self.claude_process and self.claude_process.isalive():
            try:
                self.claude_process.sendeof()
                logging.debug("Sent EOF to terminal")
            except Exception as e:
                logging.error(f"Failed to send EOF: {e}")
        
    # Optimized key mapping dictionary for fast lookups
    _KEY_MAP = {
        "up": '\x1b[A',
        "down": '\x1b[B', 
        "left": '\x1b[D',
        "right": '\x1b[C',
        "home": '\x01',
        "end": '\x05',
        "backspace": '\x7f',
        "delete": '\x1b[3~',
        "enter": '\r',
        "tab": '\t',
        "shift+tab": '\x1b[Z',
        "escape": '\x1b'
    }
    
    async def on_key(self, event: Key) -> None:
        """Handle keyboard input and send to Claude process with optimized performance."""
        # Check if screen_display exists
        if not hasattr(self, 'screen_display') or not self.screen_display:
            return
            
        # Only handle keys if this panel has focus (is visible and active)
        if not self.has_focus:
            logging.debug(f"EmulatedTerminalPanel: Ignoring key '{event.key}' - panel not focused")
            return
            
        # Handle escape key as a regular terminal input
        # No special focus handling needed since TextArea is always display-only
            
        # Handle copy shortcuts
        if event.key == "ctrl+shift+c":
            logging.info("EmulatedTerminalPanel: Handling Ctrl+Shift+C")
            self.action_copy_terminal()
            event.stop()
            return
        elif event.key == "ctrl+c" and hasattr(self, 'screen_display') and self.screen_display and hasattr(self.screen_display, 'selected_text') and self.screen_display.selected_text:
            # If there's selected text, copy it
            logging.info("EmulatedTerminalPanel: Handling Ctrl+C with selection")
            self.action_copy_terminal()
            event.stop()
            return
        elif event.key == "ctrl+shift+v":
            logging.info("EmulatedTerminalPanel: Handling Ctrl+Shift+V")
            asyncio.create_task(self.action_paste_terminal())
            event.stop()
            return
            
        # Handle selection keys - allow TextArea to handle them for text selection
        selection_keys = {
            "shift+up", "shift+down", "shift+left", "shift+right",
            "shift+home", "shift+end", "shift+pageup", "shift+pagedown",
            "ctrl+a",  # Select all
        }
        
        if event.key in selection_keys:
            # Allow selection keys to pass through to TextArea for text selection
            # Don't send these to Claude process - they're for UI interaction only
            # Don't stop the event so TextArea can handle selection
            return
            
        if not self.claude_process or not self.claude_process.isalive():
            return
            
        # Check if this is an app-level binding we should let through
        app_bindings = {
            "ctrl+s",       # Save Workspace
            "ctrl+l",       # Load Workspace  
            "ctrl+q",       # Quit
            "ctrl+shift+f", # Safe Mode
            "ctrl+t",       # Reload All
        }
        
        if event.key in app_bindings:
            # Let the event bubble up to the app
            logging.info(f"EmulatedTerminalPanel: Letting {event.key} bubble up to app")
            # Don't stop the event, just return to let it propagate
            return
            
        # TextArea is always display-only, no need to manage its focus
        # All input is handled by the Panel directly
            
        # Fast dictionary lookup for special keys
        key_sequence = self._KEY_MAP.get(event.key)
        if key_sequence:
            # Send special key sequences (including arrow keys) to Claude
            self.claude_process.send(key_sequence)
            logging.debug(f"Sent special key '{event.key}' as sequence '{repr(key_sequence)}' to Claude")
        elif event.character and len(event.character) == 1:
            # Direct character send for regular keys
            self.claude_process.send(event.character)
            logging.debug(f"Sent character '{event.character}' to Claude")
        else:
            # Log unhandled keys for debugging
            logging.debug(f"Unhandled key event: '{event.key}' (character: {repr(event.character)})")
            
        event.stop()
        
    def get_state(self) -> Dict[str, Any]:
        """Get current panel state for persistence with optimized screen access."""
        # Use optimized screen text extraction and split into lines
        screen_text = self._get_screen_text()
        lines = screen_text.split('\n')
            
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
            
    def on_mouse_down(self, event) -> None:
        """Handle mouse down for text selection without focus changes."""
        # Check if we have screen_display
        if not hasattr(self, 'screen_display') or not self.screen_display:
            return
            
        # TextArea remains display-only (can_focus=False) but can still handle mouse selection
        # Focus always stays on the Panel for keyboard input
        # Mouse selection works without changing focus
        pass
        
    def on_mouse_up(self, event) -> None:
        """Handle mouse up after selection."""
        # Keep focus for now to allow copying
        pass
        
    def get_copyable_content(self) -> str:
        """Get the terminal screen content for copying."""
        # If there's a selection in the TextArea, use that
        if hasattr(self, 'screen_display') and self.screen_display:
            if hasattr(self.screen_display, 'selected_text'):
                selection = self.screen_display.selected_text
                if selection:
                    return selection
            elif hasattr(self.screen_display, 'selection'):
                # Try to get text from selection
                start = self.screen_display.selection.start
                end = self.screen_display.selection.end
                if start != end:
                    text = self.screen_display.text
                    return text[start:end]
        # Otherwise return all content
        return self._get_screen_text()
        
    def get_selected_content(self) -> str:
        """Get selected content from terminal."""
        # Get selection from TextArea
        if hasattr(self, 'screen_display') and self.screen_display:
            if hasattr(self.screen_display, 'selected_text'):
                selection = self.screen_display.selected_text
                if selection:
                    return selection
            elif hasattr(self.screen_display, 'selection'):
                # Try to get text from selection
                start = self.screen_display.selection.start
                end = self.screen_display.selection.end
                if start != end:
                    text = self.screen_display.text
                    return text[start:end]
        # Fall back to all content
        return self.get_copyable_content()
        
    def action_copy_terminal(self) -> None:
        """Copy terminal content to clipboard."""
        try:
            content = self.get_copyable_content()
            if content:
                self._copy_to_clipboard(content)
                self.app.notify("Terminal content copied to clipboard", severity="information")
            else:
                self.app.notify("No content to copy", severity="warning")
        except Exception as e:
            logging.error(f"Error copying terminal content: {e}")
            self.app.notify(f"Copy failed: {str(e)}", severity="error")
            
    async def action_paste_terminal(self) -> None:
        """Paste clipboard content into terminal."""
        try:
            # Import clipboard functions from BasePanel
            from pathlib import Path
            clipboard_file = Path.home() / ".claude-code-morph" / "clipboard.txt"
            
            # Try to read from clipboard file first
            content = None
            if clipboard_file.exists():
                try:
                    content = clipboard_file.read_text()
                    logging.debug(f"Read {len(content)} characters from clipboard file")
                except Exception as e:
                    logging.warning(f"Could not read clipboard file: {e}")
                    
            # If no content from file, try system clipboard
            if not content:
                try:
                    if CLIPBOARD_AVAILABLE:
                        import pyperclip
                        content = pyperclip.paste()
                    else:
                        self.app.notify("Clipboard not available", severity="warning")
                        return
                except Exception as e:
                    logging.error(f"Could not read from system clipboard: {e}")
                    self.app.notify("Could not access clipboard", severity="error")
                    return
                    
            if content and self.claude_process and self.claude_process.isalive():
                # Send the pasted content to the terminal
                self.claude_process.send(content)
                self.app.notify(f"Pasted {len(content)} characters", severity="information")
            elif not self.claude_process or not self.claude_process.isalive():
                self.app.notify("Terminal not running", severity="warning")
            else:
                self.app.notify("No content to paste", severity="warning")
        except Exception as e:
            logging.error(f"Error pasting to terminal: {e}")
            self.app.notify(f"Paste failed: {str(e)}", severity="error")