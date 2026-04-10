# CLAUDE.md

Dieses Workspace ist **Jarvis** — ein persoenlicher KI-Assistent mit Sprachsteuerung, Browser-Kontrolle und Doppelklatschen-Trigger.

---

## Fuer Claude Code: Setup-Modus

Wenn der Nutzer nach dem Setup fragt oder "Richte Jarvis ein" sagt, folge den Anweisungen in `SETUP.md`.

**WICHTIG — Pruefe zuerst die `.env` auf bereits eingetragene Werte:**
Lese die `.env` Datei und pruefe ob die Platzhalter (z.B. `your_anthropic_api_key_here`, `your_name_here`) noch vorhanden sind.
- Sind **alle** Werte bereits eingetragen (keine Platzhalter mehr) → frage den Nutzer ob er wirklich neu einrichten moechte, bevor du etwas ueberschreibst.
- Sind **manche** Werte noch Platzhalter → frage nur nach den fehlenden Werten und lasse die bereits eingetragenen unangetastet.
- Ueberschreibe **niemals** einen Wert, der kein Platzhalter mehr ist, ohne ausdrueckliche Bestaetigung des Nutzers.

**WICHTIG — Pruefe und installiere zuerst alle Voraussetzungen:**

1. **Python**: Pruefe ob Python 3.10+ installiert ist (`python3 --version`). Falls nicht, installiere es:
   - macOS: `brew install python`
   - Warte bis die Installation abgeschlossen ist und pruefe erneut

2. **Google Chrome oder Brave**: Pruefe ob Chrome oder Brave installiert ist. Falls nicht, installiere Chrome via Homebrew: `brew install --cask google-chrome`

3. **Virtual Environment**: `python3 -m venv .venv && source .venv/bin/activate`

4. **pip Dependencies**: `pip3 install -r requirements.txt`

5. **Playwright Browser**: `playwright install chromium`

Erst NACHDEM alle Voraussetzungen installiert sind, fahre mit dem Setup in `SETUP.md` fort (API Keys abfragen, .env befuellen, etc.).

---

## Workspace Structure

```
.
├── CLAUDE.md              # This file
├── SETUP.md               # Setup-Anleitung fuer Claude Code
├── .env                   # Persoenliche Config (gitignored)
├── requirements.txt       # Python Dependencies
├── server.py              # FastAPI Backend (Claude Haiku + ElevenLabs TTS)
├── browser_tools.py       # Playwright Browser-Steuerung
├── screen_capture.py      # Screenshot + Claude Vision
├── frontend/
│   ├── index.html         # Jarvis Web-UI
│   ├── main.js            # Speech Recognition + WebSocket + Audio
│   └── style.css          # Dark Theme mit Orb-Animation
└── scripts/
    ├── clap-trigger.py    # Doppelklatschen-Erkennung
    └── launch-session.sh  # Startet alle Apps + Jarvis (macOS)
```
