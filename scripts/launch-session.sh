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
    do script "cd '$PROJECT_DIR' && source .venv/bin/activate && python3 server.py"
end tell
EOF

# 2. Open Apple Music (optional — plays playlist if set, otherwise just opens)
# Variable passed via argv, never interpolated into the AppleScript string
if [ -n "${APPLE_MUSIC_PLAYLIST:-}" ]; then
    osascript -e 'on run argv' \
              -e 'tell application "Music" to play playlist (item 1 of argv)' \
              -e 'end run' \
              -- "$APPLE_MUSIC_PLAYLIST"
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
# Use array to prevent word-splitting and injection via BROWSER_URL
CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_ARGS=(
    "--profile-directory=Jarvis"
    "--no-first-run"
    "--no-default-browser-check"
    "--autoplay-policy=no-user-gesture-required"
    "--disable-background-timer-throttling"
    "--disable-tab-discarding"
    "http://localhost:8340"
)
if [ -n "${BROWSER_URL:-}" ]; then
    CHROME_ARGS+=("$BROWSER_URL")
fi
"$CHROME_BIN" "${CHROME_ARGS[@]}" &

# 6. Apply Rectangle Pro layout (after apps have opened)
RECTANGLE_LAYOUT="${RECTANGLE_LAYOUT:-Jarvis}"
sleep 2
open "rectangle-pro://layout?name=${RECTANGLE_LAYOUT}"
