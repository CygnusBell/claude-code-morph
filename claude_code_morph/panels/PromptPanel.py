"""Prompt Panel - Handles user input and prompt optimization."""

import os
import logging
from typing import Optional, Callable
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center, Middle, Grid
from textual.widgets import Static, TextArea, Button, Label, Select
from textual.reactive import reactive
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.events import Click
from rich.panel import Panel
from rich.syntax import Syntax
import asyncio
from panels.BasePanel import BasePanel

# Import AI libraries conditionally
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

class PromptPanel(BasePanel):
    """Panel for composing and optimizing prompts."""
    
    BINDINGS = BasePanel.BINDINGS + [
        Binding("cmd+a", "select_all_in_panel", "Select All", priority=True, show=False),
    ]
    
    CSS = BasePanel.DEFAULT_CSS + """
    PromptPanel {
        layout: vertical;
        height: 100%;
    }
    
    PromptPanel > Vertical {
        height: 100%;
        width: 100%;
    }
    
    PromptPanel .panel-title {
        height: 3;
        padding: 1;
        text-align: center;
        background: $primary;
    }
    
    PromptPanel #prompt-input {
        height: 1fr;
        min-height: 10;
        margin: 1;
        background: $surface;
    }
    
    PromptPanel .controls-container {
        layout: vertical;
        height: auto;
        min-height: 3;
        margin: 0;
        padding: 0 1;
        background: $panel;
    }
    
    PromptPanel .button-controls {
        height: 3;
        layout: horizontal;
        align: center stretch;
    }
    
    PromptPanel Select {
        width: 15;
        margin: 0 1;
    }
    
    PromptPanel #submit-btn {
        margin-left: 2;
    }
    
    # Clickable text buttons
    PromptPanel .clickable {
        padding: 0 1;
        margin: 0 1;
        background: $panel;
        color: $text;
    }
    
    PromptPanel .clickable:hover {
        background: $primary;
        color: $text;
    }
    
    PromptPanel .selected {
        background: $primary;
        color: $text;
        text-style: bold;
    }
    
    PromptPanel Button {
        min-width: 8;
        width: auto;
        height: 1;
        margin: 0 0.25;
        padding: 0;
        content-align: center middle;
        text-align: center;
    }
    
    PromptPanel Button#clear-btn, PromptPanel .clear-button {
        background: red !important;
        color: white !important;
        border: solid darkred !important;
        content-align: center middle;
        text-align: center;
    }
    
    PromptPanel #submit-btn {
        background: green;
        color: black;
    }
    """
    
    DEFAULT_STYLES = [
        ("verbose", "Detailed and comprehensive instructions"),
        ("concise", "Brief and to-the-point"),
        ("debugger", "Focus on debugging and error analysis"),
        ("architect", "High-level design and architecture"),
        ("refactor", "Code improvement and optimization"),
    ]
    
    def __init__(self, on_submit: Optional[Callable] = None, **kwargs):
        """Initialize the prompt panel.
        
        Args:
            on_submit: Callback function to handle submitted prompts
        """
        super().__init__(**kwargs)
        # Don't store the actual callback in _init_params as it can't be serialized
        self._init_params = {}  # Store for hot-reloading
        self.on_submit = on_submit
        self.prompt_history = []
        self.history_index = -1
        
        # Debug: Log CSS loading
        logging.info("PromptPanel CSS styles loading...")
        logging.info(f"CSS Hash: {hash(self.CSS)}")
        logging.debug(f"PromptPanel initialized with on_submit={on_submit}")
        
        # State that should survive hot-reload
        self._preserved_state = {
            'selected_style': 'verbose',
            'selected_mode': 'develop',
            'prompt_text': '',
            'prompt_history': [],
            'history_index': -1
        }
        
    def compose_content(self) -> ComposeResult:
        """Create the panel layout."""
        # Initialize values if not already set
        if not hasattr(self, 'selected_style'):
            self.selected_style = "verbose"
        if not hasattr(self, 'selected_mode'):
            self.selected_mode = "develop"
        
        # Title
        yield Static("📝 Prompt Generator", classes="panel-title")
        
        # Prompt input area
        self.prompt_input = TextArea(id="prompt-input")
        yield self.prompt_input
        
        # Debug: Log composition
        logging.debug("Creating controls container")
        
        # Controls with 3 dropdowns and action buttons
        with Horizontal(classes="button-controls"):
            # Style dropdown
            self.style_select = Select(
                [
                    ("verbose", "Verbose"),
                    ("concise", "Concise"),
                    ("debugger", "Debugger"),
                    ("architect", "Architect"),
                    ("refactor", "Refactor"),
                ],
                id="style-select",
            )
            yield self.style_select
            
            # Mode dropdown
            self.mode_select = Select(
                [
                    ("develop", "Develop"),
                    ("morph", "Morph"),
                ],
                id="mode-select",
            )
            yield self.mode_select
            
            # Action buttons
            yield Button("Submit", variant="primary", id="submit-btn")
            yield Button("Improve", variant="default", id="optimize-btn")
            yield Button("Clear", id="clear-btn")
    
            
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "submit-btn":
            self.submit_prompt()
        elif button_id == "optimize-btn":
            self.optimize_prompt()
        elif button_id == "clear-btn":
            self.clear_prompt()
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle dropdown selection changes."""
        # Get the actual value from the selection
        if event.value == Select.BLANK:
            return  # No selection
            
        if event.select.id == "style-select" and event.value is not None:
            # The value is the tuple, we want the first element
            self.selected_style = event.value
            self.app.notify(f"Style: {self.selected_style.capitalize()}", severity="information")
        elif event.select.id == "mode-select" and event.value is not None:
            self.selected_mode = event.value
            mode_desc = "IDE development" if self.selected_mode == "morph" else "Project development"
            self.app.notify(f"Mode: {mode_desc}", severity="information")
    
    
            
    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "ctrl+enter":
            self.submit_prompt()
        elif event.key == "ctrl+o":
            self.optimize_prompt()
        elif event.key == "ctrl+l":
            self.clear_prompt()
        elif event.key == "ctrl+up":
            self.navigate_history(-1)
        elif event.key == "ctrl+down":
            self.navigate_history(1)
            
    def submit_prompt(self) -> None:
        """Submit the current prompt."""
        prompt = self.prompt_input.text.strip()
        
        if not prompt:
            self.app.notify("Please enter a prompt", severity="warning")
            return
            
        # Add to history
        self.prompt_history.append(prompt)
        self.history_index = len(self.prompt_history)
        
        # Use the prompt directly
        final_prompt = prompt
        
        # Call submit handler with mode
        mode = getattr(self, 'selected_mode', 'develop')
        if self.on_submit:
            # Run async callback with mode
            task = asyncio.create_task(self._async_submit(final_prompt, mode))
            task.add_done_callback(self._handle_task_error)
        else:
            # Notify terminal panel directly with mode
            asyncio.create_task(self._send_to_terminal(final_prompt, mode))
            
        # Clear input
        self.prompt_input.text = ""
        
    async def _async_submit(self, prompt: str, mode: str) -> None:
        """Handle async submission."""
        await self.on_submit(prompt, mode)
        
    async def _send_to_terminal(self, prompt: str, mode: str) -> None:
        """Send prompt to terminal panel."""
        # Find terminal panel
        terminal = None
        for panel in self.app.panels.values():
            if panel.__class__.__name__ == "TerminalPanel":
                terminal = panel
                break
                
        if terminal and hasattr(terminal, 'send_prompt'):
            await terminal.send_prompt(prompt, mode)
        else:
            self.app.notify("Terminal panel not found", severity="error")
            
    def optimize_prompt(self) -> None:
        """Optimize the current prompt using AI."""
        prompt = self.prompt_input.text.strip()
        
        if not prompt:
            self.app.notify("Please enter a prompt to optimize", severity="warning")
            return
            
        # Get selected style
        style = getattr(self, 'selected_style', 'verbose')
        
        # Run optimization in background
        task = asyncio.create_task(self._optimize_prompt_async(prompt, style))
        task.add_done_callback(self._handle_task_error)
        
    async def _optimize_prompt_async(self, prompt: str, style: str) -> None:
        """Optimize prompt asynchronously and submit."""
        self.app.notify("Improving prompt...", severity="information")
        
        try:
            optimized = await self._call_optimizer(prompt, style)
            self.app.notify("Prompt improved!", severity="success")
            
            # Submit the optimized prompt directly with current mode
            mode = getattr(self, 'selected_mode', 'develop')
            if self.on_submit:
                await self._async_submit(optimized, mode)
            else:
                await self._send_to_terminal(optimized, mode)
                
            # Clear input after submission
            self.prompt_input.text = ""
        except Exception as e:
            self.app.notify(f"Optimization failed: {e}", severity="error")
            
    async def _call_optimizer(self, prompt: str, style: str) -> str:
        """Call AI optimizer to enhance the prompt."""
        # Get style description
        style_desc = dict(self.DEFAULT_STYLES).get(style, "")
        
        system_prompt = f"""You are a developer assistant that rewrites vague prompts into precise, Claude-friendly instructions.
Your task is to enhance prompts with a {style} style: {style_desc}

Guidelines:
- Preserve the original intent
- Make instructions clear and actionable
- Add specific technical details where helpful
- Format for immediate execution
- Keep the enhanced prompt focused and well-structured

Output only the enhanced prompt, nothing else."""

        user_message = f"Enhance this prompt:\n\n{prompt}"
        
        # Try Groq first
        if GROQ_AVAILABLE and os.getenv("GROQ_API_KEY"):
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=1000
            )
            return response.choices[0].message.content
            
        # Try Anthropic
        elif ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
            client = anthropic.AsyncAnthropic()
            response = await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            return response.content[0].text
            
        # Try OpenAI
        elif OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            client = openai.AsyncOpenAI()
            response = await client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
            )
            return response.choices[0].message.content
            
        else:
            # Fallback: Simple enhancement
            return self._simple_enhance(prompt, style)
            
    def _simple_enhance(self, prompt: str, style: str) -> str:
        """Simple prompt enhancement without AI."""
        # Add style-specific prefix
        prefixes = {
            "verbose": "Please provide a detailed implementation for the following:\n\n",
            "concise": "Task: ",
            "debugger": "Debug and analyze the following:\n\n",
            "architect": "Design and architect a solution for:\n\n",
            "refactor": "Refactor and optimize the following:\n\n",
        }
        
        prefix = prefixes.get(style, "")
        
        # Add some structure
        enhanced = f"{prefix}{prompt}"
        
        if style == "verbose":
            enhanced += "\n\nPlease include:\n- Step-by-step implementation\n- Error handling\n- Code comments\n- Usage examples"
        elif style == "debugger":
            enhanced += "\n\nFocus on:\n- Identifying issues\n- Root cause analysis\n- Suggested fixes\n- Prevention strategies"
            
        return enhanced
        
    def clear_prompt(self) -> None:
        """Clear prompt area with confirmation."""
        # Check if there's any content to clear
        if self.prompt_input.text.strip():
            # For simplicity, just clear with a notification
            self.prompt_input.text = ""
            self.app.notify("Prompt cleared", severity="information")
        else:
            self.app.notify("Nothing to clear", severity="information")
    
    
    async def _confirm_clear(self) -> None:
        """Show confirmation dialog for clearing."""
        
        class ConfirmDialog(ModalScreen):
            """Modal dialog for confirmation."""
            
            def compose(self):
                with Center():
                    with Middle():
                        with Vertical(id="dialog"):
                            yield Label("Clear all text?", id="question")
                            with Horizontal(id="buttons"):
                                yield Button("Yes", variant="warning", id="yes")
                                yield Button("No", variant="primary", id="no")
            
            def on_button_pressed(self, event: Button.Pressed) -> None:
                self.dismiss(event.button.id == "yes")
        
        # Show dialog and wait for result
        result = await self.app.push_screen(ConfirmDialog(), wait_for_dismiss=False)
        if await result:
            # User confirmed - clear the prompt
            self.prompt_input.text = ""
            self.app.notify("Prompt cleared", severity="information")
        
    def navigate_history(self, direction: int) -> None:
        """Navigate through prompt history."""
        if not self.prompt_history:
            return
            
        self.history_index = max(0, min(len(self.prompt_history) - 1, 
                                       self.history_index + direction))
        
        if 0 <= self.history_index < len(self.prompt_history):
            self.prompt_input.text = self.prompt_history[self.history_index]
    
    def get_copyable_content(self) -> str:
        """Get the content that can be copied from this panel."""
        # Return the current prompt text
        return self.prompt_input.text if hasattr(self, 'prompt_input') else ""
    
    def on_focus(self, event) -> None:
        """Handle focus event to ensure copy shortcuts work."""
        # Make sure our bindings are active when focused
        pass
    
    def _handle_task_error(self, task: asyncio.Task) -> None:
        """Handle errors from async tasks."""
        try:
            task.result()
        except Exception as e:
            self.app.notify(f"Error: {str(e)}", severity="error")
            logging.error(f"Task error: {e}", exc_info=True)
    
    def action_select_all_in_panel(self) -> None:
        """Select all text in the prompt input."""
        if hasattr(self, 'prompt_input'):
            # Focus the text area first
            self.prompt_input.focus()
            # Select all text in the TextArea
            if hasattr(self.prompt_input, 'select_all'):
                self.prompt_input.select_all()
            else:
                # Fallback: set cursor to beginning and selection to end
                self.prompt_input.cursor_location = (0, 0)
                if self.prompt_input.text:
                    lines = self.prompt_input.text.split('\n')
                    last_line = len(lines) - 1
                    last_col = len(lines[-1])
                    # Try to select from start to end
                    try:
                        self.prompt_input.selection = ((0, 0), (last_line, last_col))
                    except:
                        pass
    
    def get_selected_content(self) -> Optional[str]:
        """Get currently selected content from the TextArea."""
        try:
            if hasattr(self, 'prompt_input'):
                # TextArea has a text property we can use
                # For now, just return None to indicate no selection
                # This will make it fall back to copying all content
                return None
        except Exception as e:
            logging.error(f"Error in get_selected_content: {e}")
        return None