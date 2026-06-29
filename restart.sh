#!/bin/bash
# DHCP Management Restart Script
# This script kills any running DHCP management instances and starts a fresh one with a watchdog loop

PROJECT_DIR="/home/nutanix/web-dhcp"
LOG_FILE="/tmp/web-dhcp.log"
APP_NAME="web-dhcp"

echo "🔄 Restarting DHCP Management..."

# Kill any existing watchdog loops and processes
echo "🛑 Stopping existing processes..."
pkill -f "${APP_NAME}.*loop" 2>/dev/null || true
pkill -f "gunicorn.*web-dhcp" 2>/dev/null || true

# Wait a moment for processes to terminate
sleep 2

# Verify processes are stopped
if pgrep -f "gunicorn.*web-dhcp" > /dev/null; then
    echo "⚠️  Force killing remaining processes..."
    pkill -9 -f "gunicorn.*web-dhcp" 2>/dev/null || true
    sleep 1
fi

# Change to the project directory
cd $PROJECT_DIR

# Start the watchdog loop in the background
echo "🚀 Starting Flask application with watchdog loop..."
# Use the system python or venv if it exists
PYTHON_BIN="/home/nutanix/web-dns/.venv/bin/gunicorn"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="gunicorn"
fi

nohup bash -c "while true; do 
    $PYTHON_BIN --bind 0.0.0.0:5001 --workers 4 --timeout 300 \
    --access-logfile /tmp/gunicorn-access-web-dhcp.log \
    --error-logfile /tmp/gunicorn-error-web-dhcp.log app:app >> $LOG_FILE 2>&1
    echo \"[\$(date)] App crashed with exit code \$?. Restarting...\" >> $LOG_FILE
    sleep 1
done" > /dev/null 2>&1 &

WATCHDOG_PID=$!

# Wait a moment for watchdog to start
sleep 2

# Check if watchdog is running
if ps -p $WATCHDOG_PID > /dev/null; then
    echo "✅ DHCP Management started successfully with self-healing loop"
    echo "📝 Logs: tail -f $LOG_FILE"
    echo "🌐 URL: http://$(hostname -I | awk '{print $1}'):5001"
    echo ""
    echo "To stop: pkill -f '${APP_NAME}.*loop'"
else
    echo "❌ Failed to start app. Check $LOG_FILE for errors."
    exit 1
fi
