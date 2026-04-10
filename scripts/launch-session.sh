#!/usr/bin/env bash
# Jarvis — Launch Session (macOS)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load .env
set -a
source "$PROJECT_DIR/.env"
set +a

# 1. Start server in a new Terminal window
osascript <<EOF
tell application "Terminal"
    do script "cd '$PROJECT_DIR' && python server.py"
    activate
end tell
EOF

# 2. Open Apple Music (optional — plays playlist if set, otherwise just opens)
if [ -n "${APPLE_MUSIC_PLAYLIST:-}" ]; then
    osascript -e "tell application \"Music\" to play playlist \"$APPLE_MUSIC_PLAYLIST\""
else
    open -a "Music"
fi

# 3. Open VS Code
if command -v code &>/dev/null; then
    code "$PROJECT_DIR"
fi

# 4. Open Obsidian (optional)
if [ -n "${OBSIDIAN_INBOX_PATH:-}" ]; then
    open -a "Obsidian" 2>/dev/null || true
fi

# 5. Wait for server to start, then open Chrome
sleep 3
CHROME_ARGS="--autoplay-policy=no-user-gesture-required http://localhost:8340"
if [ -n "${BROWSER_URL:-}" ]; then
    CHROME_ARGS="$CHROME_ARGS $BROWSER_URL"
fi
open -a "Google Chrome" --args $CHROME_ARGS
