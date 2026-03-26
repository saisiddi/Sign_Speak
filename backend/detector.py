"""
SignSpeak - Detector (MediaPipe Tasks API)
==========================================
Uses the new MediaPipe Tasks GestureRecognizer — no TensorFlow needed.
Recognizes ASL hand gestures in real time from webcam.

Run standalone: python detector.py
Controls: Q = quit, SPACE = clear buffer
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.vision import GestureRecognizer, GestureRecognizerOptions, RunningMode
from mediapipe.tasks.python.vision.hand_landmarker import HandLandmarksConnections
from tts_bridge import TTSBridge
import time
import threading
import sys
import os
import numpy as np

HAND_CONNECTIONS = HandLandmarksConnections.HAND_CONNECTIONS

# ── Config ───────────────────────────────────────────────────────────────────
CAMERA_ID          = 0
FRAME_WIDTH        = 1280
FRAME_HEIGHT       = 720
SIGN_HOLD_FRAMES   = 8
WORD_PAUSE_SECS    = 999
MODEL_PATH         = os.path.join(os.path.dirname(__file__), "model", "gesture_recognizer.task")

# Map MediaPipe gesture names to display labels
GESTURE_MAP = {
    "Open_Palm":    "Hello",
    "Thumb_Up":     "Yes",
    "Thumb_Down":   "No",
    "Victory":      "Thank you",
    "Pointing_Up":  "Help me",
    "Closed_Fist":  "Stop",
    "ILoveYou":     "I love you",
    "None":         "NOTHING",
}


class SignDetector:
    def __init__(self):
        self._load_recognizer()
        self._last_spoken    = None
        self._cooldown_until = 0

        self.current_sign    = None
        self.sign_hold_count = 0
        self.confirmed_sign  = None
        self.text_buffer     = ""
        self.last_sign_time  = time.time()

        self.on_sign_confirmed = None
        self.on_text_updated   = None
        self.on_speak_trigger  = None

        self._latest_result = None

    def _load_recognizer(self):
        if not os.path.exists(MODEL_PATH):
            print(f"[Detector] ERROR: Model not found at {MODEL_PATH}")
            print("[Detector] Run: python download_model.py")
            self._recognizer = None
            return

        base_options = mp_python.BaseOptions(model_asset_path=MODEL_PATH)
        options = GestureRecognizerOptions(
            base_options=base_options,
            running_mode=RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.6,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.5,
        )
        self._recognizer = GestureRecognizer.create_from_options(options)
        print("[Detector] MediaPipe Gesture Recognizer loaded OK")

    def process_frame(self, frame) -> dict:
        sign         = "NOTHING"
        conf         = 0.0
        hand_visible = False

        if self._recognizer is None:
            self._draw_ui(frame, None, 0.0, False)
            return {"sign": None, "confidence": 0, "confirmed": None,
                    "text_buffer": self.text_buffer, "hand_visible": False}

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._recognizer.recognize(mp_image)

        if result.gestures and result.hand_landmarks:
            hand_visible = True
            conf         = result.gestures[0][0].score
            raw_gesture  = result.gestures[0][0].category_name
            print(f"[RAW] {raw_gesture} ({conf:.2f})")
            sign         = GESTURE_MAP.get(raw_gesture, raw_gesture)

            # Draw hand landmarks
            h, w = frame.shape[:2]
            lms = result.hand_landmarks[0]
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in lms]

            # Draw connections
            for connection in HAND_CONNECTIONS:
                cv2.line(frame, pts[connection.start], pts[connection.end], (0, 200, 120), 1)

            # Draw landmark dots
            for pt in pts:
                cv2.circle(frame, pt, 4, (0, 230, 140), -1)

            # Draw bounding box
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x1, y1 = max(0, min(xs) - 20), max(0, min(ys) - 20)
            x2, y2 = min(w, max(xs) + 20), min(h, max(ys) + 20)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 120), 2)

            self._update_sign_state(sign, conf)
        else:
            self._check_word_pause()
            self.current_sign    = None
            self.sign_hold_count = 0

        self._draw_ui(frame, sign, conf, hand_visible)

        return {
            "sign":         sign,
            "confidence":   round(conf, 3),
            "confirmed":    self.confirmed_sign,
            "text_buffer":  self.text_buffer,
            "hand_visible": hand_visible,
        }

    def _update_sign_state(self, sign: str, conf: float):
        if time.time() < self._cooldown_until:
            self.sign_hold_count = 0
            self.current_sign    = None
            return

        if sign == "NOTHING" or conf < 0.5:
            self.sign_hold_count = 0
            self.current_sign    = None
            return

        if sign == self.current_sign:
            self.sign_hold_count += 1
        else:
            self.current_sign    = sign
            self.sign_hold_count = 1

        if self.sign_hold_count == SIGN_HOLD_FRAMES:
            self.confirmed_sign = sign
            self.last_sign_time = time.time()
            self._handle_confirmed(sign)

    def _handle_confirmed(self, sign: str):
        if sign == "NOTHING":
            return
        now = time.time()
        if now < self._cooldown_until:
            return
        if sign == self._last_spoken:
            # Same sign — only allow repeat after 4 seconds
            if now - self._cooldown_until < 4.0:
                return
        self._last_spoken    = sign
        self._cooldown_until = now + 3.0
        self.text_buffer     = sign
        self.sign_hold_count = 0
        self.current_sign    = None
        self.confirmed_sign  = None
        if self.on_speak_trigger:
            self.on_speak_trigger(sign)
        if self.on_sign_confirmed:
            self.on_sign_confirmed(sign)
        if self.on_text_updated:
            self.on_text_updated(sign)

    def _check_word_pause(self):
        pass

    def _draw_ui(self, frame, sign, conf, hand_visible):
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 120), (w, h), (15, 15, 15), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        if sign and sign != "NOTHING" and hand_visible:
            label = f"{sign}  {int(conf * 100)}%"
            cv2.putText(frame, label, (20, h - 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 230, 140), 3)
        else:
            cv2.putText(frame, "Show hand...", (20, h - 75),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (120, 120, 120), 2)

        display_text = self.text_buffer[-50:] if len(self.text_buffer) > 50 else self.text_buffer
        cv2.putText(frame, display_text or "_", (20, h - 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 2)

        if self.sign_hold_count > 0:
            bar_w = int((self.sign_hold_count / SIGN_HOLD_FRAMES) * 300)
            cv2.rectangle(frame, (20, h - 130), (20 + bar_w, h - 122), (0, 200, 100), -1)

        cv2.putText(frame, "SignSpeak", (w - 160, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 140), 2)

    def reset_buffer(self):
        self.text_buffer    = ""
        self.confirmed_sign = None


if __name__ == "__main__":
    print("=" * 50)
    print("  SignSpeak - Webcam Test (Tasks API)")
    print("  Press Q to quit | SPACE to clear buffer")
    print("=" * 50)

    tts = TTSBridge()
    threading.Thread(target=lambda: (time.sleep(1), tts.speak("SignSpeak ready")), daemon=True).start()

    detector = SignDetector()

    detector.on_sign_confirmed = lambda s: print(f"[SIGN] {s}")
    detector.on_text_updated   = lambda t: print(f"[TEXT] '{t}'")

    def on_speak(w):
        print(f"[SPEAK] '{w}'")
        tts.speak(w)

    detector.on_speak_trigger = on_speak

    # Windows fix: use DirectShow backend
    cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        print(f"ERROR: Cannot open camera {CAMERA_ID}")
        sys.exit(1)

    # Warm up camera
    for _ in range(5):
        cap.read()

    print(f"Camera opened: {int(cap.get(3))}x{int(cap.get(4))}")

    prev_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Frame read failed — retrying...")
            cap.release()
            time.sleep(0.5)
            cap = cv2.VideoCapture(CAMERA_ID, cv2.CAP_DSHOW)
            continue

        frame = cv2.flip(frame, 1)
        detector.process_frame(frame)

        fps = 1.0 / (time.time() - prev_time + 1e-8)
        prev_time = time.time()
        cv2.putText(frame, f"{fps:.0f} fps", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 1)

        cv2.imshow("SignSpeak (Q to quit)", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord(' '):
            detector.reset_buffer()
            print("[RESET] Buffer cleared")

    cap.release()
    cv2.destroyAllWindows()
    print("Done.")
