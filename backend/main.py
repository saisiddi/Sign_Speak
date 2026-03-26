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


def _broadcast(payload: dict):
    """Send JSON to all connected WebSocket clients (thread-safe via asyncio)."""
    msg = json.dumps(payload)
    for ws in active_ws.copy():
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(msg), asyncio.get_event_loop())
        except Exception:
            pass


# ── Camera thread ─────────────────────────────────────────────────────────────
def _camera_thread():
    global latest_frame, camera_running
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

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
        result = detector.process_frame(frame)

        # Encode frame to JPEG
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
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
        "buffer": detector.text_buffer,
    }


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
            # Keep connection alive, handle incoming messages
            data = await asyncio.wait_for(ws.receive_text(), timeout=30)
            msg  = json.loads(data)
            if msg.get("action") == "reset":
                detector.reset_buffer()
                await ws.send_text(json.dumps({"type": "text", "text": ""}))
            elif msg.get("action") == "speak":
                tts.speak(msg.get("text", ""))
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
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
