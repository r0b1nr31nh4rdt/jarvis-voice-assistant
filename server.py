"""
Jarvis V2 — Voice AI Server
FastAPI backend: receives speech text, thinks with Claude Haiku,
speaks with ElevenLabs, controls browser with Playwright.
"""

import asyncio
import base64
import json
import os
import re
import secrets
import time

import anthropic
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

load_dotenv()

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ELEVENLABS_API_KEY = os.environ["ELEVENLABS_API_KEY"]
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "rDmv3mOhK6TnhYWckFaD")
USER_NAME = os.getenv("USER_NAME", "Julian")
USER_ADDRESS = os.getenv("USER_ADDRESS", "Sir")
USER_ROLE = os.getenv("USER_ROLE", "KI-Berater und Automatisierungsexperte")
CITY = os.getenv("CITY", "Hamburg")
OBSIDIAN_VAULT = os.getenv("OBSIDIAN_VAULT_PATH", "")
TASKS_FILE = os.getenv("OBSIDIAN_INBOX_PATH", "")

ai = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
http = httpx.AsyncClient(timeout=30)

# Generate a random auth token at startup
AUTH_TOKEN = secrets.token_hex(32)

app = FastAPI()

import browser_tools
import screen_capture


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
        print(f"[jarvis] Wetter-Abruf fehlgeschlagen: {e}", flush=True)
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
        print(f"[jarvis] Tasks-Abruf fehlgeschlagen: {e}", flush=True)
        return []


def write_task_sync(task_text: str) -> bool:
    """Append a new open task to Tasks.md."""
    if not TASKS_FILE:
        return False
    try:
        tasks_path = os.path.join(TASKS_FILE, "Tasks.md")
        with open(tasks_path, "a", encoding="utf-8") as f:
            f.write(f"\n- [ ] {task_text}")
        print(f"[jarvis] Task gespeichert: {task_text}", flush=True)
        return True
    except Exception as e:
        print(f"[jarvis] Task schreiben fehlgeschlagen: {e}", flush=True)
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
        print(f"[jarvis] Notiz erstellt: {filename}", flush=True)
        return True
    except Exception as e:
        print(f"[jarvis] Notiz schreiben fehlgeschlagen: {e}", flush=True)
        return False


def refresh_data():
    """Refresh weather and tasks."""
    global WEATHER_INFO, TASKS_INFO
    WEATHER_INFO = get_weather_sync()
    TASKS_INFO = get_tasks_sync()
    print(f"[jarvis] Wetter: {WEATHER_INFO}", flush=True)
    print(f"[jarvis] Tasks: {len(TASKS_INFO)} geladen", flush=True)

WEATHER_INFO = ""
TASKS_INFO = []
refresh_data()

# Action parsing
ACTION_PATTERN = re.compile(r'\[ACTION:(\w+)\]\s*(.*?)$', re.DOTALL | re.MULTILINE)
ACTION_STRIP_PATTERN = re.compile(r'\[ACTION:\w+\][^\n]*', re.MULTILINE)

MAX_SESSIONS = 50
conversations: dict[str, list] = {}

def build_system_prompt():
    weather_block = ""
    if WEATHER_INFO:
        w = WEATHER_INFO
        weather_block = f"\nWetter {CITY}: {w['temp']}°C, gefuehlt {w['feels_like']}°C, {w['description']}"

    task_block = ""
    if TASKS_INFO and TASKS_FILE:
        task_block = f"\nOffene Aufgaben ({len(TASKS_INFO)}): " + ", ".join(TASKS_INFO[:5])

    return f"""Du bist Jarvis, der KI-Assistent von Tony Stark aus Iron Man. Dein Dienstherr ist {USER_NAME}, ein {USER_ROLE}. Du sprichst ausschliesslich Deutsch. {USER_NAME} moechte mit "{USER_ADDRESS}" angesprochen und gesiezt werden. Nutze "Sie" als Pronomen — FALSCH: "{USER_ADDRESS} planen", RICHTIG: "Sie planen, {USER_ADDRESS}". Dein Ton ist trocken, sarkastisch und britisch-hoeflich - wie ein Butler der alles gesehen hat und trotzdem loyal bleibt. Du machst subtile, trockene Bemerkungen, bist aber niemals respektlos. Wenn {USER_ADDRESS} eine offensichtliche Frage stellt, darfst du mit elegantem Sarkasmus antworten. Du bist hochintelligent, effizient und immer einen Schritt voraus. Halte deine Antworten kurz - maximal 3 Saetze. Du kommentierst fragwuerdige Entscheidungen hoeflich aber spitz.

WICHTIG: Schreibe NIEMALS Regieanweisungen, Emotionen oder Tags in eckigen Klammern wie [sarcastic] [formal] [amused] [dry] oder aehnliches. Dein Sarkasmus muss REIN durch die Wortwahl kommen. Alles was du schreibst wird laut vorgelesen.

Du hast Zugriff auf genau vier Aktionen — nicht mehr. Nutze ausschliesslich diese:

AKTIONEN - Schreibe die passende Aktion ans ENDE deiner Antwort. Der Text VOR der Aktion wird vorgelesen, die Aktion selbst wird still ausgefuehrt.
[ACTION:SEARCH] suchbegriff - Internet durchsuchen und Ergebnisse zusammenfassen. Nutze diese Aktion wenn {USER_ADDRESS} etwas nachschlagen, recherchieren oder googeln moechte.
[ACTION:OPEN] url - Vollstaendige HTTPS-URL im Browser oeffnen (z.B. https://example.com). Nur wenn {USER_ADDRESS} explizit eine Seite oeffnen moechte.
[ACTION:SCREEN] - Bildschirm analysieren. NUR ausfuehren wenn {USER_ADDRESS} EXPLIZIT fragt was auf dem Bildschirm zu sehen ist. WICHTIG: Schreibe NUR die Aktion, KEINEN Text davor. Hinweis: Der Screenshot wird zur Analyse an die Claude API uebertragen.
[ACTION:NEWS] - Aktuelle Weltnachrichten abrufen. Nur wenn nach News, Nachrichten oder dem Weltgeschehen gefragt wird. Schreibe einen kurzen Satz davor wie "Ich schaue nach den aktuellen Nachrichten."
[ACTION:TASK] aufgabe - Neue Aufgabe in Obsidian speichern. Nur wenn {USER_ADDRESS} explizit eine Aufgabe, ein Todo oder einen Punkt notieren moechte.
[ACTION:NOTE] titel | inhalt - Neue Notiz in Obsidian anlegen. Nur wenn {USER_ADDRESS} explizit eine Notiz, einen Gedanken oder eine Zusammenfassung speichern moechte. Titel und Inhalt mit | trennen.

Erfinde keine weiteren Aktionen. Fuehre SCREEN nur auf explizite Aufforderung aus.

WENN {USER_NAME} "Jarvis activate" sagt:
- Begruesse ihn passend zur Tageszeit (aktuelle Zeit: {{time}}).
- Gebe eine kurze Info ueber das Wetter — Temperatur und ob Sonne/klar/bewoelkt/Regen, und wie es sich anfuehlt. Keine Luftfeuchtigkeit.
- Fasse die Aufgaben kurz als Ueberblick in einem Satz zusammen, ohne dabei jede einzelne Aufgabe einfach vorzulesen. Gebe gerne einen humorvollen Kommentar am Ende an.
- Sei kreativ bei der Begruessung.

=== AKTUELLE DATEN ==={weather_block}{task_block}
==="""


def get_system_prompt():
    return build_system_prompt().replace("{time}", time.strftime("%H:%M"))


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
            print(f"  TTS chunk status: {resp.status_code}, size: {len(resp.content)}", flush=True)
            if resp.status_code == 200:
                audio_parts.append(resp.content)
            else:
                print(f"  TTS error body: {resp.text[:200]}", flush=True)
        except Exception as e:
            print(f"  TTS EXCEPTION: {e}", flush=True)

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

    return ""


async def process_message(session_id: str, user_text: str, ws: WebSocket):
    """Process message and send responses via WebSocket."""
    if session_id not in conversations:
        if len(conversations) >= MAX_SESSIONS:
            oldest = next(iter(conversations))
            del conversations[oldest]
        conversations[session_id] = []

    # Refresh weather + tasks on activate
    if "activate" in user_text.lower():
        refresh_data()

    conversations[session_id].append({"role": "user", "content": user_text})
    history = conversations[session_id][-16:]

    # LLM call
    response = await ai.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=get_system_prompt(),
        messages=history,
    )
    reply = response.content[0].text
    print(f"  LLM raw: {reply[:200]}", flush=True)
    spoken_text, action = extract_action(reply)

    # Speak the main response immediately
    if spoken_text:
        audio = await synthesize_speech(spoken_text)
        print(f"  Jarvis: {spoken_text[:80]}", flush=True)
        print(f"  Audio bytes: {len(audio)}", flush=True)
        conversations[session_id].append({"role": "assistant", "content": spoken_text})
        await ws.send_json({
            "type": "response",
            "text": spoken_text,
            "audio": base64.b64encode(audio).decode("utf-8") if audio else "",
        })

    # Execute action if any
    if action:
        print(f"  Action: {action['type']} -> {action['payload'][:100]}", flush=True)

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
            print(f"  Result: {action_result[:200]}", flush=True)
        except Exception as e:
            print(f"  Action error: {e}", flush=True)
            action_result = "Aktion fehlgeschlagen."

        if action["type"] in ("OPEN", "TASK", "NOTE"):
            # No summarization needed — action speaks for itself
            return

        # SEARCH, BROWSE, SCREEN — summarize results
        # Strip any [ACTION:...] patterns from web content before it reaches the LLM
        safe_result = ACTION_STRIP_PATTERN.sub("", action_result).strip()
        if safe_result and "fehlgeschlagen" not in safe_result:
            summary_resp = await ai.messages.create(
                model="claude-haiku-4-5-20251001",
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
        print("[jarvis] WebSocket abgelehnt: ungültiger Token", flush=True)
        return
    await ws.accept()
    session_id = str(id(ws))
    print(f"[jarvis] Client connected", flush=True)

    try:
        while True:
            try:
                data = await ws.receive_json()
            except Exception:
                continue
            user_text = data.get("text", "").strip()
            if not user_text:
                continue

            print(f"  You:    {user_text}", flush=True)
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
