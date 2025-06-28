"""OSC 52 clipboard support for copying over SSH."""

import base64
import sys
import os

# Store original stderr before any redirection
_original_stderr = sys.__stderr__

def copy_to_clipboard_osc52(text: str) -> bool:
    """Copy text to clipboard using OSC 52 escape sequence.
    
    This works over SSH if your terminal supports OSC 52.
    Supported terminals: iTerm2, Terminal.app (macOS), kitty, alacritty, etc.
    """
    try:
        # Encode text to base64
        encoded = base64.b64encode(text.encode('utf-8')).decode('utf-8')
        
        # Create OSC 52 escape sequence
        # Format: ESC ] 52 ; c ; <base64 encoded text> BEL
        osc52 = f"\033]52;c;{encoded}\a"
        
        # Try to write to /dev/tty first (direct terminal access)
        try:
            with open('/dev/tty', 'w') as tty:
                tty.write(osc52)
                tty.flush()
            return True
        except (OSError, IOError):
            # Fallback to original stderr if /dev/tty not available
            if _original_stderr and hasattr(_original_stderr, 'write'):
                _original_stderr.write(osc52)
                _original_stderr.flush()
                return True
            else:
                # Last resort: try current stderr
                sys.stderr.write(osc52)
                sys.stderr.flush()
                return True
                
    except Exception as e:
        return False

def copy_with_display(text: str) -> str:
    """Copy text and return a display version for user verification.
    
    Returns the text formatted for display in the terminal so users
    can manually copy if OSC 52 doesn't work.
    """
    # Try OSC 52 first
    osc52_success = copy_to_clipboard_osc52(text)
    
    # Format for display
    border = "─" * 60
    display_text = f"""
╭{border}╮
│ COPIED TEXT (select and copy if needed):
├{border}┤
{text}
╰{border}╯
"""
    
    return display_text, osc52_success