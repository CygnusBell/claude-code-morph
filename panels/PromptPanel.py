"""Prompt Panel - Handles user input and prompt optimization."""

import os
from typing import Optional, Callable
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center, Middle
from textual.widgets import Static, TextArea, Select, Button, OptionList, Label
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.screen import ModalScreen
from rich.panel import Panel
from rich.syntax import Syntax
import asyncio

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

class PromptPanel(Static):
    """Panel for composing and optimizing prompts."""
    
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    
    ConfirmDialog > Center {
        min-width: 40;
        min-height: 11;
        background: $surface;
        border: solid $primary;
    }
    
    ConfirmDialog #dialog {
        padding: 2;
        width: 100%;
    }
    
    ConfirmDialog #question {
        text-align: center;
        margin-bottom: 2;
    }
    
    ConfirmDialog #buttons {
        align: center middle;
    }
    
    ConfirmDialog Button {
        margin: 0 1;
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
        self._init_params = {"on_submit": on_submit}  # Store for hot-reloading
        self.on_submit = on_submit
        self.prompt_history = []
        self.history_index = -1
        
    def compose(self) -> ComposeResult:
        """Create the panel layout."""
        with Vertical():
            yield Static("📝 Prompt Generator", classes="panel-title")
            
            # Prompt input area
            self.prompt_input = TextArea(
                id="prompt-input"
            )
            self.prompt_input.styles.height = "50%"
            yield self.prompt_input
            
            # Style selector
            yield Static("Style:", classes="section-title")
            self.style_select = OptionList(
                *[Option(style, id=style) for style, _ in self.DEFAULT_STYLES],
                id="style-select"
            )
            self.style_select.styles.height = 5
            self.style_select.highlighted = 0  # Default to verbose
            yield self.style_select
                
            # Buttons
            with Horizontal(classes="buttons"):
                yield Button("Submit", variant="primary", id="submit-btn")
                yield Button("Improve", variant="default", id="optimize-btn")
                yield Button("Clear", variant="warning", id="clear-btn")
            
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "submit-btn":
            self.submit_prompt()
        elif button_id == "optimize-btn":
            self.optimize_prompt()
        elif button_id == "clear-btn":
            self.clear_prompt()
            
    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "ctrl+enter":
            self.submit_prompt()
        elif event.key == "ctrl+o":
            self.optimize_prompt()
        elif event.key == "ctrl+l":
            self.clear_prompt()
        elif event.key == "up" and event.ctrl:
            self.navigate_history(-1)
        elif event.key == "down" and event.ctrl:
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
        
        # Call submit handler
        if self.on_submit:
            # Run async callback
            asyncio.create_task(self._async_submit(final_prompt))
        else:
            # Notify terminal panel directly
            asyncio.create_task(self._send_to_terminal(final_prompt))
            
        # Clear input
        self.prompt_input.text = ""
        
    async def _async_submit(self, prompt: str) -> None:
        """Handle async submission."""
        await self.on_submit(prompt)
        
    async def _send_to_terminal(self, prompt: str) -> None:
        """Send prompt to terminal panel."""
        # Find terminal panel
        terminal = None
        for panel in self.app.panels.values():
            if panel.__class__.__name__ == "TerminalPanel":
                terminal = panel
                break
                
        if terminal and hasattr(terminal, 'send_prompt'):
            await terminal.send_prompt(prompt)
        else:
            self.app.notify("Terminal panel not found", severity="error")
            
    def optimize_prompt(self) -> None:
        """Optimize the current prompt using AI."""
        prompt = self.prompt_input.text.strip()
        
        if not prompt:
            self.app.notify("Please enter a prompt to optimize", severity="warning")
            return
            
        # Get selected style from OptionList
        selected_option = self.style_select.highlighted
        style = list(dict(self.DEFAULT_STYLES).keys())[selected_option] if selected_option is not None else "verbose"
        
        # Run optimization in background
        asyncio.create_task(self._optimize_prompt_async(prompt, style))
        
    async def _optimize_prompt_async(self, prompt: str, style: str) -> None:
        """Optimize prompt asynchronously and submit."""
        self.app.notify("Improving prompt...", severity="information")
        
        try:
            optimized = await self._call_optimizer(prompt, style)
            self.app.notify("Prompt improved!", severity="success")
            
            # Submit the optimized prompt directly
            if self.on_submit:
                await self._async_submit(optimized)
            else:
                await self._send_to_terminal(optimized)
                
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
                model="llama-4-maverick-17Bx128E",
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
            # Show confirmation dialog
            asyncio.create_task(self._confirm_clear())
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
        if await self.app.push_screen_wait(ConfirmDialog()):
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