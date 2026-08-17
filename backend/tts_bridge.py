"""
SignSpeak - TTS Bridge (persistent Piper TTS)
Piper runs as ONE long-lived subprocess. Text goes in on stdin; each
utterance is written to a unique WAV file in a scratch directory (piper's
stdout mode corrupts binary audio on Windows - the C runtime stuffs \\r
bytes into every \\n), and the file is read back and played. The model
stays loaded between phrases. Synthesized phrases are cached in memory, so
repeated phrases (the normal case for a small gesture vocabulary) play
instantly. Falls back to Windows SAPI if the Piper process dies.
"""
import threading
import queue
import re
import time
import subprocess
import os
import io
import struct
import tempfile
import winsound
import numpy as np
from collections import OrderedDict

# Preferred player: sounddevice + soundfile (correct playback of any rate/depth).
# winsound stays as a fallback if these are not installed.
try:
    import sounddevice as _sd
    import soundfile as _sf
    _HAS_SD = True
except ImportError:
    _HAS_SD = False


def _wasapi_output_device():
    """Prefer the WASAPI default output device — the same modern audio path
    media players use. PortAudio's default (MME) resampling garbles Piper
    audio on some machines and adds latency. WASAPI only accepts the device
    mix rate (48 kHz), so _play_wav always resamples to 48000 stereo."""
    if not _HAS_SD:
        return None
    try:
        for api in _sd.query_hostapis():
            if 'WASAPI' in api['name'] and api.get('default_output_device', -1) >= 0:
                return api['default_output_device']
    except Exception:
        pass
    return None


# Paths — relative to project root
PIPER_EXE   = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'piper', 'piper.exe'))
PIPER_MODEL = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'piper', 'en_US-lessac-high.onnx'))

# Piper writes each utterance to a uniquely-named WAV in the scratch dir.
_SYNTH_TIMEOUT = 10.0    # watchdog per CHUNK (a few seconds of speech each)
_CHUNK_CHARS   = 220     # max characters per synthesis chunk (~12s of audio)
_WRITE_SLICE   = 2400    # 50 ms at 48 kHz — interruption granularity

_SENTENCE_RE = re.compile(r'[^.!?\n]+[.!?]*')


def _split_sentences(text: str) -> list:
    """Split text into sentence-ish chunks, each short enough that Piper
    synthesizes it well inside the watchdog timeout."""
    parts = [p.strip() for p in _SENTENCE_RE.findall(text) if p.strip()]
    if not parts:
        return [text]
    chunks, cur = [], ''
    for p in parts:
        while len(p) > _CHUNK_CHARS:            # pathological unbroken text
            cut = p.rfind(' ', 0, _CHUNK_CHARS)
            cut = cut if cut > 60 else _CHUNK_CHARS
            chunks.append(p[:cut].strip())
            p = p[cut:].strip()
        if len(cur) + len(p) + 1 <= _CHUNK_CHARS:
            cur = (cur + ' ' + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return chunks

# Phrase cache limits (WAV bytes ~44.1 KB per second of audio)
_CACHE_MAX_ENTRIES = 256
_CACHE_MAX_BYTES   = 64 * 1024 * 1024

# SAPI fallback settings
SAPI_RATE   = 3
SAPI_VOLUME = 100


class _PiperProcess:
    """One long-lived `piper.exe --output_dir <scratch>` subprocess.

    synthesize(text) writes one line to piper's stdin, waits for the WAV
    file piper writes for that utterance, and returns its bytes. Only the
    TTS worker thread touches the process, so no extra locking is needed.
    """

    def __init__(self):
        self._proc = None
        self._dir = tempfile.mkdtemp(prefix='signspeak_tts_')

    def start(self) -> bool:
        self.stop()
        for f in os.listdir(self._dir):        # drop leftovers from a crash
            try:
                os.remove(os.path.join(self._dir, f))
            except OSError:
                pass
        try:
            self._proc = subprocess.Popen(
                [PIPER_EXE, '--model', PIPER_MODEL, '--output_dir', self._dir],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"[TTS] Piper process started (pid {self._proc.pid})")
            return True
        except Exception as e:
            print(f"[TTS] Failed to start Piper: {e}")
            self._proc = None
            return False

    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self):
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def synthesize(self, text: str):
        """Return WAV bytes for text, or None if the process failed."""
        if not self.alive() and not self.start():
            return None
        before = set(os.listdir(self._dir))
        watchdog = threading.Timer(_SYNTH_TIMEOUT, self.stop)
        watchdog.start()
        try:
            self._proc.stdin.write(text.replace('\n', ' ').encode('utf-8') + b'\n')
            self._proc.stdin.flush()
            deadline = time.time() + _SYNTH_TIMEOUT
            while time.time() < deadline:
                new = sorted(f for f in os.listdir(self._dir)
                             if f.endswith('.wav') and f not in before)
                if new:
                    wav = self._read_complete(os.path.join(self._dir, new[-1]))
                    if wav is not None:
                        return wav
                time.sleep(0.015)
            print("[TTS] Piper synthesize timed out")
            self.stop()
            return None
        except Exception as e:
            print(f"[TTS] Piper synthesize failed: {e}")
            self.stop()
            return None
        finally:
            watchdog.cancel()

    def _read_complete(self, path: str):
        """Read the WAV once it is fully written (RIFF sizes consistent)."""
        for _ in range(25):
            try:
                with open(path, 'rb') as f:
                    raw = f.read()
            except OSError:
                time.sleep(0.02)
                continue
            if len(raw) > 44 and raw[:4] == b'RIFF':
                riff_size = struct.unpack('<I', raw[4:8])[0]
                if len(raw) >= 8 + riff_size:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    return raw[:8 + riff_size]
            time.sleep(0.02)
        return None


class TTSBridge:
    def __init__(self):
        self._queue      = queue.Queue()
        self._piper      = _PiperProcess()
        self._piper_lock = threading.Lock()   # one piper client at a time
        self._cache      = OrderedDict()   # text -> [48 kHz stereo float32, ...]
        self._cached_bytes = 0
        self._out_stream = None            # one long-lived output stream
        self._out_device = None            # device index the stream is open on
        self._out_params = None            # (blocksize, latency) the stream is open with
        self._pa_refreshed = 0.0           # last PortAudio device-table refresh
        self._speak_seq   = 0              # bumped per speak(); latest wins
        self._backend = "piper" if self._piper.start() else "sapi"
        self._worker  = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        print(f"[TTS] Backend: {self._backend}")

    @property
    def backend(self) -> str:
        return self._backend

    def speak(self, text: str):
        text = text.strip()
        if not text:
            return
        # Latest phrase wins: drop anything queued and invalidate whatever
        # is currently being spoken so a new gesture interrupts immediately.
        # (put() must run OUTSIDE the mutex — it acquires the same lock.)
        with self._queue.mutex:
            self._queue.queue.clear()
            self._speak_seq += 1
            seq = self._speak_seq
        self._queue.put((seq, text))

    def speak_now(self, text: str):
        self.speak(text)

    def _stale(self, seq: int) -> bool:
        return self._speak_seq != seq

    def _worker_loop(self):
        while True:
            seq, text = self._queue.get()
            try:
                self._say(text, seq)
            except Exception as e:
                print(f"[TTS] Error: {e}")
            self._queue.task_done()

    def _say(self, text: str, seq: int):
        if self._backend == "piper":
            if self._speak_piper(text, seq):
                return
            if self._stale(seq):
                return          # interrupted by a newer phrase — it takes over
            print("[TTS] Piper unavailable — falling back to SAPI")
        self._say_sapi(text)

    def _speak_piper(self, text: str, seq: int) -> bool:
        cached = self._cache.get(text)
        if cached is not None:
            self._cache.move_to_end(text)
            for arr in cached:
                if self._stale(seq):
                    return True         # superseded mid-playback — not an error
                if not self._stream_write(arr, seq):
                    return False
            return True
        status, arrays = self._stream_speak(text, seq)
        if status == 'done':
            self._store_cache(text, arrays)
            return True
        return status == 'stale'

    def prewarm(self, phrases):
        """Synthesize the given phrases in the background so gesture triggers
        play from cache with ~zero synthesis latency. Very long texts are
        skipped — they stream on first use instead."""
        def job():
            for phrase in set(phrases):
                phrase = (phrase or '').strip()
                if not phrase or phrase in self._cache or len(phrase) > 300:
                    continue
                try:
                    arrays = [self._synth_chunk(c) for c in _split_sentences(phrase)]
                    if all(a is not None for a in arrays):
                        self._store_cache(phrase, arrays)
                except Exception as e:
                    print(f"[TTS] Prewarm skipped {phrase!r}: {e}")
        threading.Thread(target=job, daemon=True).start()

    def _synth_chunk(self, text: str):
        """Synthesize one chunk and convert it to playback-ready audio."""
        with self._piper_lock:
            wav = self._piper.synthesize(text)
            if wav is None and self._piper.start():
                wav = self._piper.synthesize(text)
        if wav is None:
            return None
        return self._to_playback(wav)

    def _stream_speak(self, text: str, seq: int):
        """Speak text sentence-by-sentence: chunk i plays while chunk i+1 is
        being synthesized, so long phrases start fast and never hit the
        per-chunk synthesis timeout. Returns (status, played_arrays) with
        status in {'done', 'stale', 'error'}."""
        chunks = _split_sentences(text)
        arrays = []
        cur = self._synth_chunk(chunks[0])
        for i in range(len(chunks)):
            box, t = [None], None
            if i + 1 < len(chunks):
                def prefetch(idx=i + 1):
                    box[0] = self._synth_chunk(chunks[idx])
                t = threading.Thread(target=prefetch, daemon=True)
                t.start()
            if cur is None:
                return 'error', arrays
            if self._stale(seq):
                if t is not None:
                    t.join()
                return 'stale', arrays
            arrays.append(cur)
            if not self._stream_write(cur, seq):
                return 'error', arrays
            cur = None
            if t is not None:
                t.join()
                cur = box[0]
        return 'done', arrays

    def _store_cache(self, text: str, arrays):
        self._cache[text] = arrays
        self._cached_bytes += sum(a.nbytes for a in arrays)
        while (len(self._cache) > _CACHE_MAX_ENTRIES
               or self._cached_bytes > _CACHE_MAX_BYTES):
            _, old = self._cache.popitem(last=False)
            self._cached_bytes -= sum(a.nbytes for a in old)

    def _to_playback(self, wav_bytes: bytes):
        """WAV bytes -> 48 kHz stereo float32 (the format the WASAPI stream
        is opened with, so playback is a pure buffer write)."""
        try:
            data, sr = _sf.read(io.BytesIO(wav_bytes), dtype='float32')
        except Exception as e:
            print(f"[TTS] WAV decode failed: {e}")
            return None
        if data.ndim > 1:
            return data
        if sr != 48000:
            t_old = np.arange(len(data)) / sr
            t_new = np.arange(0, len(data) / sr, 1 / 48000)
            data = np.interp(t_new, t_old, data).astype(np.float32)
        return np.ascontiguousarray(np.column_stack([data, data]))

    def _stream_write(self, arr, seq: int = None) -> bool:
        """Write audio in ~100 ms slices, checking between slices whether a
        newer phrase has arrived; on interruption the stream is closed so the
        old speech cuts off immediately."""
        if not _HAS_SD:
            return False
        # Attempt (480, 'low'): ~10 ms blocks, snappiest response. Attempt
        # (0, None): PortAudio-chosen buffering — fallback for devices that
        # reject aggressive settings (Bluetooth hands-free, exotic drivers).
        for params in ((480, 'low'), (0, None)):
            blocksize, latency = params
            try:
                dev = self._current_device()
                st = self._out_stream
                if (st is None or not st.active
                        or dev != self._out_device
                        or params != self._out_params):
                    self._close_stream()
                    kwargs = dict(samplerate=48000, channels=2,
                                  dtype='float32', device=dev)
                    if blocksize:
                        kwargs['blocksize'] = blocksize
                    if latency is not None:
                        kwargs['latency'] = latency
                    st = _sd.OutputStream(**kwargs)
                    st.start()
                    self._out_stream = st
                    self._out_device = dev
                    self._out_params = params
                i = 0
                while i < len(arr):
                    if seq is not None and self._stale(seq):
                        self._close_stream()
                        return True            # interrupted, not failed
                    st.write(arr[i:i + _WRITE_SLICE])
                    i += _WRITE_SLICE
                return True
            except Exception as e:
                print(f"[TTS] Playback attempt {params} failed: {e}")
                self._close_stream()
        return False

    def _current_device(self):
        """Live default output device.

        PortAudio freezes its device table at Pa_Initialize (sounddevice does
        this once at import), so plugging/unplugging earphones is invisible to
        a running backend and audio keeps targeting the dead endpoint. Force a
        re-enumeration (terminate + initialize) at most every 0.5 s — phrases
        are seconds apart, so each new utterance sees fresh devices while
        sentence chunks within one phrase reuse the open stream."""
        now = time.time()
        if now - self._pa_refreshed > 0.5:
            self._close_stream()
            try:
                while _sd._initialized:
                    _sd._terminate()
                _sd._initialize()
            except Exception as e:
                print(f"[TTS] PortAudio re-init failed: {e}")
            self._pa_refreshed = now
        return _wasapi_output_device()

    def _close_stream(self):
        if self._out_stream is not None:
            try:
                self._out_stream.stop()
                self._out_stream.close()
            except Exception:
                pass
            self._out_stream = None
            self._out_device = None
            self._out_params = None

    def _say_sapi(self, text: str):
        text = text.replace('"', '').replace("'", '')
        cmd = (
            f'Add-Type -AssemblyName System.Speech;'
            f'$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;'
            f'$s.Rate={SAPI_RATE};'
            f'$s.Volume={SAPI_VOLUME};'
            f'$s.Speak("{text}");'
        )
        subprocess.run(
            ['powershell', '-NonInteractive', '-Command', cmd],
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )


if __name__ == "__main__":
    print("=" * 50)
    print("  SignSpeak — Persistent Piper TTS Test")
    print("=" * 50)
    tts = TTSBridge()
    time.sleep(0.5)
    tts.prewarm(["Hello, SignSpeak is ready.", "Yes", "Thank you",
                 "I need help", "Good morning everyone"])

    phrases = [
        "Hello, SignSpeak is ready.",
        "Yes",
        "Thank you",
        "I need help",
        "Good morning everyone",
        "A brand new phrase never spoken before",
        "Yes",   # repeat — instant cache hit
    ]

    for phrase in phrases:
        time.sleep(2.0)
        cached = phrase in tts._cache
        t0 = time.time()
        print(f"Speaking: {phrase}" + ("  (cached)" if cached else "  (synthesizing)"))
        tts.speak(phrase)
        tts._queue.join()
        print(f"  finished in {time.time() - t0:.2f}s")

    tts._close_stream()
    tts._piper.stop()
    print("Done.")
