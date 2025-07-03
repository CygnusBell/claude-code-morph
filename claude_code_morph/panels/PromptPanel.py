"""Prompt Panel - Handles user input and prompt optimization."""

import os
import logging
from typing import Optional, Callable, Dict, Any
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Center, Middle, Grid, ScrollableContainer
from textual.widgets import Static, TextArea, Button, Label, Select, Input
from textual.reactive import reactive
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.events import Click, MouseScrollUp, MouseScrollDown, Key
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
    /* CSS Updated: 2025-07-02 22:47 - Queue items now height: 1 */
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
        margin: 0 1;
        padding: 1;
        background: $surface;
        border: solid $primary;
    }
    
    PromptPanel .controls-container {
        layout: vertical;
        height: auto;
        min-height: 3;
        margin: 0;
        padding: 0;
        background: $panel;
    }
    
    PromptPanel .button-controls {
        height: 3;
        layout: horizontal;
        align: center middle;
        margin: 0;
        padding: 0 1;
    }
    
    PromptPanel #submit-btn {
        background: $surface;
        border: solid $primary;
        margin-left: auto;
        text-style: none;
    }
    
    PromptPanel #morph-mode-btn {
        background: $panel;
        border: solid $primary;
        min-width: 13;
        text-style: none;
    }
    
    PromptPanel #morph-mode-btn:hover {
        background: $primary-lighten-1;
        text-style: none;
    }
    
    PromptPanel #morph-mode-btn:focus {
        text-style: none;
    }
    
    PromptPanel #morph-mode-btn.active {
        background: rgb(0,100,0);
        color: white;
        border: solid rgb(0,150,0);
        text-style: none;
    }
    
    PromptPanel #morph-mode-btn.active:hover {
        background: rgb(0,120,0);
        color: white;
        text-style: none;
    }
    
    PromptPanel #morph-mode-btn.active:focus {
        background: rgb(0,100,0);
        color: white;
        text-style: none;
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
        text-style: none;
    }
    
    PromptPanel Button:focus {
        text-style: none;
    }
    
    PromptPanel Button:hover {
        text-style: none;
    }
    
    PromptPanel Button.-active {
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
    PromptPanel Button#clear-btn.-active {
        background: red !important;
        color: white !important;
        border: solid darkred !important;
    }
    
    /* Prompt queue styles */
    PromptPanel .prompt-queue-container {
        height: auto;
        max-height: 5;
        min-height: 2;
        margin: 0;
        padding: 0;
        background: $surface;
        border: solid $primary;
        overflow-y: auto;
    }
    
    PromptPanel .prompt-queue-item {
        layout: horizontal;
        height: 1;
        padding: 0 0.5;
        margin: 0;
        background: $panel;
        border-bottom: thin $primary-darken-3;
        align: center middle;
    }
    
    PromptPanel .prompt-queue-item:hover {
        background: $primary-darken-3;
    }
    
    PromptPanel .prompt-queue-item.highlighted {
        background: $primary-darken-2;
        border: solid $accent;
    }
    
    PromptPanel .prompt-queue-item.sending {
        background: $warning-darken-3;
        border-left: thick $warning;
    }
    
    PromptPanel .prompt-queue-item.next {
        background: $success-darken-3;
        border-left: thick $success;
    }
    
    PromptPanel .prompt-queue-item.failed {
        background: $error-darken-3;
        border-left: thick $error;
    }
    
    PromptPanel .queue-item-status {
        width: 6;
        text-align: left;
    }
    
    PromptPanel .queue-item-label {
        width: 1fr;
        padding: 0 0.5;
        text-style: normal;
        overflow: hidden ellipsis;
    }
    
    PromptPanel .queue-item-label:hover {
        text-style: bold;
        background: $primary-darken-3;
    }
    
    PromptPanel .queue-item-edit {
        width: 1fr;
        margin: 0 1;
        height: 1;
    }
    
    PromptPanel .queue-item-delete {
        width: 3;
        height: 1;
        min-width: 3;
        padding: 0;
        margin: 0;
    }
    
    PromptPanel .queue-item-save-btn, PromptPanel .queue-item-cancel-btn {
        width: 3;
        height: 1;
        min-width: 3;
        padding: 0;
        margin: 0 0 0 1;
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
        
        # Prompt queue management - NEW IMPLEMENTATION
        self.prompt_queue = []  # Still a list for display, but not for processing
        self._queue_for_processing = asyncio.Queue()  # Thread-safe queue for processing
        self._process_lock = asyncio.Lock()  # Prevent concurrent processors
        self._processor_task = None  # Track the active processor task
        self.highlighted_queue_index = 0  # Currently highlighted item in queue
        self._editing_index = -1  # Index of item being edited inline
        self._queue_paused = False  # Whether queue processing is paused
        self._last_activity_time = 0  # Track last activity for timeout detection
        self._monitor_task = None  # Track the monitoring task
        
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
        if not hasattr(self, 'context_saver_enabled'):
            self.context_saver_enabled = False
        
        # Remove test label
        
        # Main container - but don't use classes that might have conflicting CSS
        with Vertical():
            # Prompt input area - takes up most space
            self.prompt_input = TextArea(id="prompt-input")
            self.prompt_input.styles.height = "1fr"
            self.prompt_input.styles.min_height = 10
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
                
                # Token Saver toggle button with indicator
                self.cost_saver_btn = Button(
                    "○ Token Saver",
                    id="optimize-btn"
                )
                yield self.cost_saver_btn
                
                # Context Saver toggle button with indicator
                self.context_saver_btn = Button(
                    "○ Context Saver",
                    id="context-saver-btn"
                )
                yield self.context_saver_btn
                
                # Action buttons
                yield Button("Clear", id="clear-btn")
                yield Button("Submit", id="submit-btn")
                
                # Clear Queue button (will be shown/hidden dynamically)
                self.clear_queue_btn = Button("Clear Queue", id="clear-queue-btn", classes="clear-button")
                self.clear_queue_btn.display = False
                yield self.clear_queue_btn
                
                # Resume Queue button (will be shown/hidden dynamically)
                self.resume_queue_btn = Button("Resume Queue", id="resume-queue-btn", variant="success")
                self.resume_queue_btn.display = False
                yield self.resume_queue_btn
            
            # Prompt queue container - set size directly
            self.queue_container = ScrollableContainer(id="queue-container", classes="prompt-queue-container")
            self.queue_container.styles.height = 3  # Fixed height of 3 lines
            self.queue_container.styles.max_height = 3
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
            pending_count = sum(1 for item in self.prompt_queue if item.get('status', 'pending') in ['pending', 'failed'])
            
            if pending_count > 0:
                self.app.notify(
                    f"Found {pending_count} pending prompts from previous session. Click 'Resume Queue' to process them.", 
                    severity="warning"
                )
            else:
                self.app.notify(
                    f"Found {old_count} queued prompts from previous session (none pending).", 
                    severity="information"
                )
            logging.info(f"Restored {old_count} prompts in queue from previous session ({pending_count} pending)")
            
            # Mark queue as paused initially so it doesn't auto-process old prompts
            self._queue_paused = True
            
            # Allow manual processing by resetting flag after a delay
            async def reset_processing():
                await asyncio.sleep(2.0)
                self._queue_paused = False
            
            asyncio.create_task(reset_processing())
        
        self._update_queue_display()
        
        # Start queue monitor task (combines health monitoring and processing)
        if not hasattr(self, '_queue_monitor_task') or self._queue_monitor_task.done():
            self._queue_monitor_task = asyncio.create_task(self._monitor_queue())
        
    async def _monitor_queue(self) -> None:
        """Monitor the queue and ensure it's processed when Claude is idle."""
        import time
        monitor_cycle = 0
        
        while True:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds
                monitor_cycle += 1
                
                # Skip if queue is empty
                if not self.prompt_queue:
                    continue
                
                # Count items by status
                status_counts = {}
                for item in self.prompt_queue:
                    status = item.get('status', 'pending')
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                # Check processor health
                processor_running = self._processor_task and not self._processor_task.done()
                processing_queue_size = self._queue_for_processing.qsize()
                
                # Log status every 12 cycles (60 seconds)
                if monitor_cycle % 12 == 0:
                    logging.info(f"Queue Health: display={len(self.prompt_queue)} "
                               f"processing={processing_queue_size} "
                               f"status={status_counts} "
                               f"processor={'running' if processor_running else 'stopped'} "
                               f"paused={self._queue_paused}")
                
                # Auto-start processor if needed
                pending_count = status_counts.get('pending', 0) + status_counts.get('failed', 0)
                if pending_count > 0 and not processor_running and not self._queue_paused:
                    # Check if Claude is idle before starting
                    terminal = None
                    for panel in self.app.panels.values():
                        if hasattr(panel, 'is_claude_processing'):
                            terminal = panel
                            break
                    
                    if terminal:
                        try:
                            is_claude_processing = terminal.is_claude_processing()
                            if not is_claude_processing:
                                logging.info(f"Auto-starting processor: {pending_count} pending items, Claude is idle")
                                self._ensure_processor_running()
                            else:
                                logging.debug("Claude is busy, waiting to start processor")
                        except Exception as e:
                            logging.error(f"Error checking Claude state: {e}")
                    else:
                        # No terminal found, try anyway
                        if monitor_cycle % 20 == 0:  # Log less frequently
                            logging.warning("No terminal panel found, starting processor anyway")
                        self._ensure_processor_running()
                
                # Update button visibility
                self._update_queue_display()
                    
            except Exception as e:
                logging.error(f"Queue monitor error: {e}", exc_info=True)
                await asyncio.sleep(5.0)  # Wait longer on error
            
    
    def toggle_cost_saver(self) -> None:
        """Toggle cost saver mode."""
        # Toggle the state
        self.cost_saver_enabled = not self.cost_saver_enabled
        
        # Update button appearance
        if self.cost_saver_enabled:
            self.cost_saver_btn.label = "● Token Saver"  # Filled circle
            self.cost_saver_btn.add_class("active")
            self.app.notify("Token Saver: ON - AI refinement enabled", severity="information")
        else:
            self.cost_saver_btn.label = "○ Token Saver"  # Empty circle
            self.cost_saver_btn.remove_class("active")
            self.app.notify("Token Saver: OFF - AI refinement disabled", severity="information")
    
    def toggle_context_saver(self) -> None:
        """Toggle context saver mode."""
        # Toggle the state
        self.context_saver_enabled = not self.context_saver_enabled
        
        # Update button appearance
        if self.context_saver_enabled:
            self.context_saver_btn.label = "● Context Saver"  # Filled circle
            self.context_saver_btn.add_class("active")
            self.app.notify("Context Saver: ON", severity="information")
        else:
            self.context_saver_btn.label = "○ Context Saver"  # Empty circle
            self.context_saver_btn.remove_class("active")
            self.app.notify("Context Saver: OFF", severity="information")
    
    def toggle_morph_mode(self) -> None:
        """Toggle between develop and morph modes."""
        # Toggle the mode
        self.selected_mode = "develop" if self.selected_mode == "morph" else "morph"
        
        # Update button appearance
        if self.selected_mode == "morph":
            self.morph_mode_btn.label = "● Morph Mode"  # Filled circle
            self.morph_mode_btn.add_class("active")
            self.app.notify("Morph Mode: ON - Editing the IDE", severity="information")
            
            # Widget labels will automatically show in morph mode via hover detection
        else:
            self.morph_mode_btn.label = "○ Morph Mode"  # Empty circle
            self.morph_mode_btn.remove_class("active")
            self.app.notify("Morph Mode: OFF - Editing current project", severity="information")
    
    
            
    def on_key(self, event) -> None:
        """Handle keyboard shortcuts."""
        # Handle Escape to cancel editing
        if event.key == "escape" and hasattr(self, '_editing_index') and self._editing_index >= 0:
            self._cancel_edit()
            event.stop()
        elif event.key == "ctrl+enter" or event.key == "shift+enter":
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
            self._start_editing(self.highlighted_queue_index)
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
        
        # Create queue item with simplified structure
        import uuid
        import time
        mode = getattr(self, 'selected_mode', 'develop')
        queue_item = {
            'id': str(uuid.uuid4()),
            'prompt': prompt,
            'mode': mode,
            'cost_saver': self.cost_saver_enabled,
            'created_at': time.time(),
        }
        
        # Add to display queue
        self.prompt_queue.append(queue_item)
        
        # Add to processing queue (thread-safe)
        asyncio.create_task(self._queue_for_processing.put(queue_item))
        
        # Update queue display
        self._update_queue_display()
        
        # Clear input
        self.prompt_input.text = ""
        
        # Notify user
        self.app.notify(f"Prompt added to queue (position {len(self.prompt_queue)})", severity="information")
        
        # Start processor if not running
        self._ensure_processor_running()
        
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
            try:
                logging.info(f"Sending prompt to terminal panel: {terminal.__class__.__name__}")
                await terminal.send_prompt(prompt, mode)
                logging.info("Prompt sent successfully to terminal")
            except Exception as e:
                logging.error(f"Error sending prompt to terminal: {e}")
                self.app.notify(f"Error sending prompt: {e}", severity="error")
                raise
        else:
            error_msg = "Terminal panel not found or doesn't have send_prompt method"
            logging.error(error_msg)
            self.app.notify(error_msg, severity="error")
            raise RuntimeError(error_msg)
            
    def optimize_and_submit_prompt(self, prompt: str) -> None:
        """Optimize and submit the prompt when Token Saver is enabled."""
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
            
        # Cancel existing processor if running
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            self.app.notify("Cancelled existing processor, starting new one...", severity="warning")
            logging.info("Force cancelled existing queue processor")
        
        # Reset pause state
        self._queue_paused = False
        
        # Re-add all pending items to processing queue
        pending_count = 0
        for item in self.prompt_queue:
            if item.get('status', 'pending') in ['pending', 'failed']:
                item['status'] = 'pending'  # Reset failed items
                item['attempts'] = 0  # Reset attempts
                asyncio.create_task(self._queue_for_processing.put(item.copy()))
                pending_count += 1
        
        if pending_count > 0:
            self.app.notify(f"Re-queued {pending_count} prompts for processing", severity="information")
            # Start processing
            self._ensure_processor_running()
        else:
            self.app.notify("No pending prompts to process", severity="information")
    
    
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
    
    # Legacy method kept for compatibility during transition
    async def _process_queue(self) -> None:
        """Legacy queue processor - redirects to new implementation."""
        logging.info("Legacy _process_queue called, redirecting to new implementation")
        await self._process_queue_v2()
    
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
            last_state_log = 0  # Track when we last logged the state
            
            while waited < max_wait:
                # Check if Claude is processing
                is_processing = terminal.is_claude_processing()
                
                # Log state every 5 seconds to debug
                if waited - last_state_log >= 5:
                    logging.info(f"Waiting for Claude: is_processing={is_processing}, waited={waited:.1f}s")
                    last_state_log = waited
                
                if not is_processing:
                    # Claude is idle, we can proceed
                    logging.info(f"Claude is idle after waiting {waited:.1f}s")
                    break
                    
                await asyncio.sleep(0.5)
                waited += 0.5
            
            if waited >= max_wait:
                logging.warning(f"Timeout waiting for Claude to become idle after {max_wait}s")
                self.app.notify("Warning: Claude may be stuck. Proceeding anyway...", severity="warning")
            
            # Extra wait to ensure prompt is visible and Claude is ready
            await asyncio.sleep(1.5)
        else:
            # Fallback: wait a fixed time
            logging.warning("No terminal panel found with is_claude_processing method, using fallback wait")
            await asyncio.sleep(2.0)
    
    def _ensure_processor_running(self) -> None:
        """Ensure the queue processor is running."""
        # Check if processor task exists and is running
        if self._processor_task and not self._processor_task.done():
            logging.debug("Queue processor is already running")
            return
        
        # Start new processor task
        logging.info("Starting queue processor task")
        self._processor_task = asyncio.create_task(self._process_queue_v2())
        
        # Add error handler
        def handle_error(task):
            try:
                task.result()
            except asyncio.CancelledError:
                logging.info("Queue processor was cancelled")
            except Exception as e:
                logging.error(f"Queue processor error: {e}", exc_info=True)
                self.app.notify(f"Queue processor error: {e}", severity="error")
            finally:
                # Reset state on error or cancellation
                self._processor_task = None
        
        self._processor_task.add_done_callback(handle_error)
    
    async def _process_queue_v2(self) -> None:
        """Process queue items using asyncio.Lock for thread safety."""
        async with self._process_lock:
            logging.info("Queue processor started")
            processed_count = 0
            
            try:
                while True:
                    # Check if we have items in the processing queue
                    if self._queue_for_processing.empty():
                        logging.info("Processing queue is empty, exiting processor")
                        break
                    
                    # Get next item from queue (this is thread-safe)
                    try:
                        item = await asyncio.wait_for(self._queue_for_processing.get(), timeout=1.0)
                    except asyncio.TimeoutError:
                        logging.debug("No items in processing queue")
                        break
                    
                    logging.info(f"Processing queue item {item['id'][:8]}...")
                    
                    # Find corresponding display item and update status
                    display_item = None
                    for idx, display in enumerate(self.prompt_queue):
                        if display['id'] == item['id']:
                            display_item = display
                            display_item['status'] = 'sending'
                            display_item['attempts'] = display_item.get('attempts', 0) + 1
                            self._update_queue_display()
                            break
                    
                    if not display_item:
                        logging.error(f"Display item not found for {item['id']}")
                        continue
                    
                    # Wait for Claude to be idle
                    try:
                        logging.info("Waiting for Claude to be idle...")
                        await self._wait_for_claude_idle()
                    except Exception as e:
                        logging.error(f"Error waiting for Claude: {e}")
                        display_item['status'] = 'failed'
                        display_item['last_error'] = str(e)
                        self._update_queue_display()
                        continue
                    
                    # Send prompt to terminal
                    success = False
                    try:
                        logging.info(f"Sending prompt to terminal: {item['prompt'][:50]}...")
                        
                        # Find terminal panel
                        terminal = None
                        for panel in self.app.panels.values():
                            if hasattr(panel, 'send_prompt'):
                                terminal = panel
                                break
                        
                        if not terminal:
                            raise RuntimeError("No terminal panel found")
                        
                        # Send with proper mode
                        await terminal.send_prompt(item['prompt'], item['mode'])
                        
                        # Wait a bit for Claude to start processing
                        await asyncio.sleep(2.0)
                        
                        # Mark as successfully sent and remove from display queue
                        success = True
                        processed_count += 1
                        logging.info(f"Successfully sent prompt {item['id'][:8]}")
                        
                        # Remove from display queue
                        self.prompt_queue.remove(display_item)
                        self._update_queue_display()
                        
                        # Notify user
                        remaining = len(self.prompt_queue)
                        if remaining > 0:
                            self.app.notify(f"Prompt sent! {remaining} remaining in queue", severity="information")
                        else:
                            self.app.notify("All prompts processed!", severity="success")
                        
                        # Wait between prompts to avoid overwhelming Claude
                        if remaining > 0:
                            await asyncio.sleep(3.0)
                    
                    except Exception as e:
                        logging.error(f"Failed to send prompt: {e}")
                        display_item['status'] = 'failed'
                        display_item['last_error'] = str(e)
                        self._update_queue_display()
                        
                        # Check retry attempts
                        if display_item.get('attempts', 0) >= 3:
                            logging.error(f"Max retries reached for {item['id'][:8]}")
                            self.prompt_queue.remove(display_item)
                            self._update_queue_display()
                            self.app.notify(f"Failed to send prompt after 3 attempts", severity="error")
                
                logging.info(f"Queue processor finished. Processed {processed_count} items")
                
            except Exception as e:
                logging.error(f"Queue processor error: {e}", exc_info=True)
                self.app.notify(f"Queue processor crashed: {e}", severity="error")
            finally:
                # Clear processor task reference
                self._processor_task = None
                logging.info("Queue processor exited")
    
    def _update_queue_display(self) -> None:
        """Update the queue display."""
        if not hasattr(self, 'queue_container'):
            return
            
        # Show/hide queue control buttons based on queue content
        if hasattr(self, 'clear_queue_btn'):
            self.clear_queue_btn.display = bool(self.prompt_queue)
        
        # Show Resume button if queue is paused or has pending items
        if hasattr(self, 'resume_queue_btn'):
            has_pending = any(item.get('status', 'pending') in ['pending', 'failed'] for item in self.prompt_queue)
            is_processor_dead = not self._processor_task or self._processor_task.done()
            self.resume_queue_btn.display = bool(self.prompt_queue) and has_pending and is_processor_dead
            
        # Clear current display
        self.queue_container.remove_children()
        
        if not self.prompt_queue:
            # Show empty message
            empty_msg = Static("Queue is empty", classes="queue-empty-message")
            self.queue_container.mount(empty_msg)
        else:
            # Display queue items
            for i, item in enumerate(self.prompt_queue):
                # Create queue item container with horizontal layout
                queue_item = Horizontal(classes="prompt-queue-item")
                
                # Add highlighted class if this is the highlighted item
                if i == self.highlighted_queue_index:
                    queue_item.add_class("highlighted")
                
                # Check if this item is being edited
                is_editing = getattr(self, '_editing_index', -1) == i
                
                # Add status indicator based on item status
                item_status = item.get('status', 'pending')
                if item_status == 'sending':
                    status = "⚡"
                    queue_item.add_class("sending")
                elif item_status == 'failed':
                    status = "❌"
                    queue_item.add_class("failed")
                elif item_status == 'pending' and i == 0:
                    status = "▶️"
                    queue_item.add_class("next")
                else:
                    status = f"{i+1}."
                
                # Add mode and options indicators
                mode_indicator = "🔧" if item['mode'] == 'develop' else "🎨"
                saver_indicator = "💰" if item.get('cost_saver', False) else ""
                
                # Create status/mode container
                status_container = Static(f"{status} {mode_indicator} {saver_indicator}", classes="queue-item-status")
                queue_item.mount(status_container)
                
                if is_editing:
                    # Show input field for editing
                    edit_input = Input(
                        value=item['prompt'],
                        classes="queue-item-edit",
                        id=f"edit-input-{i}"
                    )
                    queue_item.mount(edit_input)
                    
                    # Add save/cancel buttons
                    save_btn = Button("✓", variant="success", classes="queue-item-save-btn", id=f"save-{i}")
                    cancel_btn = Button("✗", variant="default", classes="queue-item-cancel-btn", id=f"cancel-{i}")
                    queue_item.mount(save_btn)
                    queue_item.mount(cancel_btn)
                else:
                    # Show label with prompt text (clickable for editing)
                    prompt_text = item['prompt']
                    if len(prompt_text) > 70:
                        prompt_text = prompt_text[:67] + "..."
                    
                    label = Label(prompt_text, classes="queue-item-label", id=f"label-{i}")
                    label.can_focus = True
                    label.tooltip = "Click to edit"
                    queue_item.mount(label)
                    
                    # Add delete button
                    delete_btn = Button("🗑", variant="error", classes="queue-item-delete", id=f"delete-{i}")
                    delete_btn.tooltip = "Delete this prompt"
                    queue_item.mount(delete_btn)
                
                self.queue_container.mount(queue_item)
    
    def on_click(self, event: Click) -> None:
        """Handle click events on queue items."""
        # First call parent's on_click
        super().on_click(event)
        
        # Check if click is on a queue item label
        widget_info = self.app.get_widget_at(*event.screen_offset)
        if widget_info:
            target, _ = widget_info  # Unpack widget and region
            if target and hasattr(target, 'id') and target.id and target.id.startswith('label-'):
                # Extract index from label ID
                try:
                    index = int(target.id.split('-')[1])
                    self._start_editing(index)
                except (ValueError, IndexError):
                    pass
    
    def _start_editing(self, index: int) -> None:
        """Start in-place editing of a queue item."""
        if 0 <= index < len(self.prompt_queue):
            self._editing_index = index
            self._update_queue_display()
            # Focus the input field
            edit_input = self.query_one(f"#edit-input-{index}", Input)
            if edit_input:
                edit_input.focus()
    
    def _save_edit(self, index: int) -> None:
        """Save the edited prompt."""
        if 0 <= index < len(self.prompt_queue):
            edit_input = self.query_one(f"#edit-input-{index}", Input)
            if edit_input and edit_input.value.strip():
                self.prompt_queue[index]['prompt'] = edit_input.value.strip()
                self.app.notify("Prompt updated", severity="information")
            self._editing_index = -1
            self._update_queue_display()
    
    def _cancel_edit(self) -> None:
        """Cancel editing."""
        self._editing_index = -1
        self._update_queue_display()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        # Handle queue-specific buttons first
        if button_id and button_id.startswith('save-'):
            try:
                index = int(button_id.split('-')[1])
                self._save_edit(index)
            except (ValueError, IndexError):
                pass
        elif button_id and button_id.startswith('cancel-'):
            self._cancel_edit()
        elif button_id and button_id.startswith('delete-'):
            try:
                index = int(button_id.split('-')[1])
                self._delete_queue_item(index)
            except (ValueError, IndexError):
                pass
        # Handle main panel buttons
        elif button_id == "submit-btn":
            self.submit_prompt()
        elif button_id == "optimize-btn":
            self.toggle_cost_saver()
        elif button_id == "context-saver-btn":
            self.toggle_context_saver()
        elif button_id == "clear-btn":
            self.clear_prompt()
        elif button_id == "morph-mode-btn":
            self.toggle_morph_mode()
        elif button_id == "clear-queue-btn":
            self.clear_queue()
        elif button_id == "resume-queue-btn":
            self.force_process_queue()
        else:
            # Pass to parent class for any other buttons
            super().on_button_pressed(event)
    
    def _delete_queue_item(self, index: int) -> None:
        """Delete a queue item."""
        if 0 <= index < len(self.prompt_queue):
            self.prompt_queue.pop(index)
            # Adjust highlighted index if needed
            if self.highlighted_queue_index >= len(self.prompt_queue) and self.highlighted_queue_index > 0:
                self.highlighted_queue_index = len(self.prompt_queue) - 1
            # Cancel editing if we're deleting the item being edited
            if self._editing_index == index:
                self._editing_index = -1
            elif self._editing_index > index:
                self._editing_index -= 1
            self._update_queue_display()
            self.app.notify("Prompt removed from queue", severity="information")
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input fields."""
        if event.input.id and event.input.id.startswith('edit-input-'):
            try:
                index = int(event.input.id.split('-')[2])
                self._save_edit(index)
                event.stop()
            except (ValueError, IndexError):
                pass
    
    
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
                    self.cost_saver_btn.label = "● Token Saver"
                    self.cost_saver_btn.add_class("active")
                else:
                    self.cost_saver_btn.label = "○ Token Saver"
                    self.cost_saver_btn.remove_class("active")
                    
        # Restore prompt history
        if 'prompt_history' in state:
            self.prompt_history = state['prompt_history']
            
        if 'history_index' in state:
            self.history_index = state['history_index']
            
        # Restore prompt queue
        if 'prompt_queue' in state:
            self.prompt_queue = state['prompt_queue']
            # Mark queue as paused initially so it doesn't auto-process old prompts
            if self.prompt_queue:
                self._queue_paused = True
                # Reset after a delay to allow manual control
                async def reset():
                    await asyncio.sleep(3.0)
                    self._queue_paused = False
                asyncio.create_task(reset())
            
        if 'highlighted_queue_index' in state:
            self.highlighted_queue_index = state['highlighted_queue_index']
            
        # Restore current prompt text
        if 'current_prompt' in state and hasattr(self, 'prompt_input') and self.prompt_input:
            self.prompt_input.text = state['current_prompt']
            
        # Update queue display if mounted
        if hasattr(self, 'queue_container'):
            self._update_queue_display()
        
        # Queue monitor will be started by on_mount
            
        logging.info(f"PromptPanel state restored: mode={self.selected_mode}, queue_size={len(self.prompt_queue)}")