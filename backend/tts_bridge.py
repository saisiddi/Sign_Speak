"""
SignSpeak - TTS Bridge (subprocess per-call, non-blocking)
"""
import threading, queue, time, subprocess

SAPI_RATE   = 3
SAPI_VOLUME = 100

class TTSBridge:
    def __init__(self):
        self._queue   = queue.Queue()
        self._backend = "sapi"
        self._worker  = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        print("[TTS] Backend: Windows SAPI")

    def speak(self, text: str):
        text = text.strip().replace('"', '').replace("'", '')
        if text:
            # Clear queue — always speak latest word only
            while not self._queue.empty():
                try: self._queue.get_nowait()
                except: break
            self._queue.put(text)

    def speak_now(self, text: str):
        self.speak(text)

    def _worker_loop(self):
        while True:
            text = self._queue.get()
            try:
                cmd = (
                    f'Add-Type -AssemblyName System.Speech;'
                    f'$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;'
                    f'$s.Rate={SAPI_RATE};'
                    f'$s.Volume={SAPI_VOLUME};'
                    f'$s.Speak("{text}");'
                )
                subprocess.run(
                    ['powershell', '-NonInteractive', '-Command', cmd],
                    timeout=10,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                print(f"[TTS] Error: {e}")
            self._queue.task_done()


if __name__ == "__main__":
    tts = TTSBridge()
    time.sleep(0.5)

    for word in ["Hello", "Yes", "Thank you", "Stop", "Help me"]:
        print(f"Speaking: {word}")
        tts.speak(word)
        time.sleep(2.5)

    print("Done.")