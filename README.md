# SignSpeak 🤟

> Real-time American Sign Language → speech. 100% local — no cloud, no API keys, works offline.

SignSpeak watches your webcam, recognizes ASL gestures and fingerspelling in real time,
and instantly speaks the matching phrase through **Piper neural TTS**. Built for people
who communicate in sign language to be heard — literally — on any Windows laptop.

---

## Features

- **7 whole-hand gestures** (MediaPipe GestureRecognizer) → customizable spoken phrases
- **ASL fingerspelling** — 15 letters (`A B C D E F I L O R S U V W Y`) with majority-vote
  filtering, spelled words are spoken automatically when you pause
- **Piper neural TTS** — offline, natural voice, phrase caching = near-zero latency on repeats
- **Follows your audio device** — speakers, headphones, Bluetooth earbuds; switches automatically
- **Live React UI** — video feed, transcript, event log, editable gesture→phrase snippets
- **Three modes:** Gestures only / ASL spell only / Both
- **One-click launcher** — `run.bat` sets up and starts everything

---

## Quick Start (Windows, one click)

Requirements: **Python 3.11+**, **Node.js 18+**, a webcam.

```bat
git clone https://github.com/saisiddi/Sign_Speak.git
cd Sign_Speak
run.bat
```

`run.bat` automatically:
1. Creates a virtual environment and installs Python deps
2. Downloads Piper TTS + voice model (~60 MB, first time only)
3. Downloads the gesture recognition model (first time only)
4. Installs frontend packages
5. Starts the backend on **http://localhost:8001** and the UI on **http://localhost:5173**

Open **http://localhost:5173** and start signing.

---

## Manual Setup

### Backend

```bash
python -m venv venv
venv\Scripts\pip install -r requirements.txt

python backend\download_model.py        # gesture_recognizer.task

# Piper: download piper_windows_amd64.zip from
#   https://github.com/rhasspy/piper/releases
# and extract piper.exe + DLLs into piper/
# Download the voice model into piper/ from
#   https://huggingface.co/rhasspy/piper-voices  (en_US/lessac/high):
#   en_US-lessac-high.onnx + en_US-lessac-high.onnx.json

cd backend
..\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

---

## Default Gesture → Phrase Map

| Gesture | Spoken phrase |
|---|---|
| ✋ Open Palm | Hello |
| 👍 Thumb Up | Yes |
| 👎 Thumb Down | No |
| ✌️ Victory | Thank you |
| ☝️ Pointing Up | I need help |
| ✊ Closed Fist | Please stop |
| 🤟 I Love You | I love you |

Phrases are fully editable in the UI (**Snippets** page) and stored in `backend/snippets.json`.

## Fingerspelling

Switch to **ASL Spell** or **Both** mode. Hold each letter ~0.3s to accept it
(majority vote over 10 frames). Pause ~1.8s between words — the word is spoken automatically.

Recognized letters: `A B C D E F I L O R S U V W Y`
(letters requiring motion like J/Z and ambiguous ones like M/N are excluded deliberately
to keep recognition reliable.)

---

## How It Works

```
Webcam → MediaPipe GestureRecognizer ─┬─ gesture ──► phrase lookup ─┐
  (640×360 @ 30fps)                   └─ hand landmarks ─► ASL letter rules ─┤
                                                                              ▼
        Browser ◄── WebSocket events ◄── FastAPI backend      Piper TTS (cached) ─► default audio device
```

- `backend/detector.py` — capture → recognition → stability/vote filtering
- `backend/asl_alphabet.py` — geometric rules for static ASL letters
- `backend/tts_bridge.py` — persistent Piper subprocess + phrase cache + device-following playback
- `backend/main.py` — FastAPI server: REST + WebSocket + MJPEG video feed
- `frontend/` — React + Vite UI

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Frontend (serves built app, else status JSON) |
| `GET /health` | Status: TTS backend, camera, fps, mode |
| `WS /ws` | Live detection events (JSON) |
| `GET /video_feed` | MJPEG webcam stream with overlays |
| `POST /speak` | `{"text": "hello"}` → speak now |
| `POST /reset` | Clear text buffer |
| `GET/POST /mode` | `snippets` \| `asl` \| `both` |
| `POST /letters` | Enable/disable fingerspelling |
| `GET/POST /snippets` | View/update gesture→phrase map |
| `POST /snippets/reset` | Restore default phrases |

Interactive docs at **http://localhost:8001/docs**.

---

## Troubleshooting

**Camera not opening** → another app (Zoom/Teams/Camera) may be holding it, or change `CAMERA_ID` in `backend/detector.py`.

**No audio / wrong device** → audio always follows the Windows *default output device*. Set your speaker/earbuds as default; switching works live, no restart needed.

**Gesture not detected** → good lighting, hand 30–80 cm from camera, palm facing the lens.

**Letter flickers** → by design letters need 8/10 frame agreement; hold the shape briefly.

**Port 8001 busy** → `run.bat` already kills leftover instances; or run `taskkill /F /IM python.exe` (careful) / change the port in `run.bat` and `frontend/src/hooks/useWebSocket.js`.

---

## Tech Stack

Python · FastAPI · MediaPipe Tasks · OpenCV · Piper TTS · sounddevice · React 19 · Vite
