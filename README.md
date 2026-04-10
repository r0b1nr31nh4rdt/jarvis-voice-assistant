# J.A.R.V.I.S. — Personal AI Voice Assistant

> Double-clap. Jarvis wakes up, greets you with the weather and your tasks, answers your questions with dry British wit, controls your browser, and sees your screen.

Built entirely with [Claude Code](https://claude.ai/code) — no code written manually.

---

## Youtube Video

[Demo & Explaination](https://youtu.be/XsceN-hEit4)

---

## Features

- **Double-Clap Trigger** — Clap twice and your entire workspace launches: Apple Music, VS Code, Obsidian, Chrome with Jarvis UI
- **Voice Conversation** — Speak freely with Jarvis through your microphone. He listens, thinks, and responds with voice
- **Sarcastic British Butler** — Jarvis speaks German with the personality of Tony Stark's AI: dry, witty, and always one step ahead
- **Weather & Tasks** — On startup, Jarvis greets you with the current weather and a humorous summary of your open tasks from Obsidian
- **Browser Automation** — "Search for MiroFish" → Jarvis opens a real browser, navigates to the page, reads the content, and summarizes it for you
- **Screen Vision** — "What's on my screen?" → Jarvis takes a screenshot, analyzes it with Claude Vision, and describes what he sees
- **World News** — "What's happening in the world?" → Jarvis opens worldmonitor.app and summarizes current global events

---

## Architecture

```
You (speak) → Chrome Browser (Web Speech API) → FastAPI Server (local)
                                                       ↓
                                                Claude Haiku (thinks)
                                                       ↓
                                    ┌──────────────────┼───────────────────┐
                                    ↓                  ↓                   ↓
                             ElevenLabs TTS     Playwright Browser    Screen Capture
                             (speaks back)      (searches/opens)     (Claude Vision)
                                    ↓
                             Audio → Chrome → You (hear)
```

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Speech Input | Web Speech API (Chrome) | Converts your voice to text |
| Server | FastAPI (Python) | Local orchestration — runs on your machine |
| Brain | Claude Haiku (Anthropic) | Thinks, decides, formulates responses |
| Voice | ElevenLabs TTS | Converts text to natural German speech |
| Browser Control | Playwright | Automates a real browser you can see |
| Screen Vision | Claude Vision + Pillow | Screenshots and describes your screen |
| Clap Detection | sounddevice + numpy | Listens for double-clap to launch everything |

---

## Prerequisites

- **macOS**
- **Python 3.10+**
- **Google Chrome**
- **[Claude Code](https://claude.ai/code)** (recommended for setup)

### API Keys Needed

| Service | What For | Cost | Link |
|---------|----------|------|------|
| Anthropic | Claude Haiku (the brain) | ~$0.25 / 1M tokens | [console.anthropic.com](https://console.anthropic.com) |
| ElevenLabs | Voice (text-to-speech) | Free tier: 10k chars/month | [elevenlabs.io](https://elevenlabs.io) |

---

## Quick Start

### Option A: Setup with Claude Code (Recommended)

1. Clone the repo:
   ```bash
   git clone https://github.com/Julian-Ivanov/jarvis-voice-assistant.git
   cd jarvis-voice-assistant
   ```

2. Open in VS Code, start Claude Code, and say:
   ```
   Set up Jarvis for me.
   ```

3. Claude Code will ask for your API keys, name, preferences, and configure everything automatically.

### Option B: Manual Setup

1. **Clone and install dependencies:**
   ```bash
   git clone https://github.com/Julian-Ivanov/jarvis-voice-assistant.git
   cd jarvis-voice-assistant
   pip3 install -r requirements.txt
   playwright install chromium
   ```

2. **Create `.env`** from the template:
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`** with your API keys and preferences:
   ```env
   ANTHROPIC_API_KEY=sk-ant-...
   ELEVENLABS_API_KEY=sk_...
   ELEVENLABS_VOICE_ID=your_voice_id
   USER_NAME=Your Name
   USER_ADDRESS=Sir
   CITY=Hamburg
   OBSIDIAN_INBOX_PATH=/Users/you/path/to/obsidian/inbox
   APPLE_MUSIC_PLAYLIST=Your Playlist
   BROWSER_URL=https://your-website.com
   ```

4. **Start Jarvis:**
   ```bash
   python3 server.py
   ```

5. **Open Chrome** and go to `http://localhost:8340`

6. **Click anywhere** on the page, then speak!

---

## Usage

### Start Jarvis manually
```bash
python3 server.py
```
Then open `http://localhost:8340` in Chrome.

### Start everything with a double-clap
```bash
python3 scripts/clap-trigger.py
```
Clap twice → Apple Music plays, VS Code opens, Obsidian opens, Chrome opens with Jarvis.

### Auto-start on macOS login
1. Open **System Settings → General → Login Items**
2. Add a small shell script or use a launchd plist that runs:
   ```bash
   python3 /path/to/jarvis-voice-assistant/scripts/clap-trigger.py
   ```

---

## What You Can Say

| Command | What Happens |
|---------|-------------|
| *"Good morning, Jarvis"* | Jarvis greets you with weather + tasks |
| *"Search for AI news"* | Opens browser, searches, summarizes results |
| *"Open skool.com"* | Opens the URL in your browser |
| *"What's on my screen?"* | Takes screenshot, describes what he sees |
| *"What's happening in the world?"* | Opens worldmonitor.app, summarizes global news |
| *Any question* | Jarvis answers in his sarcastic butler style |

---

## Project Structure

```
jarvis-voice-assistant/
├── server.py              # FastAPI backend — the brain
├── browser_tools.py       # Playwright browser automation
├── screen_capture.py      # Screenshot + Claude Vision
├── .env                   # Your personal config (gitignored)
├── .env.example           # Template — copy to .env and fill in your values
├── requirements.txt       # Python dependencies
├── frontend/
│   ├── index.html         # Jarvis web UI
│   ├── main.js            # Speech recognition + WebSocket + audio
│   └── style.css          # Dark theme with animated orb
├── scripts/
│   ├── clap-trigger.py    # Double-clap detection
│   └── launch-session.sh  # Launches all apps (macOS)
├── CLAUDE.md              # Instructions for Claude Code
└── SETUP.md               # Detailed setup guide
```

---

## Customization

### Change Jarvis's personality
Edit the system prompt in `server.py` → `build_system_prompt()`. The personality, greeting behavior, and action instructions are all defined there.

### Change which apps launch
Edit `.env`:
```env
APPLE_MUSIC_PLAYLIST=Focus
BROWSER_URL=https://your-website.com
```

### Change the voice
Find a voice on [elevenlabs.io](https://elevenlabs.io), copy the Voice ID, and set it in `.env`:
```env
ELEVENLABS_VOICE_ID=your_voice_id
```

### Change the weather city
```env
CITY=Berlin
```

### Adjust clap sensitivity
In `scripts/clap-trigger.py`:
```python
THRESHOLD = 0.15  # Lower = more sensitive
MAX_GAP = 1.2     # Seconds between claps
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Jarvis doesn't speak | Check if server is running. Kill old process: `pkill -f server.py` then restart |
| "Connection lost" in browser | Old server still running on port 8340. Kill it: `lsof -ti:8340 \| xargs kill` |
| Clap not detected | Lower `THRESHOLD` in `clap-trigger.py` (try 0.10) |
| Browser search fails | Run `playwright install chromium` |
| No audio in Chrome | Click anywhere on the page first (Chrome autoplay policy) |
| Missing `.env` variables | Copy the template values from `.env` and fill in your data |

---

## Tech Stack

- **[FastAPI](https://fastapi.tiangolo.com/)** — Python web framework for the local server
- **[Claude Haiku](https://anthropic.com)** — Fast, affordable AI model (the brain)
- **[ElevenLabs](https://elevenlabs.io)** — Natural text-to-speech (the voice)
- **[Playwright](https://playwright.dev)** — Browser automation
- **[Web Speech API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)** — Browser-native speech recognition
- **[sounddevice](https://python-sounddevice.readthedocs.io/)** — Audio input for clap detection

---

## Credits

Original concept and implementation by [Julian](https://skool.com/ki-automatisierung).

macOS port, security hardening, and `.env` migration by Robin Reinhardt — built with [Claude Code](https://claude.ai/code).

Inspired by Iron Man's J.A.R.V.I.S. — *"At your service, Sir."*

---

## Security Fixes

The following vulnerabilities were identified and fixed in the macOS fork:

### Critical

| # | Vulnerability | Fix |
|---|--------------|-----|
| 1 | **Shell injection** — `APPLE_MUSIC_PLAYLIST` and `BROWSER_URL` were interpolated directly into shell commands | Variables passed via `argv` to AppleScript; Chrome args use a Bash array |
| 2 | **No WebSocket authentication** — any device on the network could connect and control Jarvis | Per-session token (`secrets.token_hex(32)`) injected into served HTML; verified via `secrets.compare_digest` |
| 3 | **Server exposed on all interfaces** — `host="0.0.0.0"` allowed LAN access | Changed to `host="127.0.0.1"` |
| 4 | **Prompt injection via web content** — `[ACTION:...]` tags in scraped pages reached the LLM | Action patterns stripped from web content before the summarization call |
| 5 | **HTTP navigation not blocked** — HTTPS check ran after the page had already loaded | Playwright `page.route()` now aborts all `http://` requests before any content loads |
| 6 | **Exception details leaked to LLM** — full Python exceptions (file paths, stack traces) were forwarded to Claude | Generic error message returned; details logged to console only |

### High

| # | Vulnerability | Fix |
|---|--------------|-----|
| 7 | **No URL validation** — `file://`, `javascript:` and other schemes could be opened | `_require_https()` enforces `https://` on all three browser entry points |
| 8 | **Search query not URL-encoded** — special characters broke the DuckDuckGo URL | `urllib.parse.quote_plus()` applied to all search queries |
| 9 | **Bare `except:` handlers** — swallowed `KeyboardInterrupt`, `SystemExit`, and masked all errors silently | Replaced with `except Exception as e` and explicit logging |
| 10 | **Malformed JSON crashes WebSocket handler** — invalid client data terminated the connection | `receive_json()` wrapped in its own `try/except`; bad messages are discarded |

### Medium

| # | Vulnerability | Fix |
|---|--------------|-----|
| 11 | **Browser pages never closed** — `search_and_read` and `fetch_news` leaked Playwright page objects | `await page.close()` added to `finally` blocks |
| 12 | **`conversations` dict grew unboundedly** — no session limit enabled memory exhaustion | Hard cap of 50 sessions; oldest session evicted when limit is reached |
| 13 | **`CITY` not URL-encoded in weather request** — umlauts and spaces broke the API URL | `urllib.parse.quote()` applied to `CITY` |
| 14 | **Unused imports (`re`, `httpx`)** — dead code increased attack surface | Removed |

---

## License

MIT — use it, modify it, build on it. If you build something cool, let me know!
