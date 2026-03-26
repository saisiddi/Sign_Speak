# SignSpeak 🤟
> Real-time ASL sign language → text → speech. Runs 100% locally on your laptop.

## Quick Start (5 steps)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test your webcam
python test_webcam.py

# 3. Download the pre-trained ASL model (~100KB)
python backend/download_model.py

# 4. Test detection standalone (no server needed)
python backend/detector.py

# 5. Start the full server
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

**Windows one-click (for expo):** just run `run.bat`

---

## Project Structure

```
sign-speak/
├── backend/
│   ├── main.py               ← FastAPI server + WebSocket
│   ├── detector.py           ← OpenCV + MediaPipe pipeline
│   ├── classifier.py         ← TFLite landmark classifier
│   ├── tts_bridge.py         ← VoiceBox / Kokoro / pyttsx3 TTS
│   ├── download_model.py     ← Downloads pre-trained model
│   └── model/
│       └── keypoint_classifier.tflite   ← ASL model (auto-downloaded)
├── frontend/                 ← React UI (Week 2)
├── test_webcam.py            ← Sanity check
├── requirements.txt
└── run.bat                   ← One-click expo launcher
```

---

## How It Works

```
Webcam → MediaPipe Hands → 21 Landmarks → TFLite Classifier → Letter/Sign
    ↓                                                              ↓
MJPEG Stream                                              Text Buffer
(in browser)                                                    ↓
                                                   VoiceBox TTS (speaks word)
                                                                ↓
                                               WebSocket → React Frontend
```

---

## Sign Controls (while detecting)

| Action | How |
|--------|-----|
| Add letter | Hold ASL letter for ~10 frames |
| Space / next word | Sign "SPACE" (flat hand, fingers together) |
| Delete last | Sign "DELETE" (D gesture) |
| Auto-speak | Hold any sign or pause hand = TTS speaks last word |

---

## TTS Backend Priority

The app tries these TTS backends in order:

1. **Kokoro** — best quality, ElevenLabs-level (install: `pip install kokoro-onnx sounddevice`)
2. **VoiceBox** — if running on `localhost:50021`
3. **pyttsx3** — built-in Windows SAPI fallback (always works, no install)

---

## Google Meet Demo (Expo)

**Option A (simple):** Run app in a browser window next to Google Meet.

**Option B (impressive):** Use OBS Virtual Camera:
1. Add a Browser Source in OBS pointing to `http://localhost:8000`
2. Enable OBS Virtual Camera
3. In Google Meet → Settings → Camera → select "OBS Virtual Camera"

---

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | Frontend |
| `WS /ws` | Live detection events (JSON) |
| `GET /video_feed` | MJPEG webcam stream |
| `GET /health` | Status + TTS backend |
| `POST /speak` | `{"text": "hello"}` → TTS |
| `POST /reset` | Clear text buffer |

---

## Common Issues

**Camera not opening** → Change `CAMERA_ID = 1` in `detector.py` and `test_webcam.py`

**Low accuracy** → Ensure good lighting, keep hand centered, use pre-trained model

**TTS not speaking** → Run `python backend/tts_bridge.py` to check which backend is active

**Port 8000 busy** → Change to `--port 8001` in uvicorn command and `run.bat`

---

## Week 2 (Next)

- Build React frontend with live transcript panel
- WebSocket integration
- Animated sign detection feedback
- Google Meet overlay via OBS
