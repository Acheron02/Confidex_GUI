#!/bin/bash

# -----------------------------------
# Script to run Confidex and log output
# -----------------------------------

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create logs folder if it doesn't exist
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

# Set log file name with timestamp
LOG_FILE="$LOG_DIR/app_$(date +'%Y%m%d_%H%M%S').log"

# Load environment variables from .env.local
if [ -f "$SCRIPT_DIR/.env.local" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env.local" | xargs)
fi

# Run Python directly from venv (safer than source for .desktop)
"$SCRIPT_DIR/venv/bin/python" "$SCRIPT_DIR/main.py" >> "$LOG_FILE" 2>&1

# Optional: print message when done
echo "Logs saved to $LOG_FILE"