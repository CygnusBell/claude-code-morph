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
from claude_code_sdk import query, ClaudeCodeOptions, AssistantMessage, TextBlock
import logging
from panels.BasePanel import BasePanel

class TerminalPanel(BasePanel):
    """Panel that interacts with Claude via the SDK."""
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("ctrl+k", "interrupt", "Interrupt"),
        Binding("ctrl+r", "restart", "Restart Session"),
    ]
    
    def __init__(self, **kwargs):
        """Initialize the terminal panel."""
        # Extract auto_start parameter if present (not used in SDK version)
        auto_start = kwargs.pop('auto_start', True)
        
        super().__init__(**kwargs)
        self._init_params = {}  # Store for hot-reloading
        self.current_task: Optional[asyncio.Task] = None
        self.conversation_history = []
        
    def compose(self) -> ComposeResult:
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
        logging.debug("TerminalPanel compose() called")
            
    async def on_mount(self) -> None:
        """Called when panel is mounted."""
        self.output.write("[yellow]Claude Terminal Ready![/yellow]")
        self.output.write(f"[dim]Working directory: {os.getcwd()}[/dim]")
        self.output.write("[green]Send a message using the prompt panel above.[/green]")
        
    async def send_prompt(self, prompt: str) -> None:
        """Send a prompt to Claude via SDK."""
        if self.current_task and not self.current_task.done():
            self.output.write("[red]Claude is still processing. Please wait...[/red]")
            return
            
        # Display the user prompt
        self.output.write(f"\n[bold blue]You:[/bold blue] {prompt}")
        self.status.update("Status: [yellow]Processing...[/yellow]")
        
        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        
        # Check if this is a "morph" command
        processed_prompt = self._process_morph_command(prompt)
        
        # Create the query task
        self.current_task = asyncio.create_task(self._query_claude(processed_prompt))
        
    def _process_morph_command(self, prompt: str) -> str:
        """Process morph commands to redirect to Claude Code Morph source.
        
        If the prompt contains 'morph' (case-insensitive), it will be modified
        to explicitly work on the Claude Code Morph source files.
        """
        # Check if "morph" appears in the prompt (case-insensitive)
        if 'morph' in prompt.lower():
            # Get the Claude Code Morph source directory
            morph_dir = Path(__file__).parent.parent.absolute()
            
            # Add context to the prompt
            morph_context = f"\n\n[IMPORTANT: This is a 'morph' command. Please work on the Claude Code Morph source files located at {morph_dir}, NOT the current working directory. The user wants to modify the IDE itself.]"
            
            # Log the morph command detection
            logging.info(f"Morph command detected: {prompt}")
            self.output.write("[dim italic]→ Morph command detected - targeting IDE source files[/dim italic]")
            
            return prompt + morph_context
        
        # Return unmodified prompt for regular commands
        return prompt
        
    async def _query_claude(self, prompt: str) -> None:
        """Query Claude and display the response."""
        try:
            self.output.write("\n[bold green]Claude:[/bold green] ")
            
            response_text = ""
            message_started = False
            
            # Determine the working directory based on whether this is a morph command
            morph_dir = str(Path(__file__).parent.parent.absolute())
            is_morph_command = "[IMPORTANT: This is a 'morph' command" in prompt
            working_dir = morph_dir if is_morph_command else os.getcwd()
            
            # Query Claude with streaming
            async for message in query(
                prompt=prompt,
                options=ClaudeCodeOptions(
                    max_turns=1,
                    cwd=working_dir,
                    system_prompt=f"You are Claude, helping with software development. The Claude Code Morph IDE source is at {morph_dir}. For 'morph' commands, work on the IDE source. For other commands, work in the user's current directory."
                )
            ):
                # Handle different message types
                if isinstance(message, AssistantMessage):
                    # Handle AssistantMessage with TextBlock content
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if not message_started:
                                message_started = True
                            self.output.write(block.text)
                            response_text += block.text
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
                    # Handle plain text responses
                    text = str(message)
                    if text.strip():
                        if not message_started:
                            message_started = True
                        self.output.write(text)
                        response_text += text
            
            # Add response to history
            if response_text:
                self.conversation_history.append({"role": "assistant", "content": response_text})
                
            # Ensure we end with a newline
            self.output.write("")
            
            # Update status based on whether it was a morph command
            if is_morph_command:
                self.status.update("Status: [green]Ready[/green] [dim](last: morph command)[/dim]")
            else:
                self.status.update("Status: [green]Ready[/green]")
            
        except Exception as e:
            import traceback
            self.output.write(f"\n[red]Error querying Claude: {str(e)}[/red]")
            self.output.write(f"[red]{traceback.format_exc()}[/red]")
            self.status.update("Status: [red]Error[/red]")
            logging.error(f"Error in _query_claude: {e}\n{traceback.format_exc()}")
        finally:
            self.current_task = None
            
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