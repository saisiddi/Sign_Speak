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
from collections import deque, Counter
from snippets import get_phrase
from asl_alphabet import classify as classify_letter
import numpy as np

HAND_CONNECTIONS = HandLandmarksConnections.HAND_CONNECTIONS

# Set True to print every frame's raw gesture + confidence (debug only —
# the per-frame print costs I/O and spams the log at ~10 lines/sec)
RAW_DEBUG = False

# ── Config ───────────────────────────────────────────────────────────────────
CAMERA_ID          = 0
FRAME_WIDTH        = 1280
FRAME_HEIGHT       = 720
SIGN_HOLD_FRAMES   = 2
CONF_INSTANT       = 0.75   # a frame this confident confirms the gesture at once
WORD_PAUSE_SECS    = 999

# Fingerspelling (ASL alphabet database)
LETTER_VOTE_LEN    = 10     # sliding window of letter classifications
LETTER_VOTE_NEEDED = 8      # agreement required to accept a letter (~0.33s hold at 30fps — kills I/S flicker)
LETTER_GAP_SECS    = 1.2    # hold the SAME letter again to double it in a word
WORD_SPEAK_PAUSE   = 1.8    # no new letter for this long -> speak the word
WORD_MAX_LETTERS   = 24
MODES              = ("snippets", "asl", "both")
MODEL_PATH         = os.path.join(os.path.dirname(__file__), "model", "gesture_recognizer.task")

# MediaPipe recognizer confidence thresholds
MIN_DETECTION_CONF = 0.80
MIN_TRACKING_CONF  = 0.75

# Per-gesture phrase-confirmation thresholds. 0.50 keeps the recognizer
# responsive to low-confidence but deliberate gestures; the consecutive-frame
# hold requirement (SIGN_HOLD_FRAMES) filters flicker and misreads.
DEFAULT_CONF_MIN   = 0.50
GESTURE_CONF_MIN   = {}

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
        self._ts             = 0        # VIDEO-mode frame timestamp (ms, increasing)
        self.fps             = 0.0      # rolling recognition rate
        self._prev_frame     = None

        self.current_sign    = None
        self.sign_hold_count = 0
        self.confirmed_sign  = None
        self.text_buffer     = ""
        self.last_sign_time  = time.time()

        # Fingerspelling state
        self.letters_enabled = True
        self.mode            = "both"     # snippets | asl | both
        self._letter          = None
        self._letter_n        = 0
        self._vote            = deque(maxlen=LETTER_VOTE_LEN)
        self._last_letter_add = 0.0
        self.spell_buffer     = ""

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
            running_mode=RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=MIN_DETECTION_CONF,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=MIN_TRACKING_CONF,
        )
        self._recognizer = GestureRecognizer.create_from_options(options)
        print("[Detector] MediaPipe Gesture Recognizer loaded OK")

    def process_frame(self, frame) -> dict:
        sign         = "NOTHING"
        conf         = 0.0
        hand_visible = False

        now = time.time()
        if self._prev_frame is not None:
            inst = 1.0 / max(now - self._prev_frame, 1e-6)
            self.fps = inst if self.fps == 0 else 0.9 * self.fps + 0.1 * inst
        self._prev_frame = now

        if self._recognizer is None:
            self._draw_ui(frame, None, 0.0, False)
            return {"sign": None, "confidence": 0, "confirmed": None,
                    "text_buffer": self.text_buffer, "hand_visible": False}

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._ts = max(self._ts + 1, int(time.time() * 1000))
        result = self._recognizer.recognize_for_video(mp_image, self._ts)

        phrase = None
        if result.gestures and result.hand_landmarks:
            hand_visible = True
            conf         = result.gestures[0][0].score
            raw_gesture  = result.gestures[0][0].category_name
            if RAW_DEBUG:
                print(f"[RAW] {raw_gesture} ({conf:.2f})")
            sign         = GESTURE_MAP.get(raw_gesture, raw_gesture)
            phrase       = get_phrase(raw_gesture) if raw_gesture != "None" else None

            # Draw hand landmarks — soft modern skeleton
            h, w = frame.shape[:2]
            lms = result.hand_landmarks[0]
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in lms]

            for connection in HAND_CONNECTIONS:
                cv2.line(frame, pts[connection.start], pts[connection.end],
                         (225, 208, 77), 2, cv2.LINE_AA)
            for pt in pts:
                cv2.circle(frame, pt, 3, (255, 255, 255), -1, cv2.LINE_AA)

            # Camera-focus style corner brackets around the hand
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x1, y1 = max(0, min(xs) - 24), max(0, min(ys) - 24)
            x2, y2 = min(w, max(xs) + 24), min(h, max(ys) + 24)
            bracket, length = (225, 208, 77), 16
            for (cx, cy, dx, dy) in ((x1, y1, 1, 1), (x2, y1, -1, 1),
                                     (x1, y2, 1, -1), (x2, y2, -1, -1)):
                cv2.line(frame, (cx, cy), (cx + dx * length, cy), bracket, 2, cv2.LINE_AA)
                cv2.line(frame, (cx, cy), (cx, cy + dy * length), bracket, 2, cv2.LINE_AA)

            # Mode system: 'snippets' = gestures only, 'asl' = letters only,
            # 'both' = gestures take priority, letters fill the gaps.
            if self.mode != "asl":
                self._update_sign_state(sign, conf, raw_gesture)

            letters_active = (
                self.letters_enabled
                and (self.mode == "asl" or (self.mode == "both" and raw_gesture == "None"))
            )
            if letters_active:
                letter, lscore = classify_letter(lms)
                self._update_letter(letter, lscore)
            else:
                self._letter, self._letter_n = None, 0
                self._vote.clear()
        else:
            self.current_sign    = None
            self.sign_hold_count = 0
            self._letter, self._letter_n = None, 0

        self._maybe_speak_word()
        self._draw_ui(frame, sign, conf, hand_visible, phrase)

        return {
            "sign":         sign,
            "confidence":   round(conf, 3),
            "confirmed":    self.confirmed_sign,
            "text_buffer":  self.text_buffer,
            "hand_visible": hand_visible,
        }

    def _update_sign_state(self, sign: str, conf: float, raw_gesture: str = None):
        if time.time() < self._cooldown_until:
            self.sign_hold_count = 0
            self.current_sign    = None
            return

        conf_min = GESTURE_CONF_MIN.get(raw_gesture, DEFAULT_CONF_MIN) if raw_gesture else DEFAULT_CONF_MIN
        if sign == "NOTHING" or conf < conf_min:
            self.sign_hold_count = 0
            self.current_sign    = None
            return

        if sign == self.current_sign:
            self.sign_hold_count += 1
        else:
            self.current_sign    = sign
            self.sign_hold_count = 1

        # High-confidence frames confirm instantly; weaker ones need a
        # short consistent hold to filter flicker.
        needed = 1 if conf >= CONF_INSTANT else SIGN_HOLD_FRAMES
        if self.sign_hold_count >= needed:
            self.confirmed_sign = sign
            self.last_sign_time = time.time()
            self._handle_confirmed(sign, raw_gesture)

    def _handle_confirmed(self, sign: str, raw_gesture: str = None):
        if sign == "NOTHING":
            return
        now = time.time()
        if now < self._cooldown_until:
            return
        if sign == self._last_spoken:
            # Same sign again — allow a quick repeat shortly after cooldown
            if now - self._cooldown_until < 1.0:
                return
        self._last_spoken    = sign
        self._cooldown_until = now + 1.2
        # Look up the snippet phrase using the RAW gesture name (e.g. "Open_Palm"),
        # not the display label, since snippets.json is keyed by raw names.
        phrase = get_phrase(raw_gesture if raw_gesture else sign)
        self.text_buffer     = phrase
        self.sign_hold_count = 0
        self.current_sign    = None
        self.confirmed_sign  = None
        if self.on_speak_trigger:
            self.on_speak_trigger(phrase)
        if self.on_sign_confirmed:
            self.on_sign_confirmed(sign)
        if self.on_text_updated:
            self.on_text_updated(self.text_buffer)

    def _update_letter(self, letter, score):
        """Fingerspelling with majority voting: a letter is accepted once it
        dominates the recent classification window, which makes recognition
        immune to single-frame flicker between similar-looking letters."""
        self._vote.append(letter if letter and score >= 0.6 else None)
        counts = Counter(v for v in self._vote if v)
        if not counts:
            self._letter, self._letter_n = None, 0
            return
        top, n = counts.most_common(1)[0]
        self._letter, self._letter_n = top, n

        if n >= LETTER_VOTE_NEEDED:
            now = time.time()
            same = self.spell_buffer and self.spell_buffer[-1] == top
            if (not same or now - self._last_letter_add >= LETTER_GAP_SECS) \
                    and len(self.spell_buffer) < WORD_MAX_LETTERS:
                self.spell_buffer += top
                self._last_letter_add = now
                self.text_buffer = self.spell_buffer
                if self.on_text_updated:
                    self.on_text_updated(self.spell_buffer)
                self._vote.clear()
                self._letter_n = 0

    def _maybe_speak_word(self):
        """When spelling stops for WORD_SPEAK_PAUSE seconds, speak the word."""
        if self.spell_buffer and time.time() - self._last_letter_add >= WORD_SPEAK_PAUSE:
            word = self.spell_buffer
            self.spell_buffer = ""
            self.text_buffer  = word
            if self.on_speak_trigger:
                self.on_speak_trigger(word)
            if self.on_text_updated:
                self.on_text_updated(word)

    def _draw_ui(self, frame, sign, conf, hand_visible, phrase=None):
        h, w = frame.shape[:2]

        # Hold progress — slim accent bar along the bottom edge (gesture or letter)
        hold, need = 0, 1
        if self.sign_hold_count > 0:
            hold, need = self.sign_hold_count, SIGN_HOLD_FRAMES
        elif self._letter:
            hold, need = self._letter_n, LETTER_VOTE_NEEDED
        if hold:
            frac = min(hold / need, 1.0)
            cv2.rectangle(frame, (0, h - 4), (int(frac * w), h), (118, 230, 0), -1)

        # Live label — spelled word (with pending letter) or gesture phrase
        label = None
        if self.spell_buffer:
            label = self.spell_buffer + (f"  [{self._letter}]" if self._letter else "")
        elif phrase and hand_visible and sign and sign != "NOTHING":
            label = f"{phrase}  ·  {int(conf * 100)}%"
        if label:
            text = label if len(label) <= 40 else label[:39] + "..."
            scale, thickness = 0.55, 1
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
            x, y = (w - tw) // 2, h - 26
            overlay = frame.copy()
            cv2.rectangle(overlay, (x - 12, y - th - 10), (x + tw + 12, y + 8),
                          (24, 24, 24), -1)
            cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
            cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale,
                        (245, 245, 245), thickness, cv2.LINE_AA)

        # Minimal brand mark, top-left
        cv2.circle(frame, (16, 16), 3, (118, 230, 0), -1, cv2.LINE_AA)
        cv2.putText(frame, "SignSpeak", (26, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (255, 255, 255), 1, cv2.LINE_AA)

    def reset_spelling(self):
        """Clear all fingerspelling state (partial word, vote window, timers)."""
        self.spell_buffer     = ""
        self._vote.clear()
        self._letter, self._letter_n = None, 0
        self._last_letter_add = 0.0

    def reset_buffer(self):
        self.text_buffer    = ""
        self.confirmed_sign = None
        self.reset_spelling()


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
