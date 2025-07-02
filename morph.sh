#!/bin/bash
# Run morph with automatic venv activation and crash detection

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate the virtual environment
if [[ -d "$SCRIPT_DIR/venv" ]]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/venv/bin/activate"
else
    echo "Error: Virtual environment not found at $SCRIPT_DIR/venv"
    exit 1
fi

# Function to check for recent errors in main.log
check_for_errors() {
    if [[ -f "$SCRIPT_DIR/main.log" ]]; then
        # Check for errors in the last 100 lines that occurred in the last 5 seconds
        local recent_errors=$(tail -n 100 "$SCRIPT_DIR/main.log" | grep -E "ERROR.*Error|Exception|Traceback" | tail -n 5)
        if [[ -n "$recent_errors" ]]; then
            # Check if the error timestamp is recent (within last 10 seconds)
            local last_error_time=$(echo "$recent_errors" | tail -n 1 | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")
            if [[ -n "$last_error_time" ]]; then
                local error_epoch=$(date -d "$last_error_time" +%s 2>/dev/null || echo "0")
                local current_epoch=$(date +%s)
                local time_diff=$((current_epoch - error_epoch))
                
                # If error occurred within last 10 seconds, it's likely from the crash
                if [[ $time_diff -lt 10 ]]; then
                    return 0  # Recent error found
                fi
            fi
        fi
    fi
    return 1  # No recent errors
}

# Main loop with crash detection
while true; do
    echo "Starting Claude Code Morph..."
    
    # Run morph and capture exit code
    morph "$@"
    exit_code=$?
    
    # Check if morph crashed (non-zero exit code)
    if [[ $exit_code -ne 0 ]]; then
        echo ""
        
        # Check if safe mode was requested (exit code 99 or flag file)
        if [[ $exit_code -eq 99 ]] || [[ -f "$SCRIPT_DIR/.safe_mode_requested" ]]; then
            echo "🔧 Safe Mode requested"
            rm -f "$SCRIPT_DIR/.safe_mode_requested" 2>/dev/null
            echo "Launching Safe Mode..."
            python "$SCRIPT_DIR/safe_mode.py"
            # Safe mode will handle restarting morph
            break
        fi
        
        echo "⚠️  Morph exited with error code: $exit_code"
        
        # Check for recent errors in log
        if check_for_errors; then
            echo "🔧 Recent errors detected in main.log"
            echo ""
            echo "Would you like to:"
            echo "1. Launch Safe Mode to fix errors"
            echo "2. Try running morph again"
            echo "3. Exit"
            echo ""
            read -p "Your choice (1-3) [default: 1]: " choice
            
            case "${choice:-1}" in
                1)
                    echo "Launching Safe Mode..."
                    python "$SCRIPT_DIR/safe_mode.py"
                    # Safe mode will handle restarting morph
                    break
                    ;;
                2)
                    echo "Restarting morph..."
                    sleep 1
                    continue
                    ;;
                *)
                    echo "Exiting..."
                    exit $exit_code
                    ;;
            esac
        else
            # No recent errors, might be intentional exit
            echo ""
            read -p "Restart morph? (y/N): " restart
            if [[ "${restart,,}" == "y" ]]; then
                echo "Restarting morph..."
                sleep 1
                continue
            else
                exit $exit_code
            fi
        fi
    else
        # Normal exit (user pressed Ctrl+Q or similar)
        break
    fi
done