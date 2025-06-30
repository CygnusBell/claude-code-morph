#!/usr/bin/env python3
"""Test what Claude CLI outputs when starting."""

import os
import pty
import select
import time

def test_claude_output():
    """Test Claude CLI output directly."""
    print("Starting Claude CLI test...")
    
    # Fork with PTY
    pid, master = pty.fork()
    
    if pid == 0:  # Child process
        # Set up the environment
        os.environ['TERM'] = 'xterm-256color'
        os.environ['LINES'] = '40'
        os.environ['COLUMNS'] = '120'
        
        # Execute Claude CLI
        try:
            os.execvp("claude", ["claude", "--dangerously-skip-permissions"])
        except Exception as e:
            print(f"Failed to start claude: {e}")
            exit(1)
    else:  # Parent process
        print(f"Claude CLI started with PID {pid}")
        
        # Read output for a few seconds
        start_time = time.time()
        output_buffer = b""
        
        while time.time() - start_time < 3:
            # Check if data is available
            ready, _, _ = select.select([master], [], [], 0.1)
            
            if ready:
                try:
                    data = os.read(master, 4096)
                    if data:
                        output_buffer += data
                        # Print raw bytes
                        print(f"\nReceived {len(data)} bytes:")
                        print(f"Raw: {repr(data[:200])}")
                        
                        # Try to decode and print
                        try:
                            text = data.decode('utf-8', errors='replace')
                            print(f"Decoded: {text[:200]}")
                        except:
                            pass
                    else:
                        break
                except:
                    break
        
        # Send a test prompt
        print("\n\nSending test prompt...")
        test_prompt = b"What is 2 + 2?\n"
        os.write(master, test_prompt)
        
        # Read response
        time.sleep(2)
        ready, _, _ = select.select([master], [], [], 0.1)
        if ready:
            try:
                data = os.read(master, 4096)
                print(f"\nResponse received {len(data)} bytes:")
                print(f"Raw: {repr(data[:500])}")
                try:
                    text = data.decode('utf-8', errors='replace')
                    print(f"Decoded:\n{text}")
                except:
                    pass
            except:
                pass
        
        # Clean up
        os.kill(pid, 9)
        os.close(master)
        
if __name__ == "__main__":
    test_claude_output()