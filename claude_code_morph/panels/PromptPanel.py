"""Prompt Panel - Handles user input and prompt optimization."""

import os
import logging
from typing import Optional, Callable, Dict, Any
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center, Middle, Grid, ScrollableContainer
from textual.widgets import Static, TextArea, Button, Label, Select
from textual.reactive import reactive
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.events import Click, MouseScrollUp, MouseScrollDown
from rich.panel import Panel
from rich.syntax import Syntax
import asyncio
try:
    from .BasePanel import BasePanel
except ImportError:
    # Fallback for when module is loaded dynamically
    from claude_code_morph.panels.BasePanel import BasePanel

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
        border: solid $primary;
        min-width: 13;
    }
    
    PromptPanel #morph-mode-btn:hover {
        background: $primary-lighten-1;
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
    }
    
    PromptPanel .clickable:hover {
        background: $primary;
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
    }
    
    PromptPanel Button#clear-btn, PromptPanel .clear-button {
        background: red !important;
        color: white !important;
        border: solid darkred !important;
        content-align: center middle;
        text-align: center;
    }
    
    PromptPanel Button#clear-btn:focus,
    PromptPanel Button#clear-btn:hover,
    PromptPanel Button#clear-btn:active,
    PromptPanel Button#clear-btn.-active,
    PromptPanel Button#clear-btn:pressed {
        background: red !important;
        color: white !important;
        border: solid darkred !important;
    }
    
    /* Prompt queue styles */
    PromptPanel .prompt-queue-container {
        height: 1fr;
        min-height: 5;
        margin: 1;
        padding: 0;
        background: $surface;
        border: solid $primary;
        overflow-y: auto;
    }
    
    PromptPanel .prompt-queue-item {
        height: 3;
        padding: 0 1;
        margin: 0;
        background: $panel;
        border-bottom: solid $primary-darken-2;
    }
    
    PromptPanel .prompt-queue-item:hover {
        background: $primary-darken-3;
    }
    
    PromptPanel .prompt-queue-item.highlighted {
        background: $primary-darken-2;
        border: solid $accent;
    }
    
    PromptPanel .prompt-queue-item Label {
        height: 100%;
        overflow: hidden ellipsis;
        padding: 1 0;
    }
    
    PromptPanel .queue-empty-message {
        height: 100%;
        content-align: center middle;
        text-style: italic;
        color: $text-muted;
    }
    
    /* Edit prompt dialog styles */
    EditPromptDialog {
        align: center middle;
    }
    
    EditPromptDialog #dialog {
        width: 80%;
        max-width: 100;
        height: 20;
        padding: 1;
        border: thick $primary 80%;
        background: $surface;
    }
    
    EditPromptDialog #edit-input {
        height: 1fr;
        margin: 1;
        padding: 1;
        background: $panel;
        border: solid $primary;
    }
    
    EditPromptDialog #buttons {
        layout: horizontal;
        height: 3;
        align: center middle;
        margin-top: 1;
    }
    
    EditPromptDialog Button {
        width: 12;
        margin: 0 1;
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
        
        # Prompt queue management
        self.prompt_queue = []  # List of queued prompts
        self.highlighted_queue_index = 0  # Currently highlighted item in queue
        self.is_processing = False  # Whether Claude is currently processing
        
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
            'cost_saver_enabled': False,
            'prompt_queue': [],
            'highlighted_queue_index': 0
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
                yield Button("Clear", id="clear-btn")
                yield Button("Submit", id="submit-btn")
                
                # Clear Queue button (will be shown/hidden dynamically)
                self.clear_queue_btn = Button("Clear Queue", id="clear-queue-btn", classes="clear-button")
                self.clear_queue_btn.display = False
                yield self.clear_queue_btn
            
            # Prompt queue container
            self.queue_container = ScrollableContainer(id="queue-container", classes="prompt-queue-container")
            yield self.queue_container
    
    def on_mount(self) -> None:
        """Initialize the queue display when mounted and set IDs for all widgets."""
        # Set IDs for all important widgets that don't already have them
        # The widgets created in compose_content already have IDs set
        
        # Set additional identifiers for widgets that might be dynamically created
        # Only set ID if it's not already set
        if hasattr(self, 'prompt_input') and not self.prompt_input.id:
            self.prompt_input.id = "prompt-input"
            
        if hasattr(self, 'morph_mode_btn') and not self.morph_mode_btn.id:
            self.morph_mode_btn.id = "morph-mode-btn"
            
        if hasattr(self, 'cost_saver_btn') and not self.cost_saver_btn.id:
            self.cost_saver_btn.id = "optimize-btn"
            
        if hasattr(self, 'clear_queue_btn') and not self.clear_queue_btn.id:
            self.clear_queue_btn.id = "clear-queue-btn"
            
        if hasattr(self, 'queue_container') and not self.queue_container.id:
            self.queue_container.id = "queue-container"
        
        # Log the widget IDs for debugging
        logging.debug(f"PromptPanel widgets initialized with IDs:")
        logging.debug(f"  - prompt_input: {getattr(self.prompt_input, 'id', 'No ID')}")
        logging.debug(f"  - morph_mode_btn: {getattr(self.morph_mode_btn, 'id', 'No ID')}")
        logging.debug(f"  - cost_saver_btn: {getattr(self.cost_saver_btn, 'id', 'No ID')}")
        logging.debug(f"  - queue_container: {getattr(self.queue_container, 'id', 'No ID')}")
        
        # Check if we have a restored queue from previous session
        if self.prompt_queue:
            # Show notification about restored queue
            old_count = len(self.prompt_queue)
            self.app.notify(
                f"Found {old_count} queued prompts from previous session. Click to edit/delete them.", 
                severity="warning"
            )
            logging.info(f"Restored {old_count} prompts in queue from previous session")
            
            # Mark queue as paused initially so it doesn't auto-process old prompts
            self.is_processing = True
            
            # Allow manual processing by resetting flag after a delay
            async def reset_processing():
                await asyncio.sleep(2.0)
                self.is_processing = False
            
            asyncio.create_task(reset_processing())
        
        self._update_queue_display()
            
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
        elif button_id == "clear-queue-btn":
            self.clear_queue()
    
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
            
            # Automatically show widget labels when entering morph mode
            # This helps users understand the IDE structure they're editing
            if hasattr(self.app, 'panels'):
                labels_enabled = False
                for panel in self.app.panels.values():
                    if hasattr(panel, 'show_widget_labels') and not panel.show_widget_labels:
                        # Enable widget labels for this panel
                        panel.show_widget_labels = True
                        labels_enabled = True
                        # Note: We don't call toggle_widget_labels() here as it would toggle back to False
                        # The show_widget_labels flag is sufficient for the panel to show labels
                
                # If we enabled any labels, notify about it
                if labels_enabled:
                    self.app.notify("Widget labels enabled to help with IDE editing", severity="information")
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
        # Queue navigation
        elif event.key == "up" and self.prompt_queue:
            self.highlighted_queue_index = max(0, self.highlighted_queue_index - 1)
            self._update_queue_display()
        elif event.key == "down" and self.prompt_queue:
            self.highlighted_queue_index = min(len(self.prompt_queue) - 1, self.highlighted_queue_index + 1)
            self._update_queue_display()
        elif event.key == "enter" and self.prompt_queue:
            # Edit highlighted item
            self._edit_queue_item(self.highlighted_queue_index)
        elif event.key == "ctrl+p":
            # Force process queue
            self.force_process_queue()
            
    def submit_prompt(self) -> None:
        """Submit the current prompt."""
        prompt = self.prompt_input.text.strip()
        
        if not prompt:
            self.app.notify("Please enter a prompt", severity="warning")
            return
            
        # Add to history
        self.prompt_history.append(prompt)
        self.history_index = len(self.prompt_history)
        
        # Add to queue
        mode = getattr(self, 'selected_mode', 'develop')
        self.prompt_queue.append({
            'prompt': prompt,
            'mode': mode,
            'cost_saver': self.cost_saver_enabled
        })
        
        # Update queue display
        self._update_queue_display()
        
        # Clear input
        self.prompt_input.text = ""
        
        # Notify user
        self.app.notify(f"Prompt added to queue (position {len(self.prompt_queue)})", severity="information")
        
        # Process queue if not already processing
        if not self.is_processing:
            logging.info("Starting queue processor")
            asyncio.create_task(self._process_queue())
        
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
    
    def clear_queue(self) -> None:
        """Clear all items from the prompt queue."""
        if self.prompt_queue:
            count = len(self.prompt_queue)
            self.prompt_queue.clear()
            self._update_queue_display()
            self.app.notify(f"Cleared {count} prompts from queue", severity="information")
            logging.info(f"User cleared {count} prompts from queue")
    
    def force_process_queue(self) -> None:
        """Force process the queue even if processor is stuck."""
        if not self.prompt_queue:
            self.app.notify("Queue is empty", severity="information")
            return
            
        if self.is_processing:
            # Reset the processing flag
            self.is_processing = False
            self.app.notify("Reset queue processor, starting again...", severity="warning")
            logging.info("Force resetting queue processor")
        
        # Start processing
        asyncio.create_task(self._process_queue())
        self.app.notify("Force processing queue...", severity="information")
    
    
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
    
    async def _process_queue(self) -> None:
        """Process prompts from the queue."""
        if self.is_processing or not self.prompt_queue:
            return
            
        self.is_processing = True
        
        try:
            while self.prompt_queue:
                logging.info(f"Processing queue with {len(self.prompt_queue)} items")
                
                # First, wait for Claude to become idle before processing
                logging.info("Waiting for Claude to become idle...")
                await self._wait_for_claude_idle()
                logging.info("Claude is idle, processing next prompt")
                
                # Double-check we still have items (might have been deleted while waiting)
                if not self.prompt_queue:
                    break
                
                # Get the first prompt
                item = self.prompt_queue[0]
                prompt = item['prompt']
                mode = item['mode']
                cost_saver = item['cost_saver']
                
                logging.info(f"Processing prompt: {prompt[:50]}...")
                
                # Update display to show processing
                self._update_queue_display()
                
                # Process with cost saver if enabled
                if cost_saver:
                    prompt = await self._call_optimizer(prompt)
                
                # Send to terminal
                if self.on_submit:
                    await self._async_submit(prompt, mode)
                else:
                    await self._send_to_terminal(prompt, mode)
                
                # Wait a moment for the prompt to be sent
                await asyncio.sleep(0.5)
                
                # Remove from queue
                self.prompt_queue.pop(0)
                self._update_queue_display()
                
                logging.info(f"Prompt processed, {len(self.prompt_queue)} items remaining")
                
        finally:
            self.is_processing = False
    
    async def _wait_for_claude_idle(self) -> None:
        """Wait for Claude CLI to become idle."""
        # Check terminal panel for idle state
        terminal = None
        for panel in self.app.panels.values():
            if hasattr(panel, 'is_claude_processing'):
                terminal = panel
                break
        
        if terminal:
            # Poll until Claude is idle (showing Human: prompt)
            max_wait = 300  # 5 minutes max wait
            waited = 0
            while waited < max_wait:
                # Check if Claude is processing
                is_processing = terminal.is_claude_processing()
                if not is_processing:
                    # Claude is idle, we can proceed
                    break
                await asyncio.sleep(0.5)
                waited += 0.5
            
            # Extra wait to ensure prompt is visible
            await asyncio.sleep(0.5)
        else:
            # Fallback: wait a fixed time
            await asyncio.sleep(2.0)
    
    def _update_queue_display(self) -> None:
        """Update the queue display."""
        if not hasattr(self, 'queue_container'):
            return
            
        # Show/hide Clear Queue button based on queue content
        if hasattr(self, 'clear_queue_btn'):
            self.clear_queue_btn.display = bool(self.prompt_queue)
            
        # Clear current display
        self.queue_container.remove_children()
        
        if not self.prompt_queue:
            # Show empty message
            empty_msg = Static("Queue is empty", classes="queue-empty-message")
            self.queue_container.mount(empty_msg)
        else:
            # Display queue items
            for i, item in enumerate(self.prompt_queue):
                # Create queue item container
                queue_item = Vertical(classes="prompt-queue-item")
                
                # Add highlighted class if this is the highlighted item
                if i == self.highlighted_queue_index:
                    queue_item.add_class("highlighted")
                
                # Truncate prompt for display
                prompt_text = item['prompt']
                if len(prompt_text) > 80:
                    prompt_text = prompt_text[:77] + "..."
                
                # Add status indicator
                if i == 0 and self.is_processing:
                    status = "⚡ Processing: "
                else:
                    status = f"{i+1}. "
                
                # Create label
                label = Label(f"{status}{prompt_text}")
                queue_item.mount(label)
                
                # Make it clickable
                queue_item.can_focus = True
                self.queue_container.mount(queue_item)
    
    def on_click(self, event: Click) -> None:
        """Handle click events on queue items."""
        # First call parent's on_click
        super().on_click(event)
        
        # Check if click is on a queue item
        target = self.app.get_widget_at(*event.screen_offset)
        if target and hasattr(target, 'parent'):
            # Find the queue item container
            widget = target
            while widget and not widget.has_class("prompt-queue-item"):
                widget = widget.parent
            
            if widget and widget.has_class("prompt-queue-item"):
                # Find index of clicked item
                for i, child in enumerate(self.queue_container.children):
                    if child == widget:
                        self._edit_queue_item(i)
                        break
    
    def _edit_queue_item(self, index: int) -> None:
        """Edit a queue item."""
        if 0 <= index < len(self.prompt_queue):
            task = asyncio.create_task(self._show_edit_dialog(index))
            task.add_done_callback(self._handle_task_error)
    
    async def _show_edit_dialog(self, index: int) -> None:
        """Show edit dialog for a queue item."""
        
        class EditPromptDialog(ModalScreen):
            """Modal dialog for editing prompts."""
            
            def __init__(self, prompt_text: str, **kwargs):
                super().__init__(**kwargs)
                self.prompt_text = prompt_text
            
            def compose(self):
                with Center():
                    with Middle():
                        with Vertical(id="dialog"):
                            yield Label("Edit Prompt", id="title")
                            self.edit_input = TextArea(self.prompt_text, id="edit-input")
                            yield self.edit_input
                            with Horizontal(id="buttons"):
                                yield Button("Save", variant="primary", id="save")
                                yield Button("Delete", variant="warning", id="delete")
                                yield Button("Cancel", variant="default", id="cancel")
            
            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "save":
                    self.dismiss(("save", self.edit_input.text))
                elif event.button.id == "delete":
                    self.dismiss(("delete", None))
                else:
                    self.dismiss((None, None))
        
        # Show dialog
        item = self.prompt_queue[index]
        result = await self.app.push_screen(
            EditPromptDialog(item['prompt']), 
            wait_for_dismiss=True
        )
        
        if result:
            action, new_text = result
            if action == "save" and new_text:
                # Update the prompt
                self.prompt_queue[index]['prompt'] = new_text.strip()
                self._update_queue_display()
                self.app.notify("Prompt updated", severity="information")
            elif action == "delete":
                # Remove from queue
                self.prompt_queue.pop(index)
                # Adjust highlighted index if needed
                if self.highlighted_queue_index >= len(self.prompt_queue) and self.highlighted_queue_index > 0:
                    self.highlighted_queue_index = len(self.prompt_queue) - 1
                self._update_queue_display()
                self.app.notify("Prompt removed from queue", severity="information")
    
    
    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        """Handle mouse scroll up on queue."""
        if self.prompt_queue and event.x >= self.queue_container.region.x and event.x <= self.queue_container.region.x + self.queue_container.region.width:
            self.highlighted_queue_index = max(0, self.highlighted_queue_index - 1)
            self._update_queue_display()
    
    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        """Handle mouse scroll down on queue."""
        if self.prompt_queue and event.x >= self.queue_container.region.x and event.x <= self.queue_container.region.x + self.queue_container.region.width:
            self.highlighted_queue_index = min(len(self.prompt_queue) - 1, self.highlighted_queue_index + 1)
            self._update_queue_display()
    
    def get_state(self) -> Dict[str, Any]:
        """Get current panel state for persistence.
        
        Returns:
            Dictionary containing panel state
        """
        state = {
            'selected_mode': getattr(self, 'selected_mode', 'develop'),
            'prompt_history': self.prompt_history.copy() if hasattr(self, 'prompt_history') else [],
            'history_index': getattr(self, 'history_index', -1),
            'prompt_queue': self.prompt_queue.copy() if hasattr(self, 'prompt_queue') else [],
            'highlighted_queue_index': getattr(self, 'highlighted_queue_index', 0),
            'cost_saver_enabled': getattr(self, 'cost_saver_enabled', False)
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
        
        # Restore cost saver state
        if 'cost_saver_enabled' in state:
            self.cost_saver_enabled = state['cost_saver_enabled']
            if hasattr(self, 'cost_saver_btn'):
                if self.cost_saver_enabled:
                    self.cost_saver_btn.label = "● Cost Saver"
                    self.cost_saver_btn.add_class("active")
                else:
                    self.cost_saver_btn.label = "○ Cost Saver"
                    self.cost_saver_btn.remove_class("active")
                    
        # Restore prompt history
        if 'prompt_history' in state:
            self.prompt_history = state['prompt_history']
            
        if 'history_index' in state:
            self.history_index = state['history_index']
            
        # Restore prompt queue
        if 'prompt_queue' in state:
            self.prompt_queue = state['prompt_queue']
            # Don't auto-process restored queue
            if self.prompt_queue:
                self.is_processing = True
                # Reset after a delay to allow manual control
                async def reset():
                    await asyncio.sleep(3.0)
                    self.is_processing = False
                asyncio.create_task(reset())
            
        if 'highlighted_queue_index' in state:
            self.highlighted_queue_index = state['highlighted_queue_index']
            
        # Restore current prompt text
        if 'current_prompt' in state and hasattr(self, 'prompt_input') and self.prompt_input:
            self.prompt_input.text = state['current_prompt']
            
        # Update queue display if mounted
        if hasattr(self, 'queue_container'):
            self._update_queue_display()
            
        logging.info(f"PromptPanel state restored: mode={self.selected_mode}, queue_size={len(self.prompt_queue)}")