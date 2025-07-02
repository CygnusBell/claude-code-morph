"""Terminal Panel - Manages Claude interaction via SDK."""

import os
import asyncio
from typing import Optional
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static, RichLog
from textual.binding import Binding
from rich.text import Text
from rich.console import Console
from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock, SystemMessage, ToolUseBlock, ToolResultBlock, UserMessage, ResultMessage
import logging
from panels.BasePanel import BasePanel

class SDKTerminalPanel(BasePanel):
    """Panel that interacts with Claude via the SDK."""
    
    CSS = BasePanel.DEFAULT_CSS
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+k", "interrupt", "Interrupt", show=False),
        Binding("ctrl+r", "restart", "Restart Session", show=False),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the terminal panel."""
        # Extract auto_start parameter if present (not used in SDK version)
        auto_start = kwargs.pop('auto_start', True)
        
        super().__init__(**kwargs)
        self._init_params = {}  # Store for hot-reloading
        self.current_task: Optional[asyncio.Task] = None
        self.spinner_task: Optional[asyncio.Task] = None
        self.conversation_history = []
        self.spinner_frames = ["⣷", "⣯", "⣟", "⡿", "⢿", "⣻", "⣽", "⣾"]
        self.spinner_index = 0
        
    def compose_content(self) -> ComposeResult:
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
            self.status = Static("Status: Ready", id="terminal-status")
            yield self.status
            
        # Debug output
        logging.debug("TerminalPanel compose_content() called")
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self.output.write("[yellow]Claude Terminal Ready![/yellow]")
        self.output.write(f"[dim]Working directory: {os.getcwd()}[/dim]")
        self.output.write("[green]Send a message using the prompt panel above.[/green]")
        
    async def send_prompt(self, prompt: str, mode: str = "develop") -> None:
        """Send a prompt to Claude via SDK.
        
        Args:
            prompt: The user's prompt
            mode: Either 'develop' or 'morph'
        """
        logging.info(f"send_prompt called with: {prompt[:100]}... mode={mode}")
        
        if self.current_task and not self.current_task.done():
            self.output.write("[red]Claude is still processing. Please wait...[/red]")
            return
            
        # Display the user prompt
        self.output.write(f"\n[bold blue]You:[/bold blue] {prompt}")
        self.status.update("Status: [yellow]Processing... ⣾[/yellow]")
        logging.info("User prompt displayed, status updated")
        
        # Start spinner animation
        self._start_spinner()
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        
        # Process based on mode
        processed_prompt = self._process_prompt_with_mode(prompt, mode)
        
        # Create the query task
        self.current_task = asyncio.create_task(self._query_claude(processed_prompt))
        
    def _start_spinner(self) -> None:
        """Start the spinner animation."""
        if self.spinner_task and not self.spinner_task.done():
            self.spinner_task.cancel()
        self.spinner_task = asyncio.create_task(self._animate_spinner())
    
    def _stop_spinner(self) -> None:
        """Stop the spinner animation."""
        if self.spinner_task and not self.spinner_task.done():
            self.spinner_task.cancel()
            self.spinner_task = None
    
    async def _animate_spinner(self) -> None:
        """Animate the spinner in the status bar."""
        try:
            while True:
                frame = self.spinner_frames[self.spinner_index]
                self.status.update(f"Status: [yellow]Processing... {frame}[/yellow]")
                self.spinner_index = (self.spinner_index + 1) % len(self.spinner_frames)
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.debug(f"Spinner animation error: {e}")
    
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
            self.output.write("[dim italic]→ Morph mode - targeting IDE source files[/dim italic]")
            
            return prompt + morph_context
        
        # For develop mode, return unmodified prompt
        logging.info(f"Develop mode active for: {prompt}")
        return prompt
        
    async def _query_claude(self, prompt: str) -> None:
        """Query Claude and display the response."""
        try:
            self.output.write("\n[bold green]Claude:[/bold green] ")
            
            response_text = ""
            message_started = False
            message_count = 0
            
            # Determine the working directory based on whether this is a morph mode command
            morph_dir = str(Path(os.environ.get("MORPH_SOURCE_DIR", Path(__file__).parent.parent)).absolute())
            is_morph_mode = "[IMPORTANT: This is a 'morph' mode command" in prompt
            # For morph mode, use morph source dir; otherwise use user's working dir
            user_cwd = os.environ.get("MORPH_USER_CWD", os.getcwd())
            working_dir = morph_dir if is_morph_mode else user_cwd
            
            # Query Claude with streaming
            logging.info(f"Starting query with prompt: {prompt[:100]}...")
            logging.info(f"Working directory: {working_dir}")
            
            # Note: Removed status update task to avoid TaskGroup errors
            # TODO: Find a better way to show progress without causing stream interruptions
            
            try:
                async for message in query(
                    prompt=prompt,
                    options=ClaudeCodeOptions(
                        max_turns=50,  # High limit for complex tasks
                        cwd=working_dir,
                        system_prompt=f"You are Claude, helping with software development. The Claude Code Morph IDE source is at {morph_dir}. For 'morph' commands, work on the IDE source. For other commands, work in the user's current directory."
                    )
                ):
                message_count += 1
                logging.debug(f"Received message #{message_count} type: {type(message).__name__}")
                
                # Skip SystemMessage - it's just metadata
                if isinstance(message, SystemMessage):
                    logging.debug("Skipping SystemMessage")
                    continue
                    
                # Skip ResultMessage - it's just summary info
                if hasattr(message.__class__, '__name__') and message.__class__.__name__ == 'ResultMessage':
                    logging.debug(f"Skipping ResultMessage: {message}")
                    continue
                
                # Handle different message types
                if isinstance(message, AssistantMessage):
                    logging.info(f"Processing AssistantMessage with {len(message.content)} blocks")
                    # Handle AssistantMessage with TextBlock content
                    for i, block in enumerate(message.content):
                        logging.debug(f"Block {i}: type={type(block).__name__}")
                        if isinstance(block, TextBlock):
                            if not message_started:
                                message_started = True
                            logging.info(f"Writing text block: {block.text[:50]}...")
                            # Write text and ensure it displays immediately
                            self.output.write(block.text)
                            response_text += block.text
                            # Don't refresh too often to avoid stream interruptions
                            await asyncio.sleep(0)  # Yield control to allow UI update
                        elif isinstance(block, ToolUseBlock):
                            # Handle tool use blocks
                            if not message_started:
                                message_started = True
                            tool_info = f"\n[dim]→ Using tool: {block.name}[/dim]\n"
                            self.output.write(tool_info)
                            response_text += tool_info
                            logging.info(f"Tool use: {block.name} with id {block.id}")
                            # Don't refresh too often to avoid stream interruptions
                            await asyncio.sleep(0)
                        else:
                            # Log unexpected block types
                            logging.warning(f"Unexpected block type in AssistantMessage: {type(block).__name__}")
                elif isinstance(message, UserMessage):
                    # Handle UserMessage (tool responses)
                    logging.info(f"Processing UserMessage")
                    # UserMessage.content can be either string or list
                    if message.content:
                        if not message_started:
                            message_started = True
                        
                        # Handle both string and list content
                        if isinstance(message.content, str):
                            self.output.write(f"[dim]{message.content}[/dim]\n")
                            response_text += message.content
                        elif isinstance(message.content, list):
                            # Handle list of content blocks (tool results)
                            for block in message.content:
                                if isinstance(block, ToolResultBlock):
                                    if block.content:
                                        content_str = str(block.content)
                                        self.output.write(f"[dim]{content_str}[/dim]\n")
                                        response_text += content_str + "\n"
                                else:
                                    # Fallback for other block types
                                    block_str = str(block)
                                    self.output.write(f"[dim]{block_str}[/dim]\n")
                                    response_text += block_str + "\n"
                elif isinstance(message, dict):
                    # Handle legacy dict format
                    if message.get("type") == "text":
                        content = message.get("content", "")
                        if content:
                            if not message_started:
                                message_started = True
                            self.output.write(content)
                            response_text += content
                    elif message.get("type") == "error":
                        self.output.write(f"\n[red]Error: {message.get('error', 'Unknown error')}[/red]")
                        self.status.update("Status: [red]Error[/red]")
                        return
                else:
                    # Handle plain text responses or unknown message types
                    text = str(message)
                    # Debug: Log the message type to understand what we're receiving
                    logging.warning(f"Unknown message type: {type(message).__name__} - content: {text[:100]}...")
                    if text.strip() and not text.startswith("SystemMessage"):
                        if not message_started:
                            message_started = True
                        self.output.write(text)
                        response_text += text
            except Exception as stream_error:
                # Log the specific streaming error
                logging.error(f"Error during message streaming: {stream_error}")
                if "unhandled errors in a TaskGroup" in str(stream_error):
                    self.output.write(f"\n[yellow]Note: Response processing completed with some warnings.[/yellow]")
                else:
                    raise
            
            # Log summary
            logging.info(f"Query complete. Messages received: {message_count}, Response length: {len(response_text)}")
            
            # Add response to history
            if response_text:
                self.conversation_history.append({"role": "assistant", "content": response_text})
            else:
                self.output.write("[dim italic](No response received)[/dim italic]")
                
            # Ensure we end with a newline
            self.output.write("")
            
            # Stop spinner
            self._stop_spinner()
            
            # Update status based on whether it was a morph mode command
            if is_morph_mode:
                self.status.update("Status: [green]Ready[/green] [dim](last: morph mode)[/dim]")
            else:
                self.status.update("Status: [green]Ready[/green]")
            
        except asyncio.CancelledError:
            # Task was cancelled, this is expected
            raise
        except Exception as e:
            import traceback
            error_msg = str(e)
            
            # Check for specific errors
            if "JSONDecodeError" in error_msg:
                self.output.write(f"\n[yellow]Claude is processing a complex response. This may take a moment...[/yellow]")
                logging.warning(f"JSON decode error (likely due to streaming): {error_msg}")
            elif "response stream interrupted" in error_msg.lower() or "unhandled errors in a TaskGroup" in error_msg or "cancel scope" in error_msg:
                # This often happens when the stream is interrupted or there's a concurrency issue
                self.output.write(f"\n[yellow]⚠ Response stream interrupted[/yellow]")
                self.output.write(f"\n[dim]Note: Claude may have completed some actions. Check for any changes.[/dim]")
                logging.warning(f"Stream/concurrency error: {error_msg[:200]}...")
                # Don't log full traceback for known stream issues
            else:
                self.output.write(f"\n[red]Error querying Claude: {error_msg}[/red]")
                self.output.write(f"\n[dim]Check main.log for details[/dim]")
                logging.error(f"Error in _query_claude: {e}\n{traceback.format_exc()}")
                
            self.status.update("Status: [yellow]Partial response[/yellow]")
        finally:
            self._stop_spinner()
            self.current_task = None
    
    async def _update_status_periodically(self):
        """Update status periodically during long operations."""
        dots = 0
        try:
            while True:
                await asyncio.sleep(1)
                dots = (dots + 1) % 4
                status_text = "Status: [yellow]Processing" + "." * dots + " " * (3 - dots) + "[/yellow]"
                self.status.update(status_text)
        except asyncio.CancelledError:
            # This is expected when the task is cancelled
            raise
        except Exception as e:
            # Log but don't crash
            logging.debug(f"Status update task error: {e}")
            
    def action_interrupt(self) -> None:
        """Interrupt current Claude query."""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            self.output.write("\n[yellow]Query interrupted![/yellow]")
            self.status.update("Status: [yellow]Interrupted[/yellow]")
            self.current_task = None
        else:
            self.output.write("[yellow]No active query to interrupt.[/yellow]")
            
    def action_restart(self) -> None:
        """Restart the conversation."""
        # Cancel any active task
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            
        # Clear conversation history
        self.conversation_history.clear()
        
        # Clear output
        self.output.clear()
        self.output.write("[yellow]Conversation restarted![/yellow]")
        self.output.write(f"[dim]Working directory: {os.getcwd()}[/dim]")
        self.output.write("[green]Send a message using the prompt panel above.[/green]")
        self.status.update("Status: [green]Ready[/green]")
    
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel."""
        try:
            if hasattr(self, 'output') and self.output:
                # RichLog doesn't have a direct way to get all text
                # For now, return empty string to avoid crashes
                # TODO: Implement proper text extraction from RichLog
                return "Terminal output (copy not yet implemented)"
        except Exception as e:
            logging.error(f"Error in TerminalPanel.get_copyable_content: {e}")
        return ""
    
    def get_selected_content(self) -> Optional[str]:
        """Get currently selected content."""
        # RichLog doesn't have built-in selection, so return None
        # Users can use Ctrl+Shift+C to copy all
        return None