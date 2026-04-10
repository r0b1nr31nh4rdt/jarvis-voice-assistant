// Jarvis V2 — Frontend
const orb = document.getElementById('orb');
const statusEl = document.getElementById('status');
const transcript = document.getElementById('transcript');

let ws;
let audioQueue = [];
let isPlaying = false;
let audioUnlocked = false;
let currentAudio = null;

// Unlock audio on ANY user interaction
function unlockAudio() {
    if (!audioUnlocked) {
        const silent = new Audio('data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYZNIGPkAAAAAAAAAAAAAAAAAAAA//tQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAABhgC7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7u7//////////////////////////////////////////////////////////////////8AAAAATGF2YzU4LjEzAAAAAAAAAAAAAAAAJAAAAAAAAAAAAYZNIGPkAAAAAAAAAAAAAAAAAAAA');
        silent.play().then(() => {
            audioUnlocked = true;
            console.log('[jarvis] Audio unlocked');
        }).catch(() => {});
    }
}
document.addEventListener('click', unlockAudio, { once: false });
document.addEventListener('touchstart', unlockAudio, { once: false });
document.addEventListener('keydown', unlockAudio, { once: false });

function connect() {
    const token = window.JARVIS_TOKEN || '';
    ws = new WebSocket(`ws://${location.host}/ws?token=${token}`);
    ws.onopen = () => {
        console.log('[jarvis] WebSocket connected');
        statusEl.textContent = 'Klicke einmal irgendwo, dann spricht Jarvis.';
        setOrbState('thinking');
        ws.send(JSON.stringify({ text: 'Jarvis activate' }));
    };
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'response') {
            addTranscript('jarvis', data.text);
            if (data.audio && data.audio.length > 0) {
                queueAudio(data.audio);
            } else {
                setOrbState('idle');
                setTimeout(startListening, 1500);
            }
        } else if (data.type === 'status') {
            statusEl.textContent = data.text;
        }
    };
    ws.onclose = () => {
        statusEl.textContent = 'Verbindung verloren...';
        setTimeout(connect, 3000);
    };
}

function queueAudio(base64Audio) {
    audioQueue.push(base64Audio);
    if (!isPlaying) playNext();
}

function playNext() {
    if (audioQueue.length === 0) {
        isPlaying = false;
        setOrbState('listening');
        statusEl.textContent = '';
        setTimeout(startListening, 1500);
        return;
    }
    isPlaying = true;
    setOrbState('speaking');
    statusEl.textContent = '';
    if (isListening) { recognition.stop(); isListening = false; }

    const b64 = audioQueue.shift();
    const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    const blob = new Blob([bytes], { type: 'audio/mpeg' });
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    audio.onended = () => { URL.revokeObjectURL(url); currentAudio = null; playNext(); };
    audio.onerror = () => { URL.revokeObjectURL(url); currentAudio = null; playNext(); };
    audio.play().catch(err => {
        console.warn('[jarvis] Autoplay blocked, waiting for click...');
        statusEl.textContent = 'Klicke irgendwo damit Jarvis sprechen kann.';
        setOrbState('idle');
        // Wait for click then retry
        document.addEventListener('click', function retry() {
            document.removeEventListener('click', retry);
            audio.play().then(() => {
                setOrbState('speaking');
                statusEl.textContent = '';
            }).catch(() => playNext());
        });
    });
}

// Speech Recognition
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition;
let isListening = false;

if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.lang = 'de-DE';
    recognition.continuous = true;
    recognition.interimResults = false;

    recognition.onresult = (event) => {
        const last = event.results[event.results.length - 1];
        if (last.isFinal) {
            const text = last[0].transcript.trim();
            if (!text) return;

            // Stop command — halt audio immediately, don't send to server
            if (/^(stop|stopp|halt|aufhören|aufhoeren|schweig|ruhig)$/i.test(text)) {
                if (currentAudio) { currentAudio.pause(); currentAudio = null; }
                audioQueue = [];
                isPlaying = false;
                setOrbState('listening');
                statusEl.textContent = '';
                return;
            }

            // Ignore everything else while audio is playing (avoid feedback)
            if (isPlaying) return;

            addTranscript('user', text);
            setOrbState('thinking');
            statusEl.textContent = 'Jarvis denkt nach...';
            ws.send(JSON.stringify({ text }));
        }
    };

    recognition.onend = () => {
        isListening = false;
        setTimeout(startListening, 300);
    };

    recognition.onerror = (event) => {
        isListening = false;
        if (event.error === 'no-speech' || event.error === 'aborted') {
            setTimeout(startListening, 300);
        } else {
            setTimeout(startListening, 1000);
        }
    };
}

function startListening() {
    try {
        recognition.start();
        isListening = true;
        setOrbState('listening');
        statusEl.textContent = '';
    } catch(e) {}
}

orb.addEventListener('click', () => {
    if (isPlaying) {
        if (currentAudio) { currentAudio.pause(); currentAudio = null; }
        audioQueue = [];
        isPlaying = false;
        setOrbState('listening');
        statusEl.textContent = '';
        return;
    }
    if (isListening) {
        recognition.stop();
        isListening = false;
        setOrbState('idle');
        statusEl.textContent = 'Pausiert. Klicke zum Fortsetzen.';
    } else {
        startListening();
    }
});

function setOrbState(state) { orb.className = state; }

function addTranscript(role, text) {
    const div = document.createElement('div');
    div.className = role;
    div.textContent = role === 'user' ? `Du: ${text}` : `Jarvis: ${text}`;
    transcript.appendChild(div);
    transcript.scrollTop = transcript.scrollHeight;
}

connect();
