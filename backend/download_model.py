"""
SignSpeak - Model Downloader
============================
Downloads the official MediaPipe Gesture Recognizer task model.

Run once before starting the app:
    python download_model.py
"""

import urllib.request
import os

MODEL_DIR = os.path.join(os.path.dirname(__file__), "model")
MODEL_URLS = [
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task",
    "https://storage.googleapis.com/mediapipe-tasks/gesture_recognizer/gesture_recognizer.task",
]
MODEL_PATH = os.path.join(MODEL_DIR, "gesture_recognizer.task")


def download_gesture_model(dest: str):
    for idx, url in enumerate(MODEL_URLS, start=1):
        print(f"  [gesture_recognizer.task] Attempt {idx}: {url}")
        try:
            urllib.request.urlretrieve(url, dest)
            size = os.path.getsize(dest)
            print(f"  [gesture_recognizer.task] Downloaded ({size // 1024} KB)")
            if size < 1024 * 1000:
                raise RuntimeError("Downloaded model is too small; expected >= 1000 KB")
            return size
        except Exception as e:
            print(f"  [gesture_recognizer.task] FAILED: {e}")
    raise RuntimeError("All model download URLs failed")


if __name__ == "__main__":
    os.makedirs(MODEL_DIR, exist_ok=True)
    print("SignSpeak - downloading model files...")
    size = download_gesture_model(MODEL_PATH)
    print(f"\nDone! gesture_recognizer.task size: {size // 1024} KB")
    print("Now run: python detector.py  (to test webcam)")
    print("     Or: uvicorn main:app --reload  (to start server)")
