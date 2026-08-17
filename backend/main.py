"""
SignSpeak - FastAPI Server
==========================
Endpoints:
  GET  /              → serves frontend (static files)
  GET  /health        → health check
  WS   /ws            → WebSocket: sends detection events as JSON
  GET  /video_feed    → MJPEG stream (for embedding in <img> tag)
  POST /speak         → manually trigger TTS
  POST /reset         → clear text buffer

Run with:
  cd backend
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import asyncio
import base64
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from detector import SignDetector
from snippets import load_snippets, save_snippets, get_phrase, reset_to_defaults, DEFAULT_SNIPPETS
from tts_bridge import TTSBridge


# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="SignSpeak", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # local only, fine for expo
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve React build if it exists
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")


# ── Global state ─────────────────────────────────────────────────────────────
detector      = SignDetector()
tts           = TTSBridge()
active_ws     : list[WebSocket] = []
latest_frame  = None            # shared between camera thread and video_feed endpoint
frame_lock    = threading.Lock()
camera_running = False
event_loop    = None            # captured at startup, used by _broadcast


@app.on_event("startup")
async def _capture_loop():
    global event_loop
    event_loop = asyncio.get_running_loop()


# ── Wire detector callbacks → TTS + WebSocket broadcast ──────────────────────
def _on_sign_confirmed(sign: str):
    payload = {"type": "sign", "sign": sign, "text": detector.text_buffer}
    _broadcast(payload)

def _on_text_updated(text: str):
    payload = {"type": "text", "text": text}
    _broadcast(payload)

def _on_speak_trigger(word: str):
    print(f"[TTS] Speaking: '{word}'")
    tts.speak(word)
    payload = {"type": "speak", "word": word}
    _broadcast(payload)

detector.on_sign_confirmed = _on_sign_confirmed
detector.on_text_updated   = _on_text_updated
detector.on_speak_trigger  = _on_speak_trigger

# Pre-synthesize all assigned phrases so gesture triggers speak from cache
tts.prewarm(load_snippets().values())


def _broadcast(payload: dict):
    """Send JSON to all connected WebSocket clients (thread-safe via asyncio)."""
    msg = json.dumps(payload)
    loop = event_loop
    if loop is None:
        return
    for ws in active_ws.copy():
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(msg), loop)
        except Exception:
            pass


# ── Camera thread ─────────────────────────────────────────────────────────────
# Recognition and streaming run on a downscaled frame — 4x cheaper per frame
# than 1280x720 with negligible detection impact, keeping CPU low enough for
# smooth video and on-time audio callbacks.
PROC_WIDTH, PROC_HEIGHT = 640, 360


def _camera_thread():
    global latest_frame, camera_running
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    # Low-res high-fps capture — recognition runs at this size anyway, and
    # small frames keep the sensor's frame rate up in dim lighting.
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, PROC_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, PROC_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, 30)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print("ERROR: Cannot open camera.")
        return

    camera_running = True
    print("[Camera] Started")

    while camera_running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.01)
            continue

        frame = cv2.flip(frame, 1)
        if frame.shape[1] != PROC_WIDTH:
            small = cv2.resize(frame, (PROC_WIDTH, PROC_HEIGHT))
        else:
            small = frame
        result = detector.process_frame(small)

        # Encode frame to JPEG
        _, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 88])
        with frame_lock:
            latest_frame = buf.tobytes()

    cap.release()
    print("[Camera] Stopped")


# Start camera on launch
threading.Thread(target=_camera_thread, daemon=True).start()


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    index = frontend_dist / "index.html"
    if index.exists():
        return HTMLResponse(index.read_text())
    return JSONResponse({"status": "SignSpeak backend running", "docs": "/docs"})


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "tts_backend": tts._backend,
        "camera": camera_running,
        "fps": round(detector.fps, 1),
        "mode": detector.mode,
        "letters": detector.letters_enabled,
        "buffer": detector.text_buffer,
    }


class ModeRequest(BaseModel):
    mode: str


@app.get("/mode")
async def get_mode():
    return {"mode": detector.mode}


@app.post("/mode")
async def set_mode(req: ModeRequest):
    """Switch recognition mode: 'snippets' (gestures only),
    'asl' (fingerspelling only), or 'both'."""
    if req.mode not in ("snippets", "asl", "both"):
        return JSONResponse({"error": "mode must be snippets, asl or both"}, status_code=400)
    detector.mode = req.mode
    detector.reset_spelling()
    detector.current_sign = None
    detector.sign_hold_count = 0
    print(f"[Mode] {req.mode}")
    _broadcast({"type": "mode", "mode": req.mode})
    return {"mode": detector.mode}


class LettersToggle(BaseModel):
    enabled: bool


@app.post("/letters")
async def toggle_letters(req: LettersToggle):
    """Enable/disable ASL fingerspelling recognition."""
    detector.letters_enabled = req.enabled
    if not req.enabled:
        detector.reset_spelling()
    return {"letters": detector.letters_enabled}


@app.get("/video_feed")
async def video_feed():
    """MJPEG stream — embed as <img src='http://localhost:8000/video_feed'>"""
    def generate():
        while True:
            with frame_lock:
                frame = latest_frame
            if frame:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            time.sleep(1 / 30)

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_ws.append(ws)
    print(f"[WS] Client connected ({len(active_ws)} active)")

    # Send current state immediately on connect
    await ws.send_text(json.dumps({
        "type": "init",
        "text": detector.text_buffer,
        "tts_backend": tts._backend,
    }))

    try:
        while True:
            try:
                # Keep connection alive, handle incoming messages
                data = await asyncio.wait_for(ws.receive_text(), timeout=20)
            except asyncio.TimeoutError:
                # Idle clients send nothing — ping them instead of dropping
                await ws.send_text(json.dumps({"type": "ping"}))
                continue
            msg  = json.loads(data)
            if msg.get("action") == "reset":
                detector.reset_buffer()
                await ws.send_text(json.dumps({"type": "text", "text": ""}))
            elif msg.get("action") == "speak":
                tts.speak(msg.get("text", ""))
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        if ws in active_ws:
            active_ws.remove(ws)
        print(f"[WS] Client disconnected ({len(active_ws)} active)")


class SpeakRequest(BaseModel):
    text: str

@app.post("/speak")
async def speak(req: SpeakRequest):
    tts.speak(req.text)
    return {"status": "queued", "text": req.text}


@app.post("/reset")
async def reset():
    detector.reset_buffer()
    _broadcast({"type": "text", "text": ""})
    return {"status": "reset"}


from pydantic import BaseModel as PydanticBase


class SnippetsUpdate(PydanticBase):
    snippets: dict


@app.get("/snippets")
async def get_snippets():
    """Get all current snippet assignments."""
    return load_snippets()


@app.post("/snippets")
async def update_snippets(req: SnippetsUpdate):
    """Save snippet assignments from frontend."""
    success = save_snippets(req.snippets)
    if success:
        tts.prewarm(req.snippets.values())
    return {"status": "ok" if success else "error", "snippets": req.snippets}


@app.post("/snippets/reset")
async def reset_snippets():
    """Reset all snippets to defaults."""
    reset_to_defaults()
    return {"status": "reset", "snippets": DEFAULT_SNIPPETS}


@app.get("/snippets/defaults")
async def get_defaults():
    """Get the default snippet assignments."""
    return DEFAULT_SNIPPETS
