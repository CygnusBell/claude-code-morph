"""Prompt Panel - Handles user input and prompt optimization."""

import os
import logging
from typing import Optional, Callable, Dict, Any
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
try:
    from .BasePanel import BasePanel
except ImportError:
    # Fallback for dynamic loading
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from BasePanel import BasePanel

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
        height: 99%;
        margin: 0;
        padding: 0;
    }
    
    PromptPanel .prompt-content {
        height: 1fr;
        width: 100%;
        margin: 0;
        padding: 0;
        layout: vertical;
    }
    
    PromptPanel .panel-title {
        height: 1;
        padding: 0 1;
        text-align: center;
        background: $primary;
        margin: 0;
    }
    
    PromptPanel #prompt-input {
        height: 1fr;
        min-height: 10;
        margin: 1;
        padding: 1;
        background: $surface;
        border: solid $primary;
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
        align: center middle;
        margin: 0;
        padding: 1;
    }
    
    PromptPanel #submit-btn {
        background: $surface;
        border: solid $primary;
        margin-left: auto;
    }
    
    PromptPanel #morph-mode-btn {
        background: $panel;
        color: $text;
        border: solid $primary;
        min-width: 13;
    }
    
    PromptPanel #morph-mode-btn:hover {
        background: $primary-lighten-1;
        color: $text;
    }
    
    PromptPanel #morph-mode-btn.active {
        background: rgb(0,100,0);
        color: white;
        border: solid rgb(0,150,0);
    }
    
    PromptPanel #morph-mode-btn.active:hover {
        background: rgb(0,120,0);
        color: white;
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
    
    PromptPanel Button:focus {
        text-style: none;
        color: $text;
    }
    
    PromptPanel Button:hover {
        color: $text;
    }
    
    PromptPanel Button:active {
        color: $text;
    }
    
    PromptPanel Button.-active {
        color: $text;
    }
    
    PromptPanel Button:pressed {
        color: $text;
    }
    
    PromptPanel Button#clear-btn, PromptPanel .clear-button {
        background: red !important;
        color: white !important;
        border: solid darkred !important;
        content-align: center middle;
        text-align: center;
    }
    
    
    /* Confirmation dialog styles */
    ConfirmDialog {
        align: center middle;
    }
    
    ConfirmDialog #dialog {
        grid-size: 1;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 1 2;
        width: 40;
        height: 11;
        border: thick $primary 80%;
        background: $surface;
    }
    
    ConfirmDialog #question {
        column-span: 1;
        height: 1;
        width: 1fr;
        content-align: center middle;
        margin-bottom: 1;
    }
    
    ConfirmDialog #buttons {
        layout: horizontal;
        height: 3;
        align: center middle;
    }
    
    ConfirmDialog Button {
        width: 12;
        margin: 0 1;
    }
    """
    
    
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
            'selected_mode': 'develop',
            'prompt_text': '',
            'prompt_history': [],
            'history_index': -1,
            'cost_saver_enabled': False
        }
        
    def compose_content(self) -> ComposeResult:
        """Create the panel layout."""
        # Initialize values if not already set
        if not hasattr(self, 'selected_mode'):
            self.selected_mode = "develop"
        if not hasattr(self, 'cost_saver_enabled'):
            self.cost_saver_enabled = False
        
        # Main container to fill remaining space
        with Vertical(classes="prompt-content"):
            # Prompt input area - takes up most space
            self.prompt_input = TextArea(id="prompt-input")
            yield self.prompt_input
            
            # Debug: Log composition
            logging.debug("Creating controls container")
            
            # Controls with toggle and action buttons
            with Horizontal(classes="button-controls"):
                # Morph Mode toggle button with indicator
                self.morph_mode_btn = Button(
                    "○ Morph Mode",
                    id="morph-mode-btn"
                )
                yield self.morph_mode_btn
                
                # Cost Saver toggle button with indicator
                self.cost_saver_btn = Button(
                    "○ Cost Saver",
                    id="optimize-btn"
                )
                yield self.cost_saver_btn
                
                # Action buttons
                yield Button("Submit", id="submit-btn")
                yield Button("Clear", id="clear-btn")
    
            
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "submit-btn":
            self.submit_prompt()
        elif button_id == "optimize-btn":
            self.toggle_cost_saver()
        elif button_id == "clear-btn":
            self.clear_prompt()
        elif button_id == "morph-mode-btn":
            self.toggle_morph_mode()
    
    def toggle_cost_saver(self) -> None:
        """Toggle cost saver mode."""
        # Toggle the state
        self.cost_saver_enabled = not self.cost_saver_enabled
        
        # Update button appearance
        if self.cost_saver_enabled:
            self.cost_saver_btn.label = "● Cost Saver"  # Filled circle
            self.cost_saver_btn.add_class("active")
            self.app.notify("Cost Saver: ON - AI refinement enabled", severity="information")
        else:
            self.cost_saver_btn.label = "○ Cost Saver"  # Empty circle
            self.cost_saver_btn.remove_class("active")
            self.app.notify("Cost Saver: OFF - AI refinement disabled", severity="information")
    
    def toggle_morph_mode(self) -> None:
        """Toggle between develop and morph modes."""
        # Toggle the mode
        self.selected_mode = "develop" if self.selected_mode == "morph" else "morph"
        
        # Update button appearance
        if self.selected_mode == "morph":
            self.morph_mode_btn.label = "● Morph Mode"  # Filled circle
            self.morph_mode_btn.add_class("active")
            self.app.notify("Morph Mode: ON - Editing the IDE", severity="information")
        else:
            self.morph_mode_btn.label = "○ Morph Mode"  # Empty circle
            self.morph_mode_btn.remove_class("active")
            self.app.notify("Morph Mode: OFF - Editing current project", severity="information")
    
    
            
    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        if event.key == "ctrl+enter" or event.key == "shift+enter":
            self.submit_prompt()
        elif event.key == "ctrl+o":
            self.toggle_cost_saver()
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
        
        # Check if cost saver is enabled
        if self.cost_saver_enabled:
            # Optimize the prompt before submitting
            self.optimize_and_submit_prompt(prompt)
            return
        
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
        # Find terminal panel (any panel with send_prompt method)
        terminal = None
        for panel in self.app.panels.values():
            if hasattr(panel, 'send_prompt'):
                terminal = panel
                break
                
        if terminal and hasattr(terminal, 'send_prompt'):
            await terminal.send_prompt(prompt, mode)
        else:
            self.app.notify("Terminal panel not found", severity="error")
            
    def optimize_and_submit_prompt(self, prompt: str) -> None:
        """Optimize and submit the prompt when Cost Saver is enabled."""
        # Run optimization in background
        task = asyncio.create_task(self._optimize_prompt_async(prompt))
        task.add_done_callback(self._handle_task_error)
    
    def optimize_prompt(self) -> None:
        """Optimize the current prompt using AI."""
        prompt = self.prompt_input.text.strip()
        
        if not prompt:
            self.app.notify("Please enter a prompt to optimize", severity="warning")
            return
        
        # Run optimization in background
        task = asyncio.create_task(self._optimize_prompt_async(prompt))
        task.add_done_callback(self._handle_task_error)
        
    async def _optimize_prompt_async(self, prompt: str) -> None:
        """Optimize prompt asynchronously and submit."""
        self.app.notify("Improving prompt...", severity="information")
        
        try:
            optimized = await self._call_optimizer(prompt)
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
            
    async def _call_optimizer(self, prompt: str) -> str:
        """Call AI optimizer to enhance the prompt."""
        
        system_prompt = """You are a developer assistant that rewrites vague prompts into precise, Claude-friendly instructions.

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
            return self._simple_enhance(prompt)
            
    def _simple_enhance(self, prompt: str) -> str:
        """Simple prompt enhancement without AI."""
        # Add a generic prefix for clarity
        prefix = "Please complete the following task:\n\n"
        
        # Add some structure
        enhanced = f"{prefix}{prompt}"
        
        # Add generic helpful guidelines
        enhanced += "\n\nPlease provide:\n- Clear implementation\n- Proper error handling\n- Relevant code comments"
            
        return enhanced
        
    def clear_prompt(self) -> None:
        """Clear prompt area with confirmation."""
        # Check if there's any content to clear
        if self.prompt_input.text.strip():
            # Show confirmation dialog using run_worker instead of create_task
            self.app.run_worker(self._confirm_clear, exclusive=True)
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
        result = await self.app.push_screen(ConfirmDialog(), wait_for_dismiss=True)
        if result:
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
    
    def get_state(self) -> Dict[str, Any]:
        """Get current panel state for persistence.
        
        Returns:
            Dictionary containing panel state
        """
        state = {
            'selected_mode': getattr(self, 'selected_mode', 'develop'),
            'prompt_history': self.prompt_history.copy() if hasattr(self, 'prompt_history') else [],
            'history_index': getattr(self, 'history_index', -1)
        }
        
        # Get current prompt text if available
        if hasattr(self, 'prompt_input') and self.prompt_input:
            state['current_prompt'] = self.prompt_input.text
            
        return state
        
    def restore_state(self, state: Dict[str, Any]) -> None:
        """Restore panel state from saved data.
        
        Args:
            state: Dictionary containing saved panel state
        """
        # Restore selections
        if 'selected_mode' in state:
            self.selected_mode = state['selected_mode']
            # Update the button appearance if it exists
            if hasattr(self, 'morph_mode_btn'):
                if self.selected_mode == 'morph':
                    self.morph_mode_btn.label = "● Morph Mode"
                    self.morph_mode_btn.add_class("active")
                else:
                    self.morph_mode_btn.label = "○ Morph Mode"
                    self.morph_mode_btn.remove_class("active")
                    
        # Restore prompt history
        if 'prompt_history' in state:
            self.prompt_history = state['prompt_history']
            
        if 'history_index' in state:
            self.history_index = state['history_index']
            
        # Restore current prompt text
        if 'current_prompt' in state and hasattr(self, 'prompt_input') and self.prompt_input:
            self.prompt_input.text = state['current_prompt']
            
        logging.info(f"PromptPanel state restored: mode={self.selected_mode}")