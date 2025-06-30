#!/usr/bin/env python3
"""Check pyte response more carefully."""

import pyte
import os
import pty
import select
import time

def check_pyte_response():
    """Check pyte response in detail."""
    # Create pyte screen  
    screen = pyte.Screen(120, 40)
    stream = pyte.ByteStream(screen)
    
    # Start Claude
    pid, master = pty.fork()
    
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.execvp("claude", ["claude", "--dangerously-skip-permissions"])
    else:
        import fcntl
        flags = fcntl.fcntl(master, fcntl.F_GETFL)
        fcntl.fcntl(master, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        # Wait and clear initial
        time.sleep(2)
        while True:
            try:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    data = os.read(master, 4096)
                    stream.feed(data)
                else:
                    break
            except:
                break
        
        # Send prompt
        prompt = "Say exactly: Hi from pyte!"
        os.write(master, b'\x15')  # Clear line
        os.write(master, prompt.encode('utf-8'))
        os.write(master, b'\n')
        
        # Collect response with timestamps
        print("Collecting response...")
        start = time.time()
        updates = []
        
        while time.time() - start < 8:
            try:
                ready, _, _ = select.select([master], [], [], 0.1)
                if ready:
                    data = os.read(master, 4096)
                    if data:
                        stream.feed(data)
                        # Capture screen state
                        screen_text = '\n'.join(screen.display)
                        updates.append({
                            'time': time.time() - start,
                            'data_len': len(data),
                            'has_response': 'Hi from pyte' in screen_text
                        })
            except:
                pass
        
        # Show updates
        print("\nUpdate timeline:")
        for u in updates:
            print(f"  {u['time']:.2f}s: {u['data_len']} bytes, response={u['has_response']}")
        
        # Show final screen with line numbers
        print("\nFinal screen (non-empty lines):")
        for i, line in enumerate(screen.display):
            if line.strip():
                print(f"  Line {i:2d}: {repr(line)}")
        
        # Look for Claude's response more carefully
        found_response = False
        for i, line in enumerate(screen.display):
            if 'Hi from pyte' in line:
                print(f"\n✓ Found response on line {i}: {line.strip()}")
                found_response = True
                
        if not found_response:
            # Check if response might be split across lines
            full_text = ' '.join(screen.display)
            if 'Hi from pyte' in full_text:
                print("\n✓ Found response (split across lines)")
            else:
                print("\n✗ No response found")
        
        # Cleanup
        os.kill(pid, 15)
        os.close(master)

if __name__ == "__main__":
    check_pyte_response()