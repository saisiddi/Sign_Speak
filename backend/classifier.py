"""
SignSpeak - Classifier (stub)
==============================
Classification is now handled entirely by MediaPipe Tasks GestureRecognizer
inside detector.py. This file is kept for import compatibility only.
"""

LABELS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["SPACE", "DELETE", "NOTHING"]


class KeypointClassifier:
    def __init__(self, *args, **kwargs):
        print("[Classifier] Using MediaPipe Tasks API — no TensorFlow needed.")

    def classify(self, landmarks):
        return "NOTHING", 0.0
