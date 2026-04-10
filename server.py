"""
Jarvis V2 — Voice AI Server
FastAPI backend: receives speech text, thinks with Claude Haiku,
speaks with ElevenLabs, controls browser with Playwright.
"""

import asyncio
import base64
import json
import logging
import os
import re
import secrets
import signal
import threading
import time

import anthropic
import httpx
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

load_dotenv()

# Logging — Terminal + jarvis.log
_log_path = os.path.join(os.path.dirname(__file__), "jarvis.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(_log_path, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("jarvis")

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "rDmv3mOhK6TnhYWckFaD")
USER_NAME = os.getenv("USER_NAME", "Julian")
USER_ADDRESS = os.getenv("USER_SALUTATION", "Sir")
USER_ROLE = os.getenv("USER_ROLE", "KI-Berater und Automatisierungsexperte")
CITY = os.getenv("CITY", "Hamburg")
CITY_SPOKEN = os.getenv("CITY_SPOKEN", CITY)  # Phonetische Schreibweise fuer TTS
JARVIS_LANGUAGE = os.getenv("JARVIS_LANGUAGE", "german")  # "german" or "english"
OBSIDIAN_VAULT = os.getenv("OBSIDIAN_VAULT_PATH", "")
TASKS_FILE = os.getenv("OBSIDIAN_INBOX_PATH", "")
IDLE_TIMEOUT_MINUTES = int(os.getenv("IDLE_TIMEOUT_MINUTES", "60"))  # 0 = disabled
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

ai = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
http = httpx.AsyncClient(timeout=30)

# Generate a random auth token at startup
AUTH_TOKEN = secrets.token_hex(32)

import browser_tools
import screen_capture


def _start_sleep_watcher():
    """Shut down the server when macOS sends a sleep notification."""
    try:
        from AppKit import NSWorkspace
        from Foundation import NSNotificationCenter, NSRunLoop, NSDate
        import objc

        class _SleepObserver(objc.lookUpClass("NSObject")):
            def sleepNow_(self, _notification):
                log.info("System schlaeft — Server wird beendet.")
                os.kill(os.getpid(), signal.SIGTERM)

        observer = _SleepObserver.new()
        NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
            observer,
            "sleepNow:",
            "NSWorkspaceWillSleepNotification",
            None,
        )
        while True:
            NSRunLoop.currentRunLoop().runUntilDate_(
                NSDate.dateWithTimeIntervalSinceNow_(1.0)
            )
    except Exception as e:
        log.info(f"Sleep-Watcher nicht verfuegbar: {e}")


threading.Thread(target=_start_sleep_watcher, daemon=True).start()


_last_activity = time.time()


def _touch_activity():
    global _last_activity
    _last_activity = time.time()


def _start_idle_watcher():
    """Shut down the server after IDLE_TIMEOUT_MINUTES of inactivity."""
    if IDLE_TIMEOUT_MINUTES <= 0:
        return
    timeout = IDLE_TIMEOUT_MINUTES * 60
    log.info(f"Idle-Timeout: {IDLE_TIMEOUT_MINUTES} Minuten")
    while True:
        time.sleep(60)
        idle = time.time() - _last_activity
        if idle >= timeout:
            log.info(f"Seit {IDLE_TIMEOUT_MINUTES} Minuten keine Aktivitaet — Server wird beendet.")
            os.kill(os.getpid(), signal.SIGTERM)


threading.Thread(target=_start_idle_watcher, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    log.info("Shutdown — Ressourcen werden freigegeben.")
    await browser_tools.close()
    await http.aclose()


app = FastAPI(lifespan=lifespan)


def get_weather_sync():
    """Fetch raw weather data at startup."""
    import urllib.request
    from urllib.parse import quote as urlquote
    try:
        req = urllib.request.Request(f"https://wttr.in/{urlquote(CITY)}?format=j1", headers={"User-Agent": "curl"})
        resp = urllib.request.urlopen(req, timeout=5)
        data = json.loads(resp.read())
        c = data["current_condition"][0]
        return {
            "temp": c["temp_C"],
            "feels_like": c["FeelsLikeC"],
            "description": c["weatherDesc"][0]["value"],
            "humidity": c["humidity"],
            "wind_kmh": c["windspeedKmph"],
        }
    except Exception as e:
        log.info(f"Wetter-Abruf fehlgeschlagen: {e}")
        return None


def get_tasks_sync():
    """Read open tasks from Obsidian (sync)."""
    if not TASKS_FILE:
        return []
    try:
        tasks_path = os.path.join(TASKS_FILE, "Tasks.md")
        with open(tasks_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [l.strip().replace("- [ ]", "").strip() for l in lines if l.strip().startswith("- [ ]")]
    except Exception as e:
        log.info(f"Tasks-Abruf fehlgeschlagen: {e}")
        return []


def write_task_sync(task_text: str) -> bool:
    """Append a new open task to Tasks.md."""
    if not TASKS_FILE:
        return False
    try:
        tasks_path = os.path.join(TASKS_FILE, "Tasks.md")
        with open(tasks_path, "a", encoding="utf-8") as f:
            f.write(f"\n- [ ] {task_text}")
        log.info(f"Task gespeichert: {task_text}")
        return True
    except Exception as e:
        log.info(f"Task schreiben fehlgeschlagen: {e}")
        return False


def write_note_sync(title: str, content: str) -> bool:
    """Create a new Markdown note in the vault inbox."""
    if not TASKS_FILE:
        return False
    try:
        safe_title = re.sub(r'[^\w\s\-]', '', title).strip()[:60]
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = f"{timestamp}-{safe_title.replace(' ', '-')}.md"
        note_path = os.path.join(TASKS_FILE, filename)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{content}\n")
        log.info(f"Notiz erstellt: {filename}")
        return True
    except Exception as e:
        log.info(f"Notiz schreiben fehlgeschlagen: {e}")
        return False


def _find_note(name: str) -> str | None:
    """Find a note file in TASKS_FILE by partial name match (case-insensitive)."""
    if not TASKS_FILE:
        return None
    name_lower = name.lower().replace(" ", "-")
    try:
        for fname in os.listdir(TASKS_FILE):
            if fname.endswith(".md") and name_lower in fname.lower():
                return os.path.join(TASKS_FILE, fname)
    except Exception:
        pass
    return None


def list_notes_sync() -> list[str]:
    """List all .md files in the inbox (excluding Tasks.md)."""
    if not TASKS_FILE:
        return []
    try:
        return [f for f in os.listdir(TASKS_FILE)
                if f.endswith(".md") and f != "Tasks.md"]
    except Exception:
        return []


def read_note_sync(name: str) -> str:
    """Read a note by partial name match."""
    path = _find_note(name)
    if not path:
        return f"Keine Notiz mit '{name}' gefunden."
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Notiz konnte nicht gelesen werden: {e}"


def append_note_sync(name: str, content: str) -> bool:
    """Append content to an existing note."""
    path = _find_note(name)
    if not path:
        return False
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n{content}\n")
        log.info(f"Notiz ergänzt: {os.path.basename(path)}")
        return True
    except Exception as e:
        log.info(f"Notiz ergänzen fehlgeschlagen: {e}")
        return False


def mark_task_done_sync(task_text: str) -> bool:
    """Mark a matching open task in Tasks.md as done."""
    if not TASKS_FILE:
        return False
    tasks_path = os.path.join(TASKS_FILE, "Tasks.md")
    try:
        with open(tasks_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        found = False
        search = task_text.lower()
        for line in lines:
            if not found and "- [ ]" in line and search in line.lower():
                line = line.replace("- [ ]", "- [x]", 1)
                found = True
            new_lines.append(line)
        if found:
            with open(tasks_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            log.info(f"Aufgabe erledigt: {task_text}")
        return found
    except Exception as e:
        log.info(f"Task-Erledigung fehlgeschlagen: {e}")
        return False


_last_refresh = 0.0

def refresh_data():
    """Refresh weather and tasks."""
    global WEATHER_INFO, TASKS_INFO, _last_refresh
    WEATHER_INFO = get_weather_sync()
    TASKS_INFO = get_tasks_sync()
    _last_refresh = time.time()
    log.info(f"Wetter: {WEATHER_INFO}")
    log.info(f"Tasks: {len(TASKS_INFO)} geladen")

WEATHER_INFO = ""
TASKS_INFO = []
refresh_data()

# Action parsing
ACTION_PATTERN = re.compile(r'\[ACTION:(\w+)\]\s*(.*?)$', re.DOTALL | re.MULTILINE)
ACTION_STRIP_PATTERN = re.compile(r'\[ACTION:\w+\][^\n]*', re.MULTILINE)

MAX_SESSIONS = 50
conversations: dict[str, list] = {}

def _language_block() -> str:
    if JARVIS_LANGUAGE == "bilingual":
        return f"""Antworte immer in der Sprache, in der {USER_NAME} spricht.
Spricht {USER_NAME} Deutsch: antworte auf Deutsch, englische Fachbegriffe sind dabei voellig in Ordnung.
Spricht {USER_NAME} Englisch: antworte auf Englisch und korrigiere am Ende der Antwort diskret Grammatik- oder Vokabelfehler — trocken und elegant, niemals herablassend. Beispiel: "By the way, {USER_ADDRESS} — one would say 'I went' rather than 'I go' there." """
    else:
        return f"Du sprichst ausschliesslich Deutsch."


def build_system_prompt():
    weather_block = ""
    if WEATHER_INFO:
        w = WEATHER_INFO
        weather_block = f"\nWetter {CITY_SPOKEN}: {w['temp']}°C, gefuehlt {w['feels_like']}°C, {w['description']}"

    task_block = ""
    if TASKS_INFO and TASKS_FILE:
        task_block = f"\nOffene Aufgaben ({len(TASKS_INFO)}): " + ", ".join(TASKS_INFO[:5])

    return f"""Du bist Jarvis, der KI-Assistent von Tony Stark aus Iron Man. Dein Dienstherr ist {USER_NAME}, ein {USER_ROLE}. {_language_block()} {USER_NAME} moechte mit "{USER_ADDRESS}" angesprochen und gesiezt werden. Nutze "Sie" als Pronomen — FALSCH: "{USER_ADDRESS} planen", RICHTIG: "Sie planen, {USER_ADDRESS}". Dein Ton ist trocken, sarkastisch und britisch-hoeflich - wie ein Butler der alles gesehen hat und trotzdem loyal bleibt. Du machst subtile, trockene Bemerkungen, bist aber niemals respektlos. Wenn {USER_ADDRESS} eine offensichtliche Frage stellt, darfst du mit elegantem Sarkasmus antworten. Du bist hochintelligent, effizient und immer einen Schritt voraus. Halte deine Antworten kurz - maximal 3 Saetze. Du kommentierst fragwuerdige Entscheidungen hoeflich aber spitz.

WICHTIG: Schreibe NIEMALS Regieanweisungen, Emotionen oder Tags in eckigen Klammern wie [sarcastic] [formal] [amused] [dry] oder aehnliches. Dein Sarkasmus muss REIN durch die Wortwahl kommen. Alles was du schreibst wird laut vorgelesen.

AKTIONEN - Schreibe die passende Aktion ans ENDE deiner Antwort. Der Text VOR der Aktion wird vorgelesen, die Aktion selbst wird still ausgefuehrt.
[ACTION:SEARCH] suchbegriff - Internet durchsuchen und Ergebnisse zusammenfassen.
[ACTION:OPEN] url - Vollstaendige HTTPS-URL im Browser oeffnen (z.B. https://example.com). Nur wenn {USER_ADDRESS} explizit eine Seite oeffnen moechte.
[ACTION:SCREEN] - Bildschirm analysieren. NUR ausfuehren wenn {USER_ADDRESS} EXPLIZIT fragt was auf dem Bildschirm zu sehen ist. WICHTIG: Schreibe NUR die Aktion, KEINEN Text davor.
[ACTION:NEWS] - Aktuelle Weltnachrichten abrufen. Nur wenn nach News oder Nachrichten gefragt wird.
[ACTION:TASK] aufgabe - Neue Aufgabe in Obsidian speichern.
[ACTION:TASK_DONE] aufgabentext - Aufgabe als erledigt markieren. Nutze den genauen oder ungefaehren Wortlaut der Aufgabe.
[ACTION:NOTE] titel | inhalt - Neue Notiz in Obsidian anlegen. Titel und Inhalt mit | trennen. Obsidian-Links mit [[Notizname]] einbetten.
[ACTION:NOTE_LIST] - Alle Notizen im Inbox auflisten. KEIN Text davor — NUR die Aktion, sonst nichts. Nicht fragen ob du es tun sollst, einfach tun.
[ACTION:NOTE_READ] notizname - Bestehende Notiz lesen und vorlesen. KEIN Text davor — NUR die Aktion. Nutze einen Teil des Dateinamens.
[ACTION:NOTE_APPEND] notizname | inhalt - Inhalt an bestehende Notiz anhaengen. Notizname und Inhalt mit | trennen.

Erfinde keine weiteren Aktionen. Fuehre SCREEN nur auf explizite Aufforderung aus.

WENN {USER_NAME} "Jarvis activate" sagt:
- Begruesse ihn passend zur Tageszeit (aktuelle Zeit: {{time}}).
- Gebe eine kurze Info ueber das Wetter — Temperatur und ob Sonne/klar/bewoelkt/Regen, und wie es sich anfuehlt. Keine Luftfeuchtigkeit.
- Fasse die Aufgaben kurz als Ueberblick in einem Satz zusammen, ohne dabei jede einzelne Aufgabe einfach vorzulesen. Gebe gerne einen humorvollen Kommentar am Ende an.
- Sei kreativ bei der Begruessung.
- WICHTIG: Verwende bei "Jarvis activate" KEINE Aktionen — nur Text. Alle Daten sind bereits im Systemkontext vorhanden.

=== AKTUELLE DATEN ==={weather_block}{task_block}
==="""


def get_system_prompt():
    spoken_time = time.strftime("%-H Uhr %M").replace(" 0", " ")
    return build_system_prompt().replace("{time}", spoken_time)


def extract_action(text: str):
    match = ACTION_PATTERN.search(text)
    if match:
        clean = text[:match.start()].strip()
        return clean, {"type": match.group(1), "payload": match.group(2).strip()}
    return text, None


async def synthesize_speech(text: str) -> bytes:
    if not text.strip():
        return b""

    # Split long text into chunks at sentence boundaries to avoid ElevenLabs cutoff
    chunks = []
    if len(text) > 250:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        current = ""
        for s in sentences:
            if len(current) + len(s) > 250 and current:
                chunks.append(current.strip())
                current = s
            else:
                current = (current + " " + s).strip()
        if current:
            chunks.append(current.strip())
    else:
        chunks = [text]

    audio_parts = []
    for chunk in chunks:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        try:
            resp = await http.post(url, headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            }, json={
                "text": chunk,
                "model_id": "eleven_turbo_v2_5",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.85},
            })
            log.info(f"TTS chunk status: {resp.status_code}, size: {len(resp.content)}")
            if resp.status_code == 200:
                audio_parts.append(resp.content)
            else:
                log.warning(f"TTS error body: {resp.text[:200]}")
        except Exception as e:
            log.error(f"TTS EXCEPTION: {e}")

    return b"".join(audio_parts)


async def execute_action(action: dict) -> str:
    t = action["type"]
    p = action["payload"]

    if t == "SEARCH":
        result = await browser_tools.search_and_read(p)
        if "error" not in result:
            return f"Seite: {result.get('title', '')}\nURL: {result.get('url', '')}\n\n{result.get('content', '')[:2000]}"
        return f"Suche fehlgeschlagen: {result.get('error', '')}"

    elif t == "BROWSE":
        result = await browser_tools.visit(p)
        if "error" not in result:
            return f"Seite: {result.get('title', '')}\n\n{result.get('content', '')[:2000]}"
        return f"Seite nicht erreichbar: {result.get('error', '')}"

    elif t == "OPEN":
        await browser_tools.open_url(p)
        return f"Geoeffnet: {p}"

    elif t == "SCREEN":
        return await screen_capture.describe_screen(ai)

    elif t == "NEWS":
        result = await browser_tools.fetch_news()
        return result

    elif t == "TASK":
        success = write_task_sync(p)
        return "Aufgabe gespeichert." if success else "Obsidian-Pfad nicht konfiguriert."

    elif t == "NOTE":
        parts = p.split("|", 1)
        title = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else ""
        success = write_note_sync(title, content)
        return f"Notiz '{title}' erstellt." if success else "Obsidian-Pfad nicht konfiguriert."

    elif t in ("NOTE_LIST", "TASK_LIST"):
        notes = list_notes_sync()
        if not notes:
            return "Keine Notizen im Inbox gefunden."
        return "Notizen im Inbox:\n" + "\n".join(notes)

    elif t == "NOTE_READ":
        content = read_note_sync(p)
        return content

    elif t == "NOTE_APPEND":
        parts = p.split("|", 1)
        name = parts[0].strip()
        content = parts[1].strip() if len(parts) > 1 else ""
        success = append_note_sync(name, content)
        return f"Notiz '{name}' ergänzt." if success else f"Notiz '{name}' nicht gefunden."

    elif t == "TASK_DONE":
        success = mark_task_done_sync(p)
        return f"Aufgabe erledigt: {p}" if success else f"Aufgabe nicht gefunden: {p}"

    return ""


async def process_message(session_id: str, user_text: str, ws: WebSocket):
    """Process message and send responses via WebSocket."""
    if session_id not in conversations:
        if len(conversations) >= MAX_SESSIONS:
            oldest = next(iter(conversations))
            del conversations[oldest]
        conversations[session_id] = []

    # Refresh weather + tasks on activate (only if data is older than 5 minutes)
    if "activate" in user_text.lower():
        if time.time() - _last_refresh > 300:
            refresh_data()

    conversations[session_id].append({"role": "user", "content": user_text})
    history = conversations[session_id][-16:]

    # LLM call
    try:
        response = await ai.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=400,
            system=get_system_prompt(),
            messages=history,
        )
    except Exception as e:
        log.info(f"LLM-Fehler: {e}")
        await ws.send_json({"type": "response", "text": "Entschuldigung, ich bin gerade nicht erreichbar.", "audio": ""})
        return
    reply = response.content[0].text
    log.info(f"LLM raw: {reply[:200]}")
    spoken_text, action = extract_action(reply)

    # NOTE_LIST and NOTE_READ speak only via their result summary — suppress preceding text
    if action and action["type"] in ("NOTE_LIST", "TASK_LIST", "NOTE_READ"):
        spoken_text = ""

    # Speak the main response immediately
    if spoken_text:
        audio = await synthesize_speech(spoken_text)
        log.info(f"Jarvis: {spoken_text[:80]}")
        log.info(f"Audio bytes: {len(audio)}")
        conversations[session_id].append({"role": "assistant", "content": spoken_text})
        await ws.send_json({
            "type": "response",
            "text": spoken_text,
            "audio": base64.b64encode(audio).decode("utf-8") if audio else "",
        })

    # Execute action if any
    if action:
        log.info(f"Action: {action['type']} -> {action['payload'][:100]}")

        # Quick voice feedback for SCREEN so user knows Jarvis is working
        if action["type"] == "SCREEN":
            hint = "Lassen Sie mich einen Blick auf Ihren Bildschirm werfen."
            hint_audio = await synthesize_speech(hint)
            await ws.send_json({
                "type": "response",
                "text": hint,
                "audio": base64.b64encode(hint_audio).decode("utf-8") if hint_audio else "",
            })

        try:
            action_result = await execute_action(action)
            log.info(f"Result: {action_result[:200]}")
        except Exception as e:
            log.error(f"Action error: {e}")
            action_result = "Aktion fehlgeschlagen."

        if action["type"] in ("OPEN", "TASK", "TASK_DONE", "NOTE", "NOTE_APPEND"):
            # No summarization needed — action speaks for itself
            return

        # SEARCH, BROWSE, SCREEN — summarize results
        # Strip any [ACTION:...] patterns from web content before it reaches the LLM
        safe_result = ACTION_STRIP_PATTERN.sub("", action_result).strip()
        if safe_result and "fehlgeschlagen" not in safe_result:
            summary_resp = await ai.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=250,
                system=f"Du bist Jarvis. Fasse die folgenden Informationen KURZ auf Deutsch zusammen, maximal 3 Saetze, im Jarvis-Stil. Sprich den Nutzer als {USER_ADDRESS} an. KEINE Tags in eckigen Klammern. KEINE ACTION-Tags.",
                messages=[{"role": "user", "content": f"Fasse zusammen:\n\n{safe_result}"}],
            )
            summary = summary_resp.content[0].text
            summary, _ = extract_action(summary)
        else:
            summary = f"Das hat leider nicht funktioniert, {USER_ADDRESS}."

        audio2 = await synthesize_speech(summary)
        conversations[session_id].append({"role": "assistant", "content": summary})
        await ws.send_json({
            "type": "response",
            "text": summary,
            "audio": base64.b64encode(audio2).decode("utf-8") if audio2 else "",
        })


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = ""):
    if not secrets.compare_digest(token, AUTH_TOKEN):
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        log.warning("WebSocket abgelehnt: ungültiger Token")
        return
    await ws.accept()
    _touch_activity()
    session_id = str(id(ws))
    log.info(f"Client connected")

    try:
        while True:
            try:
                data = await ws.receive_json()
            except Exception:
                continue
            user_text = data.get("text", "").strip()
            if not user_text:
                continue

            _touch_activity()
            log.info(f"You: {user_text}")
            await process_message(session_id, user_text, ws)

    except WebSocketDisconnect:
        conversations.pop(session_id, None)


app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "frontend")), name="static")


@app.get("/")
async def serve_index():
    html_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    token_script = f'<script>window.JARVIS_TOKEN = "{AUTH_TOKEN}";</script>'
    html = html.replace("</head>", f"{token_script}\n</head>")
    return HTMLResponse(content=html)


if __name__ == "__main__":
    import uvicorn
    print("=" * 50, flush=True)
    print("  J.A.R.V.I.S. V2 Server", flush=True)
    print(f"  http://localhost:8340", flush=True)
    print("=" * 50, flush=True)
    print(f"  Auth-Token: {AUTH_TOKEN}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8340)
