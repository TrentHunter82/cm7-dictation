#!/usr/bin/env python3
"""
CM7 Dictation Widget - HAL Edition
Hold F8 (or click) to record, release to transcribe and paste.
"""

import tkinter as tk
import threading
import time
import os
import platform
import tempfile
import wave
import struct
import math
import argparse
import configparser
from typing import Callable, Optional

_IS_MAC = platform.system() == "Darwin"

try:
    import pyaudio
    _HAS_PYAUDIO = True
except ImportError:
    _HAS_PYAUDIO = False

try:
    from pynput import keyboard as pynput_kb
    _HAS_PYNPUT = True
except ImportError:
    _HAS_PYNPUT = False

try:
    import pyperclip
    import pyautogui
    _HAS_PASTE = True
except ImportError:
    _HAS_PASTE = False

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# Map hotkey name strings to pynput Key objects
_PYNPUT_KEY_MAP = {}
if _HAS_PYNPUT:
    for i in range(1, 21):
        _PYNPUT_KEY_MAP[f"f{i}"] = getattr(pynput_kb.Key, f"f{i}", None)
    _PYNPUT_KEY_MAP.update({
        "ctrl": pynput_kb.Key.ctrl_l, "shift": pynput_kb.Key.shift_l,
        "alt": pynput_kb.Key.alt_l, "cmd": pynput_kb.Key.cmd,
        "space": pynput_kb.Key.space, "tab": pynput_kb.Key.tab,
        "esc": pynput_kb.Key.esc,
    })


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
def _config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.ini")


def load_api_key():
    path = _config_path()
    if not os.path.exists(path):
        return None
    cfg = configparser.ConfigParser()
    cfg.read(path)
    return cfg.get("groq", "api_key", fallback=None)


def save_api_key(key):
    path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(path):
        cfg.read(path)
    if not cfg.has_section("groq"):
        cfg.add_section("groq")
    cfg.set("groq", "api_key", key)
    with open(path, "w") as f:
        cfg.write(f)


def prompt_api_key():
    """Show a tkinter dialog to collect the Groq API key."""
    result = [None]

    win = tk.Tk()
    win.title("CM7 - Groq API Key")
    win.configure(bg="#1a1a1a")
    win.resizable(False, False)
    win.geometry("420x180")
    win.attributes("-topmost", True)

    # Center on screen
    win.update_idletasks()
    x = (win.winfo_screenwidth() - 420) // 2
    y = (win.winfo_screenheight() - 180) // 2
    win.geometry(f"+{x}+{y}")

    tk.Label(
        win, text="Enter your Groq API Key", font=("Arial", 13, "bold"),
        fg="#e0e0e0", bg="#1a1a1a"
    ).pack(pady=(18, 4))

    tk.Label(
        win, text="Get one free at console.groq.com", font=("Arial", 9),
        fg="#808080", bg="#1a1a1a"
    ).pack()

    entry = tk.Entry(win, width=44, font=("Consolas", 10), show="*")
    entry.pack(pady=(12, 10))
    entry.focus_set()

    def submit(event=None):
        key = entry.get().strip()
        if key:
            result[0] = key
            win.destroy()

    entry.bind("<Return>", submit)

    btn = tk.Button(
        win, text="Save & Launch", command=submit,
        font=("Arial", 10, "bold"), bg="#333", fg="#e0e0e0",
        activebackground="#555", activeforeground="#fff",
        relief="flat", padx=16, pady=4
    )
    btn.pack()

    win.protocol("WM_DELETE_WINDOW", lambda: win.destroy())
    win.mainloop()
    return result[0]


def load_elevenlabs_config():
    path = _config_path()
    if not os.path.exists(path):
        return {"api_key": None, "voice_id": None}
    cfg = configparser.ConfigParser()
    cfg.read(path)
    return {
        "api_key": cfg.get("elevenlabs", "api_key", fallback=None),
        "voice_id": cfg.get("elevenlabs", "voice_id", fallback=None),
    }


def save_elevenlabs_config(api_key, voice_id):
    path = _config_path()
    cfg = configparser.ConfigParser()
    if os.path.exists(path):
        cfg.read(path)
    if not cfg.has_section("elevenlabs"):
        cfg.add_section("elevenlabs")
    cfg.set("elevenlabs", "api_key", api_key)
    cfg.set("elevenlabs", "voice_id", voice_id)
    with open(path, "w") as f:
        cfg.write(f)


def prompt_elevenlabs_config():
    """Show a tkinter dialog to collect ElevenLabs API key and Voice ID."""
    result = [None, None]

    win = tk.Tk()
    win.title("CM7 - ElevenLabs TTS Setup")
    win.configure(bg="#1a1a1a")
    win.resizable(False, False)
    win.geometry("420x290")
    win.attributes("-topmost", True)

    win.update_idletasks()
    x = (win.winfo_screenwidth() - 420) // 2
    y = (win.winfo_screenheight() - 290) // 2
    win.geometry(f"+{x}+{y}")

    tk.Label(
        win, text="ElevenLabs TTS Setup", font=("Arial", 13, "bold"),
        fg="#e0e0e0", bg="#1a1a1a"
    ).pack(pady=(18, 4))

    tk.Label(
        win, text="Get your API key at elevenlabs.io/app/settings/api-keys",
        font=("Arial", 9), fg="#808080", bg="#1a1a1a"
    ).pack()

    tk.Label(
        win, text="API Key", font=("Arial", 10),
        fg="#c0c0c0", bg="#1a1a1a"
    ).pack(pady=(12, 2), anchor="w", padx=40)
    key_entry = tk.Entry(win, width=44, font=("Consolas", 10), show="*")
    key_entry.pack()
    key_entry.focus_set()

    tk.Label(
        win, text="Voice ID", font=("Arial", 10),
        fg="#c0c0c0", bg="#1a1a1a"
    ).pack(pady=(10, 2), anchor="w", padx=40)
    voice_entry = tk.Entry(win, width=44, font=("Consolas", 10))
    voice_entry.pack()

    status_label = tk.Label(
        win, text="", font=("Arial", 9),
        fg="#ff6060", bg="#1a1a1a"
    )
    status_label.pack(pady=(4, 0))

    def submit(event=None):
        k = key_entry.get().strip()
        v = voice_entry.get().strip()
        if not k and not v:
            status_label.config(text="Both fields are required")
            return
        if not k:
            status_label.config(text="API Key is required")
            key_entry.focus_set()
            return
        if not v:
            status_label.config(text="Voice ID is required")
            voice_entry.focus_set()
            return
        result[0] = k
        result[1] = v
        win.destroy()

    key_entry.bind("<Return>", lambda e: voice_entry.focus_set())
    voice_entry.bind("<Return>", submit)

    btn = tk.Button(
        win, text="Save & Launch", command=submit,
        font=("Arial", 10, "bold"), bg="#333", fg="#e0e0e0",
        activebackground="#555", activeforeground="#fff",
        relief="flat", padx=16, pady=4
    )
    btn.pack(pady=(6, 0))

    win.protocol("WM_DELETE_WINDOW", lambda: win.destroy())
    win.mainloop()
    return (result[0], result[1])


# ═══════════════════════════════════════════════════════════════════════════════
# DIMENSIONS
# ═══════════════════════════════════════════════════════════════════════════════
SIZE = 220
CX, CY = SIZE // 2, SIZE // 2
OUTER_R = 68
INNER_R = 52
EYE_R = 18


# ═══════════════════════════════════════════════════════════════════════════════
# BACKENDS
# ═══════════════════════════════════════════════════════════════════════════════
def groq_backend(api_key=None):
    key = api_key or os.environ.get("GROQ_API_KEY", "")
    def transcribe(path):
        try:
            from groq import Groq
            client = Groq(api_key=key)
            with open(path, "rb") as f:
                r = client.audio.transcriptions.create(
                    file=(os.path.basename(path), f.read()),
                    model="whisper-large-v3",
                    language="en",
                    response_format="text",
                )
            return (r if isinstance(r, str) else r.text).strip()
        except Exception as e:
            print(f"[CM7] Groq error: {e}")
            return ""
    return transcribe


def local_backend(model_size="base", device="cuda", compute="float16"):
    _m = {}
    def transcribe(path):
        try:
            if "model" not in _m:
                from faster_whisper import WhisperModel
                _m["model"] = WhisperModel(model_size, device=device, compute_type=compute)
            segs, _ = _m["model"].transcribe(path, language="en")
            return " ".join(s.text for s in segs).strip()
        except Exception as e:
            print(f"[CM7] Local error: {e}")
            return ""
    return transcribe


def mock_backend():
    def transcribe(path):
        time.sleep(1.2)
        return "mock transcription"
    return transcribe


# ═══════════════════════════════════════════════════════════════════════════════
# RECORDER
# ═══════════════════════════════════════════════════════════════════════════════
class Recorder:
    RATE  = 16000
    CHUNK = 1024

    def __init__(self):
        self.vu  = 0.0
        self._go = False

    def start(self): self._go = True
    def stop(self):  self._go = False

    def record(self):
        if not _HAS_PYAUDIO:
            while self._go:
                time.sleep(0.05)
            self.vu = 0.0
            return None

        import pyaudio as pa
        p = pa.PyAudio()
        fmt = pa.paInt16
        stream = p.open(format=fmt, channels=1, rate=self.RATE,
                        input=True, frames_per_buffer=self.CHUNK)
        frames = []
        while self._go:
            data = stream.read(self.CHUNK, exception_on_overflow=False)
            frames.append(data)
            samples = struct.unpack(f"{self.CHUNK}h", data)
            self.vu = min(1.0, max(abs(s) for s in samples) / 32768.0 * 2.8)

        stream.stop_stream()
        stream.close()
        self.vu = 0.0

        if not frames:
            p.terminate()
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        with wave.open(tmp.name, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(fmt))
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(frames))
        p.terminate()
        return tmp.name


# ═══════════════════════════════════════════════════════════════════════════════
# TTS PLAYER
# ═══════════════════════════════════════════════════════════════════════════════
class TTSPlayer:
    RATE = 16000
    CHUNK = 1024

    def __init__(self, api_key, voice_id, model_id="eleven_multilingual_v2"):
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._playing = False
        self._stream = None

    @property
    def is_playing(self):
        return self._playing

    def speak(self, text, on_done=None):
        if not _HAS_REQUESTS:
            print("[CM7] 'requests' package required for TTS. pip install requests")
            if on_done:
                on_done()
            return
        if not _HAS_PYAUDIO:
            print("[CM7] 'pyaudio' package required for TTS playback.")
            if on_done:
                on_done()
            return

        import pyaudio as pa
        self._playing = True
        p = None
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}"
            headers = {
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
            }
            body = {"text": text, "model_id": self._model_id}
            resp = requests.post(
                url, json=body, headers=headers,
                params={"output_format": "pcm_24000"},
                timeout=30,
            )
            if resp.status_code != 200:
                print(f"[CM7] TTS API error: {resp.status_code} - {resp.text[:200]}")
                return

            audio_data = resp.content
            # Ensure even length for 16-bit PCM
            if len(audio_data) % 2 != 0:
                audio_data = audio_data[:-1]
            if not audio_data:
                return

            p = pa.PyAudio()
            self._stream = p.open(
                format=pa.paInt16, channels=1, rate=24000,
                output=True, frames_per_buffer=2048,
            )
            # Play in chunks so we can still be stopped
            pos = 0
            chunk_size = 4096
            while pos < len(audio_data) and self._playing:
                end = min(pos + chunk_size, len(audio_data))
                self._stream.write(audio_data[pos:end])
                pos = end
        except Exception as e:
            print(f"[CM7] TTS error: {e}")
        finally:
            self._playing = False
            if self._stream:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except:
                    pass
                self._stream = None
            if p:
                p.terminate()
            if on_done:
                on_done()

    def stop(self):
        self._playing = False
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except:
                pass
            self._stream = None


# ═══════════════════════════════════════════════════════════════════════════════
# CM7 WIDGET - HAL EDITION
# ═══════════════════════════════════════════════════════════════════════════════
class CM7Widget:
    def __init__(
        self,
        parent=None,
        transcribe_fn=None,
        on_transcription=None,
        hotkey="f8",
        auto_paste=True,
        backend="groq",
        api_key=None,
        always_on_top=True,
        elevenlabs_api_key=None,
        elevenlabs_voice_id=None,
        tts_hotkey="f9",
    ):
        self.parent = parent
        self.on_transcription = on_transcription
        self.hotkey = hotkey
        self.auto_paste = auto_paste
        self.always_on_top = always_on_top
        self._tts_hotkey = tts_hotkey

        if transcribe_fn:
            self._transcribe = transcribe_fn
        elif backend == "groq":
            self._transcribe = groq_backend(api_key)
        elif backend == "local":
            self._transcribe = local_backend()
        elif backend == "mock":
            self._transcribe = mock_backend()
        else:
            self._transcribe = groq_backend(api_key)

        if elevenlabs_api_key and elevenlabs_voice_id:
            self._tts = TTSPlayer(elevenlabs_api_key, elevenlabs_voice_id)
        else:
            self._tts = None

        self._rec = Recorder()
        self._state = "ready"
        self._root = None
        self._canvas = None
        self._dx = self._dy = 0
        self._level = 0.0

        # Canvas items
        self._glow_rings = []
        self._eye_layers = []
        self._eye_core = None
        self._eye_highlight = None
        self._reflections = []
        self._status_text = None
        self._state_ring = None

    def run(self):
        root = tk.Tk()
        self._root = root
        root.title("CM7")
        root.configure(bg="#1a1a1a")
        root.resizable(False, False)
        root.geometry(f"{SIZE}x{SIZE}")
        root.overrideredirect(True)
        if self.always_on_top:
            root.attributes("-topmost", True)
        if not _IS_MAC:
            root.attributes("-transparentcolor", "#1a1a1a")
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"+{sw - SIZE - 40}+{40}")
        root.bind("<Button-1>", self._drag_start)
        root.bind("<B1-Motion>", self._drag_move)
        root.bind("<Button-3>", lambda e: self._quit())
        self._widget_size = SIZE
        self._resize_edge = None

        canvas = tk.Canvas(root, width=SIZE, height=SIZE,
                           bg="#1a1a1a", highlightthickness=0)
        canvas.pack()
        self._canvas = canvas
        self._draw()
        self._register_hotkey()
        root.after(25, self._tick)
        root.mainloop()

    def get_canvas(self):
        if not self.parent:
            raise ValueError("Set parent= to embed")
        self._root = self.parent
        c = tk.Canvas(self.parent, width=SIZE, height=SIZE,
                      bg="#1a1a1a", highlightthickness=0)
        self._canvas = c
        self._draw()
        self._register_hotkey()
        self.parent.after(25, self._tick)
        return c

    def _generate_glow_frames(self, base_img):
        """Pre-generate glow frames by boosting red/warm pixels at various intensities."""
        import numpy as np
        frames = []
        arr = np.array(base_img, dtype=np.float32)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        a = arr[:, :, 3] if arr.shape[2] == 4 else np.full_like(r, 255.0)

        # Mask: pixels where red is dominant (the eye glow area)
        red_mask = np.clip((r - np.maximum(g, b)) / 80.0, 0, 1)
        # Also include darker warm areas (the lens reflections)
        warm_mask = np.clip((r * 0.5 + g * 0.3) / 120.0, 0, 1)
        glow_mask = np.maximum(red_mask, warm_mask * 0.4)

        for i in range(16):
            boost = i / 15.0  # 0.0 to 1.0
            nr = np.clip(r + glow_mask * boost * 120, 0, 255)
            ng = np.clip(g + glow_mask * boost * 30, 0, 255)
            nb = np.clip(b + glow_mask * boost * 10, 0, 255)
            frame = np.stack([nr, ng, nb, a], axis=-1).astype(np.uint8)
            pil_frame = Image.fromarray(frame, "RGBA")
            frames.append(ImageTk.PhotoImage(pil_frame))
        return frames

    def _generate_blue_frames(self, base_img):
        """Pre-generate blue glow frames for speaking state."""
        import numpy as np
        frames = []
        arr = np.array(base_img, dtype=np.float32)
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        a = arr[:, :, 3] if arr.shape[2] == 4 else np.full_like(r, 255.0)

        red_mask = np.clip((r - np.maximum(g, b)) / 80.0, 0, 1)
        warm_mask = np.clip((r * 0.5 + g * 0.3) / 120.0, 0, 1)
        glow_mask = np.maximum(red_mask, warm_mask * 0.4)

        for i in range(16):
            boost = i / 15.0
            nr = np.clip(r + glow_mask * boost * 20, 0, 255)
            ng = np.clip(g + glow_mask * boost * 50, 0, 255)
            nb = np.clip(b + glow_mask * boost * 140, 0, 255)
            frame = np.stack([nr, ng, nb, a], axis=-1).astype(np.uint8)
            pil_frame = Image.fromarray(frame, "RGBA")
            frames.append(ImageTk.PhotoImage(pil_frame))
        return frames

    def _draw(self):
        c = self._canvas

        # ═══ HAL EYE IMAGE WITH GLOW FRAMES ═══
        self._state_ring = None
        self._glow_frames = []
        self._blue_frames = []
        self._base_frame = None
        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hal_eye.png")
        if _HAS_PIL and os.path.exists(img_path):
            pil_img = Image.open(img_path).convert("RGBA")
            self._base_frame = ImageTk.PhotoImage(pil_img)
            self._glow_frames = self._generate_glow_frames(pil_img)
            self._blue_frames = self._generate_blue_frames(pil_img)
            self._img_item = c.create_image(CX, CY, image=self._base_frame, anchor="center")
        else:
            c.create_oval(20, 20, SIZE - 20, SIZE - 20, fill="#300000", outline="#555")
            c.create_oval(50, 50, SIZE - 50, SIZE - 50, fill="#cc0000", outline="")
            self._img_item = None

        # ═══ CLICK BINDING ═══
        c.tag_bind("all", "<ButtonPress-1>", lambda e: self._press())
        c.tag_bind("all", "<ButtonRelease-1>", lambda e: self._release())

    def _tick(self):
        if not self._canvas:
            return

        c = self._canvas
        t = time.time()
        st = self._state

        # ═══ UPDATE IMAGE GLOW ═══
        if self._img_item and self._glow_frames:
            if st == "recording":
                # Pulse the red glow: sine wave maps to frame 4-15
                pulse = (math.sin(t * 6) + 1) / 2
                idx = int(4 + pulse * 11)
                c.itemconfig(self._img_item, image=self._glow_frames[min(idx, 15)])
            elif st == "processing":
                # Slower orange pulse: frames 2-10
                pulse = (math.sin(t * 4) + 1) / 2
                idx = int(2 + pulse * 8)
                c.itemconfig(self._img_item, image=self._glow_frames[min(idx, 15)])
            elif st == "speaking":
                # Blue pulse
                pulse = (math.sin(t * 3.5) + 1) / 2
                idx = int(3 + pulse * 12)
                c.itemconfig(self._img_item, image=self._blue_frames[min(idx, 15)])
            else:
                # Idle: subtle breathing glow
                breath = (math.sin(t * 1.2) + 1) / 2
                idx = int(breath * 3)
                c.itemconfig(self._img_item, image=self._glow_frames[min(idx, 15)])

        # ═══ UPDATE STATE RING ═══
        if self._state_ring:
            if st == "recording":
                bright = int(180 + 75 * ((math.sin(t * 8) + 1) / 2))
                c.itemconfig(self._state_ring,
                             outline=f"#{min(255, bright):02x}1515", width=4)
            elif st == "processing":
                bright = int(140 + 60 * ((math.sin(t * 5) + 1) / 2))
                c.itemconfig(self._state_ring,
                             outline=f"#{min(255, bright):02x}{int(bright*0.5):02x}10", width=4)
            elif st == "speaking":
                bright = int(100 + 60 * ((math.sin(t * 4) + 1) / 2))
                c.itemconfig(self._state_ring,
                             outline=f"#15{int(bright*0.6):02x}{min(255, bright):02x}", width=4)
            else:
                c.itemconfig(self._state_ring, outline="#1a1a1a", width=4)

        if self._root:
            self._root.after(40, self._tick)

    def _press(self):
        if self._state != "ready":
            return
        self._state = "recording"
        self._rec.start()
        threading.Thread(target=self._run, daemon=True).start()

    def _release(self):
        if self._state == "recording":
            self._rec.stop()

    def _run(self):
        path = self._rec.record()
        if path:
            self._state = "processing"
            text = self._transcribe(path)
            try:
                os.unlink(path)
            except:
                pass
            if text:
                print(f"[CM7] {text}")
                if self.on_transcription:
                    self.on_transcription(text)
                elif self.auto_paste and _HAS_PASTE:
                    self._paste(text)
        self._state = "ready"

    def _paste(self, text):
        try:
            time.sleep(0.15)
            if _HAS_PYNPUT:
                ctrl = pynput_kb.Controller()
                ctrl.type(text)
            else:
                pyperclip.copy(text)
                time.sleep(0.08)
                mod = "command" if _IS_MAC else "ctrl"
                pyautogui.hotkey(mod, "v")
        except Exception as e:
            print(f"[CM7] Paste error: {e}")

    def _tts_toggle(self):
        if not self._tts:
            print("[CM7] TTS not configured. Run with --tts-setup")
            return
        if self._state == "speaking":
            self._tts.stop()
            self._state = "ready"
            return
        if self._state != "ready":
            return
        if not _HAS_PASTE:
            print("[CM7] pyperclip/pyautogui required for TTS")
            return
        self._state = "speaking"
        threading.Thread(target=self._tts_grab_and_speak, daemon=True).start()

    @staticmethod
    def _play_click():
        """Play a short confirmation click sound."""
        if not _HAS_PYAUDIO:
            return
        try:
            import pyaudio as pa
            rate = 44100
            duration = 0.035
            n = int(rate * duration)
            samples = []
            for i in range(n):
                t = i / rate
                env = max(0.0, 1.0 - i / n)  # Fast decay
                val = env * math.sin(2 * math.pi * 1800 * t) * 0.4
                samples.append(int(val * 32767))
            data = struct.pack(f"{n}h", *samples)
            p = pa.PyAudio()
            s = p.open(format=pa.paInt16, channels=1, rate=rate, output=True)
            s.write(data)
            s.stop_stream()
            s.close()
            p.terminate()
        except:
            pass

    def _tts_grab_and_speak(self):
        try:
            # Speak whatever is on the clipboard.
            # User workflow: select text, Ctrl+C, then F9.
            text = pyperclip.paste()
            if not text or not text.strip():
                print("[CM7] Clipboard empty. Copy text first (Ctrl+C), then F9.")
                self._state = "ready"
                return
            text = text.strip()
            self._play_click()
            print(f"[CM7] Speaking: {text[:80]}...")
            self._tts.speak(text, on_done=lambda: setattr(self, '_state', 'ready'))
        except Exception as e:
            print(f"[CM7] TTS error: {e}")
            self._state = "ready"

    def _register_hotkey(self):
        if not _HAS_PYNPUT:
            return

        # Resolve hotkey names to pynput Key objects
        keys = self.hotkey.lower().split("+")
        main_key = _PYNPUT_KEY_MAP.get(keys[-1])
        mod_keys = [_PYNPUT_KEY_MAP.get(m) for m in keys[:-1]]
        mod_keys = [m for m in mod_keys if m is not None]

        tts_key = None
        if self._tts:
            tts_key = _PYNPUT_KEY_MAP.get(self._tts_hotkey.lower().split("+")[-1])

        pressed_keys = set()

        def on_press(key):
            pressed_keys.add(key)
            if key == main_key:
                if all(m in pressed_keys for m in mod_keys):
                    if self._root:
                        self._root.after(0, self._press)
            if tts_key and key == tts_key:
                if self._root:
                    self._root.after(0, self._tts_toggle)

        def on_release(key):
            pressed_keys.discard(key)
            if key == main_key:
                if self._root:
                    self._root.after(0, self._release)

        self._listener = pynput_kb.Listener(on_press=on_press, on_release=on_release)
        self._listener.daemon = True
        self._listener.start()

    def _apply_resize(self, new_size):
        new_size = max(100, min(400, new_size))
        if new_size == self._widget_size:
            return
        self._widget_size = new_size

        img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hal_eye.png")
        if _HAS_PIL and os.path.exists(img_path):
            pil_img = Image.open(img_path).convert("RGBA")
            pil_img = pil_img.resize((new_size, new_size), Image.LANCZOS)
            self._base_frame = ImageTk.PhotoImage(pil_img)
            self._glow_frames = self._generate_glow_frames(pil_img)
            self._blue_frames = self._generate_blue_frames(pil_img)

        self._root.geometry(f"{new_size}x{new_size}")
        self._canvas.config(width=new_size, height=new_size)
        if self._img_item:
            self._canvas.coords(self._img_item, new_size // 2, new_size // 2)

    def _drag_start(self, e):
        # Detect if click is near a corner (within 20px)
        margin = 20
        sz = self._widget_size
        near_right = e.x > sz - margin
        near_bottom = e.y > sz - margin
        if near_right and near_bottom:
            self._resize_edge = True
            self._resize_start_x = e.x_root
            self._resize_start_y = e.y_root
            self._resize_start_size = self._widget_size
        else:
            self._resize_edge = False
            self._dx = e.x_root - self._root.winfo_x()
            self._dy = e.y_root - self._root.winfo_y()

    def _drag_move(self, e):
        try:
            if self._resize_edge:
                dx = e.x_root - self._resize_start_x
                dy = e.y_root - self._resize_start_y
                delta = max(dx, dy)
                self._apply_resize(self._resize_start_size + delta)
            else:
                self._root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")
        except:
            pass

    def _quit(self):
        if self._tts and self._tts.is_playing:
            self._tts.stop()
        if hasattr(self, '_listener'):
            try:
                self._listener.stop()
            except:
                pass
        try:
            self._canvas = None
            self._root.quit()
            self._root.destroy()
        except:
            pass


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["groq", "local", "mock"], default="groq")
    p.add_argument("--hotkey", default="f8")
    p.add_argument("--no-paste", action="store_true")
    p.add_argument("--api-key", default=None, help="Groq API key (overrides config)")
    p.add_argument("--setup", action="store_true", help="Re-enter Groq API key")
    p.add_argument("--tts-setup", action="store_true", help="Configure ElevenLabs TTS")
    p.add_argument("--tts-hotkey", default="f9", help="Hotkey for TTS (default: f9)")
    args = p.parse_args()

    api_key = None
    if args.backend == "groq":
        # Priority: CLI arg > config file > env var > prompt
        if args.api_key:
            api_key = args.api_key
        elif args.setup:
            api_key = prompt_api_key()
            if api_key:
                save_api_key(api_key)
                print("[CM7] API key saved.")
            else:
                print("[CM7] No key entered, exiting.")
                exit(1)
        else:
            api_key = load_api_key() or os.environ.get("GROQ_API_KEY")
            if not api_key:
                print("[CM7] No Groq API key found. Opening setup...")
                api_key = prompt_api_key()
                if api_key:
                    save_api_key(api_key)
                    print("[CM7] API key saved.")
                else:
                    print("[CM7] No key entered, exiting.")
                    exit(1)

    # ElevenLabs TTS config
    el_config = {"api_key": None, "voice_id": None}
    if args.tts_setup:
        result = prompt_elevenlabs_config()
        if result[0] and result[1]:
            save_elevenlabs_config(result[0], result[1])
            el_config = {"api_key": result[0], "voice_id": result[1]}
            print("[CM7] ElevenLabs config saved.")
        else:
            print("[CM7] ElevenLabs setup cancelled.")
    else:
        el_config = load_elevenlabs_config()
        if not el_config["api_key"]:
            el_config["api_key"] = os.environ.get("ELEVENLABS_API_KEY")
        if not el_config["voice_id"]:
            el_config["voice_id"] = os.environ.get("ELEVENLABS_VOICE_ID")

    CM7Widget(
        hotkey=args.hotkey,
        backend=args.backend,
        api_key=api_key,
        auto_paste=not args.no_paste,
        on_transcription=(lambda t: None) if args.no_paste else None,
        elevenlabs_api_key=el_config.get("api_key"),
        elevenlabs_voice_id=el_config.get("voice_id"),
        tts_hotkey=args.tts_hotkey,
    ).run()
