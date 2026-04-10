# Jarvis Setup Guide

Dein persoenlicher KI-Assistent — inspiriert von Iron Mans Jarvis.

**Was du bekommst:**
- Zweimal klatschen → dein komplettes Arbeits-Setup startet
- Jarvis begruesst dich mit Wetter und deinen Aufgaben
- Du sprichst frei mit Jarvis — er antwortet per Stimme
- Jarvis kann deinen Browser steuern (suchen, Seiten oeffnen)
- Jarvis kann deinen Bildschirm sehen und beschreiben

---

## Voraussetzungen

- **macOS**
- **Chrome oder Brave** (fuer Spracheingabe + Jarvis UI — beides funktioniert)
- **Claude Code** installiert

Python, alle Dependencies und Browser-Treiber werden automatisch von Claude Code installiert — du musst nichts manuell einrichten.

---

## Setup starten

Oeffne diesen Ordner in VS Code, starte Claude Code, und sag:

> Richte Jarvis fuer mich ein.

Claude Code fragt dich dann nach:

1. **Dein Name** und wie du angesprochen werden willst (z.B. "Sir")
2. **Deine Taetigkeit** (z.B. "Entwickler", "Designer") — praegt Jarvis Persoenlichkeit
3. **Anthropic API Key** — von https://console.anthropic.com (fuer Claude Haiku, das Gehirn)
4. **ElevenLabs API Key** — von https://elevenlabs.io (fuer die Stimme)
5. **Apple Music Playlist** — Name der Playlist die beim Start spielen soll
6. **Website** — welche Seite soll im Browser aufgehen?
7. **Stadt fuers Wetter** — z.B. Hamburg
8. **Obsidian Vault** — optional, welcher Ordner soll Jarvis kennen?

---

## Was Claude Code fuer dich einrichtet

### 1. Voraussetzungen installieren
Claude Code prueft und installiert automatisch:
- **Python 3.10+** (falls nicht vorhanden: `brew install python`)
- **Alle Python-Pakete** (`pip3 install -r requirements.txt`)
- **Playwright Chromium** (`playwright install chromium`)

### 2. .env erstellen
Claude Code traegt deine Daten in die `.env` Datei ein:
```env
ANTHROPIC_API_KEY=sk-ant-...
ELEVENLABS_API_KEY=sk_...
ELEVENLABS_VOICE_ID=VOICE_ID
USER_NAME=Dein Name
USER_ADDRESS=Sir
USER_ROLE=Deine Taetigkeit
CITY=Hamburg
OBSIDIAN_INBOX_PATH=/Users/dein_user/pfad/zum/obsidian/inbox
APPLE_MUSIC_PLAYLIST=Deine Playlist
BROWSER_URL=https://deine-website.com
```

Alle Werte im Systemprompt (Name, Anrede, Taetigkeit) werden automatisch aus der `.env` geladen — keine manuelle Bearbeitung von `server.py` noetig.

### 3. ElevenLabs Stimme
Eine deutsche Stimme auswaehlen und die Voice ID in die `.env` eintragen. Empfehlung: **Felix Serenitas** (Starter Plan noetig) oder eine der Standard-Stimmen (Free Plan).

---

## Architektur

```
Mikrofon (Chrome/Brave) → Web Speech API → WebSocket → FastAPI Server
                                                            ↓
                                                      Claude Haiku (denkt)
                                                            ↓
                                        ┌─────────────────┼──────────────────┐
                                        ↓                 ↓                  ↓
                                ElevenLabs TTS     Playwright Browser   Screen Capture
                                (spricht)          (sucht/oeffnet)     (sieht Bildschirm)
                                        ↓
                                Audio → Browser Speaker
```

> **Hinweis:** Der Playwright-Browser ist ein separates, isoliertes Chromium-Fenster — er teilt keine Cookies oder Sessions mit deinem persoenlichen Browser.

---

## Starten

### Jarvis manuell starten
```bash
python3 server.py
```
Dann http://localhost:8340 in Chrome oder Brave oeffnen.

### Alles per Doppelklatschen starten
```bash
python3 scripts/clap-trigger.py
```
Zweimal klatschen → Apple Music, VS Code, Obsidian, Chrome mit Jarvis starten automatisch.

### Clap Trigger beim macOS-Start
1. **System Settings → General → Login Items**
2. Skript hinzufuegen, das ausfuehrt:
   ```bash
   python3 /pfad/zu/jarvis-voice-assistant/scripts/clap-trigger.py
   ```

---

## Was Jarvis kann

- **"Wie ist das Wetter?"** → kennt das aktuelle Wetter
- **"Such nach MiroFish"** → oeffnet Browser, sucht, liest Ergebnisse
- **"Oeffne https://example.com"** → oeffnet die Seite im Browser (immer vollstaendige https:// URL angeben)
- **"Was siehst du auf meinem Bildschirm?"** → macht Screenshot, beschreibt was er sieht
- **Jede Frage** → antwortet im Jarvis-Stil mit Stimme

---

## Fehlerbehebung

| Problem | Loesung |
|---|---|
| Jarvis spricht nicht | Pruefen ob Server laeuft (`python3 server.py`) und Browser offen ist |
| "Verbindung verloren" | Alter Server-Prozess laeuft noch → `pkill -f server.py` und neu starten |
| Port 8340 belegt | `lsof -ti:8340 \| xargs kill` ausfuehren |
| Klatschen wird nicht erkannt | Threshold in `clap-trigger.py` anpassen |
| Browser-Suche geht nicht | `playwright install chromium` ausfuehren |
| Kein Audio im Browser | Einmal auf die Seite klicken (Chrome/Brave Autoplay-Policy) |
| "Nur HTTPS-URLs sind erlaubt" | URL mit https:// angeben, z.B. "Oeffne https://example.com" |

---

## Fuer Claude Code: Setup-Anweisungen

Wenn ein Nutzer "Richte Jarvis ein" sagt, fuehre folgende Schritte aus:

**Schritt 0 — Voraussetzungen pruefen und installieren:**
- Pruefe ob Python 3.10+ installiert ist: `python3 --version`
- Falls nicht: `brew install python` — warte bis fertig, pruefe erneut
- Pruefe ob Chrome oder Brave installiert ist. Falls nicht, installiere Chrome via Homebrew: `brew install --cask google-chrome`
- Installiere Python-Pakete: `pip3 install -r requirements.txt`
- Installiere Playwright Browser: `playwright install chromium`

**Schritt 1 — Nutzerdaten abfragen:**
Frage nach:
- Name (z.B. "Robin")
- Taetigkeit/Rolle (z.B. "Entwickler", "Designer") — wird in den Systemprompt eingebaut
- Gewuenschte Anrede (z.B. "Sir", "Chef", oder einfach Vorname)
- Anthropic API Key (von https://console.anthropic.com)
- ElevenLabs API Key (von https://elevenlabs.io)
- Apple Music Playlist (Name der Playlist die beim Start spielen soll)
- Website die im Browser aufgehen soll
- Stadt fuers Wetter (z.B. Hamburg)
- Obsidian Vault Pfad (optional, macOS-Pfad z.B. `/Users/name/Library/Mobile Documents/iCloud~md~obsidian/Documents/vault`)

**Schritt 2 — .env befuellen:**
Trage alle Nutzerdaten in die `.env` Datei ein. Die Datei existiert bereits mit Platzhaltern. Name, Anrede und Taetigkeit werden automatisch in den Systemprompt eingebaut — `server.py` muss NICHT manuell bearbeitet werden.

**Schritt 3 — ElevenLabs Stimme einrichten:**
- Liste verfuegbare Stimmen via ElevenLabs API
- Empfehle eine deutsche Stimme
- Trage die Voice ID in `.env` ein

**Schritt 4 — Testen:**
- Starte den Server: `python3 server.py`
- Oeffne http://localhost:8340 in Chrome oder Brave
- Pruefe ob Jarvis spricht und antwortet

---

## Credits

Template von Julian — [Skool Community](https://skool.com/ki-automatisierung)
