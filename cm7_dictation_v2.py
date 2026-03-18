#!/usr/bin/env python3
"""
CM7 Dictation Widget - HAL Edition
Hold F8 (or click) to record, release to transcribe and paste.
"""

import tkinter as tk
import threading
import time
import os
import tempfile
import wave
import struct
import math
import argparse
import configparser
from typing import Callable, Optional

try:
    import pyaudio
    _HAS_PYAUDIO = True
except ImportError:
    _HAS_PYAUDIO = False

try:
    import keyboard
    _HAS_KEYBOARD = True
except ImportError:
    _HAS_KEYBOARD = False

try:
    import pyperclip
    import pyautogui
    _HAS_PASTE = True
except ImportError:
    _HAS_PASTE = False


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


# ═══════════════════════════════════════════════════════════════════════════════
# DIMENSIONS
# ═══════════════════════════════════════════════════════════════════════════════
SIZE = 160
CX, CY = SIZE // 2, SIZE // 2
OUTER_R = 68
INNER_R = 52  # Silver ring (16px)
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
    ):
        self.parent = parent
        self.on_transcription = on_transcription
        self.hotkey = hotkey
        self.auto_paste = auto_paste
        self.always_on_top = always_on_top

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
        root.attributes("-transparentcolor", "#1a1a1a")
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"+{sw - SIZE - 40}+{40}")
        root.bind("<Button-1>", self._drag_start)
        root.bind("<B1-Motion>", self._drag_move)
        root.bind("<Button-3>", lambda e: self._quit())

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

    def _draw(self):
        c = self._canvas

        # ═══ OUTER SHADOW - 32 layers ═══
        for s in range(32, 0, -1):
            t = s / 32
            alpha = int(5 + t * 20)
            offset = s * 0.25
            c.create_oval(
                CX - OUTER_R + offset, CY - OUTER_R + offset + 3,
                CX + OUTER_R + offset, CY + OUTER_R + offset + 3,
                fill=f"#{alpha:02x}{alpha:02x}{alpha:02x}", outline=""
            )

        # ═══ OUTER METALLIC RING - 256 layers ═══
        ring_thickness = OUTER_R - INNER_R
        for i in range(256):
            t = i / 256
            # Very bright silver - near white at edges
            base = 180 + 50 * t
            specular = 60 * math.exp(-((t - 0.3) ** 2) * 12)
            fresnel = 50 * (1 - t) ** 1.5  # Strong bright outer edge
            brightness = int(min(255, base + specular + fresnel))

            # Cool silver tint
            r = min(255, brightness)
            g = min(255, brightness + 3)
            b = min(255, brightness + 8)

            inset = t * ring_thickness
            c.create_oval(
                CX - OUTER_R + inset, CY - OUTER_R + inset,
                CX + OUTER_R - inset, CY + OUTER_R - inset,
                fill=f"#{r:02x}{g:02x}{b:02x}", outline=""
            )

        # Ring specular highlight (top) - 16 layers
        for w in range(16, 0, -1):
            t = w / 16
            alpha = int(80 + 120 * t * t)
            c.create_arc(
                CX - OUTER_R + 3 + w * 0.5, CY - OUTER_R + 3 + w * 0.5,
                CX + OUTER_R - 3 - w * 0.5, CY + OUTER_R - 3 - w * 0.5,
                start=20, extent=140, style="arc",
                outline=f"#{min(255,alpha):02x}{min(255,alpha):02x}{min(255,alpha):02x}", width=1
            )

        # Ring shadow (bottom) - 16 layers
        for w in range(16, 0, -1):
            t = w / 16
            alpha = int(10 + 30 * t)
            c.create_arc(
                CX - OUTER_R + 3 + w * 0.5, CY - OUTER_R + 3 + w * 0.5,
                CX + OUTER_R - 3 - w * 0.5, CY + OUTER_R - 3 - w * 0.5,
                start=200, extent=140, style="arc",
                outline=f"#{alpha:02x}{alpha:02x}{alpha:02x}", width=1
            )

        # ═══ DARK LENS - 256 layers ═══
        lens_depth = INNER_R - 8
        for i in range(256):
            t = i / 256
            # Deep glass with subtle red/brown tint
            # Vignette effect - darker at edges
            vignette = 1 - (1 - t) ** 0.5
            base_r = int(28 * (1 - vignette * 0.7))
            base_g = int(20 * (1 - vignette * 0.8))
            base_b = int(18 * (1 - vignette * 0.85))

            inset = t * lens_depth
            c.create_oval(
                CX - INNER_R + inset, CY - INNER_R + inset,
                CX + INNER_R - inset, CY + INNER_R - inset,
                fill=f"#{max(4,base_r):02x}{max(2,base_g):02x}{max(2,base_b):02x}", outline=""
            )

        # ═══ LENS REFLECTIONS - soft multipass ═══
        # Primary curved reflection - 24 layers
        for w in range(24, 0, -1):
            t = w / 24
            alpha = int(18 + 28 * t)
            spread = w * 0.4
            self._reflections.append(c.create_arc(
                CX - INNER_R + 5 + spread, CY - INNER_R + 3 + spread * 0.5,
                CX + INNER_R - 5 - spread, CY + 14 - spread * 0.3,
                start=10, extent=160, style="arc",
                outline=f"#{alpha:02x}{int(alpha*0.88):02x}{int(alpha*0.82):02x}", width=1
            ))

        # Secondary reflection - 16 layers
        for w in range(16, 0, -1):
            t = w / 16
            alpha = int(15 + 20 * t)
            spread = w * 0.3
            self._reflections.append(c.create_arc(
                CX - INNER_R + 8 + spread, CY - INNER_R + 6 + spread * 0.5,
                CX + INNER_R - 8 - spread, CY + 10 - spread * 0.2,
                start=20, extent=140, style="arc",
                outline=f"#{alpha:02x}{int(alpha*0.9):02x}{int(alpha*0.86):02x}", width=1
            ))

        # Bottom right reflection - 20 layers
        for i in range(20):
            t = i / 20
            alpha = int(12 + 18 * t)
            self._reflections.append(c.create_arc(
                CX - 2 - i * 0.3, CY + 6 - i * 0.2,
                CX + INNER_R - 8 + i * 0.4, CY + INNER_R - 8 + i * 0.4,
                start=270, extent=60, style="chord",
                fill=f"#{alpha:02x}{int(alpha*0.92):02x}{int(alpha*0.88):02x}", outline=""
            ))

        # ═══ EYE GLOW - 32 rings (stay within lens) ═══
        self._glow_rings = []
        max_glow = INNER_R - EYE_R - 4  # Stay within lens, don't cover ring
        for i in range(32, 0, -1):
            extent = int(i * max_glow / 32)
            ring = c.create_oval(
                CX - EYE_R - extent, CY - EYE_R - extent,
                CX + EYE_R + extent, CY + EYE_R + extent,
                fill="#180600", outline=""
            )
            self._glow_rings.append(ring)

        # ═══ EYE CENTER - 256 layers ═══
        self._eye_layers = []
        for i in range(256):
            t = i / 256

            # Ultra-smooth gradient with proper color science
            # Using smooth hermite interpolation between color stops
            if t < 0.25:
                # Deep crimson to red
                tt = t / 0.25
                tt = tt * tt * (3 - 2 * tt)  # Smoothstep
                r = int(40 + tt * 150)
                g = int(tt * 15)
                b = int(tt * 5)
            elif t < 0.5:
                # Red to orange-red
                tt = (t - 0.25) / 0.25
                tt = tt * tt * (3 - 2 * tt)
                r = int(190 + tt * 55)
                g = int(15 + tt * 50)
                b = int(5 + tt * 5)
            elif t < 0.75:
                # Orange-red to orange
                tt = (t - 0.5) / 0.25
                tt = tt * tt * (3 - 2 * tt)
                r = int(245 + tt * 10)
                g = int(65 + tt * 70)
                b = int(10 + tt * 15)
            else:
                # Orange to bright yellow-white core
                tt = (t - 0.75) / 0.25
                tt = tt * tt * (3 - 2 * tt)
                r = 255
                g = int(135 + tt * 105)
                b = int(25 + tt * 180)

            color = f"#{min(255,r):02x}{min(255,g):02x}{min(255,b):02x}"
            inset = t * (EYE_R - 1)
            layer = c.create_oval(
                CX - EYE_R + inset, CY - EYE_R + inset,
                CX + EYE_R - inset, CY + EYE_R - inset,
                fill=color, outline=""
            )
            self._eye_layers.append(layer)

        # Bright core - 32 layers
        for i in range(32, 0, -1):
            t = i / 32
            r = 255
            g = int(220 + (1 - t) * 35)
            b = int(180 + (1 - t) * 60)
            radius = 1 + t * 5
            c.create_oval(
                CX - radius, CY - radius,
                CX + radius, CY + radius,
                fill=f"#{r:02x}{min(255,g):02x}{min(255,b):02x}", outline=""
            )

        self._eye_core = c.create_oval(
            CX - 2, CY - 2, CX + 2, CY + 2,
            fill="#fffaf5", outline=""
        )

        # Eye specular highlight - 20 layers
        for i in range(20, 0, -1):
            t = i / 20
            alpha = int(160 + 80 * t)
            g_val = int(alpha * 0.55)
            b_val = int(alpha * 0.35)
            spread = i * 0.3
            self._eye_highlight = c.create_oval(
                CX - EYE_R + 2 + spread * 0.3, CY - EYE_R + 1 + spread * 0.2,
                CX - 5 + spread, CY - EYE_R + 8 + spread * 0.3,
                fill=f"#{min(255,alpha):02x}{g_val:02x}{b_val:02x}", outline=""
            )

        # ═══ F8 LABEL ═══
        c.create_text(
            12, 14,
            text="F8",
            fill="#505050",
            font=("Arial", 9, "bold"),
            anchor="nw"
        )

        # ═══ CLICK BINDING ═══
        c.tag_bind("all", "<ButtonPress-1>", lambda e: self._press())
        c.tag_bind("all", "<ButtonRelease-1>", lambda e: self._release())

    def _tick(self):
        if not self._canvas:
            return

        c = self._canvas
        t = time.time()
        st = self._state

        # Target level
        if st == "recording":
            target = max(0.3, self._rec.vu)
        elif st == "processing":
            pulse = (math.sin(t * 4) + 1) / 2
            target = 0.5 + pulse * 0.4
        else:
            # Subtle breathing
            target = 0.15 + (math.sin(t * 1.5) + 1) / 2 * 0.1

        # Smooth interpolation
        self._level += (target - self._level) * 0.15
        level = self._level

        # ═══ UPDATE GLOW ═══
        num_rings = len(self._glow_rings)
        for i, ring in enumerate(self._glow_rings):
            dist = (num_rings - i) / num_rings
            # Quadratic falloff for ultra-smooth realistic glow
            falloff = (1 - dist ** 0.7) ** 2
            if st == "recording":
                # Intense red-orange glow with ripple
                pulse = (math.sin(t * 8 + i * 0.08) + 1) / 2
                ripple = (math.sin(t * 12 - i * 0.15) + 1) / 2 * 0.15
                intensity = int((120 + 100 * level + 40 * pulse + 20 * ripple) * falloff)
                r = min(255, intensity)
                g = min(255, int(intensity * 0.38))
                b = min(255, int(intensity * 0.08))
            elif st == "processing":
                # Pulsing orange with wave
                pulse = (math.sin(t * 5 + i * 0.06) + 1) / 2
                intensity = int((80 + 60 * pulse) * falloff)
                r = min(255, intensity)
                g = min(255, int(intensity * 0.48))
                b = min(255, int(intensity * 0.08))
            else:
                # Subtle warm breathing glow
                breath = (math.sin(t * 1.5) + 1) / 2
                intensity = int((30 + 35 * level + 10 * breath) * falloff)
                r = min(255, intensity)
                g = min(255, int(intensity * 0.28))
                b = min(255, int(intensity * 0.05))
            c.itemconfig(ring, fill=f"#{r:02x}{g:02x}{b:02x}")

        # ═══ UPDATE EYE CORE ═══
        if st == "recording":
            pulse = (math.sin(t * 10) + 1) / 2
            core_bright = int(200 + 55 * pulse)
            c.itemconfig(self._eye_core, fill=f"#ff{core_bright:02x}{core_bright-40:02x}")
            c.itemconfig(self._eye_highlight, fill="#ffb080")
        elif st == "processing":
            pulse = (math.sin(t * 6) + 1) / 2
            c.itemconfig(self._eye_core, fill=f"#ff{int(180+40*pulse):02x}{int(140+30*pulse):02x}")
            c.itemconfig(self._eye_highlight, fill="#ff9060")
        else:
            c.itemconfig(self._eye_core, fill="#ffe0c0")
            c.itemconfig(self._eye_highlight, fill="#ff9060")

        if self._root:
            self._root.after(25, self._tick)

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
            if _HAS_KEYBOARD:
                keyboard.write(text)
            else:
                pyperclip.copy(text)
                time.sleep(0.08)
                pyautogui.hotkey("ctrl", "v")
        except Exception as e:
            print(f"[CM7] Paste error: {e}")

    def _register_hotkey(self):
        if not _HAS_KEYBOARD:
            return
        try:
            keys = self.hotkey.lower().split("+")
            main = keys[-1]
            mods = keys[:-1]

            def on_press(e):
                if all(keyboard.is_pressed(m) for m in mods):
                    if self._root:
                        self._root.after(0, self._press)

            def on_release(e):
                if self._root:
                    self._root.after(0, self._release)

            keyboard.on_press_key(main, on_press)
            keyboard.on_release_key(main, on_release)
        except Exception as e:
            print(f"[CM7] Hotkey failed: {e}")

    def _drag_start(self, e):
        self._dx = e.x_root - self._root.winfo_x()
        self._dy = e.y_root - self._root.winfo_y()

    def _drag_move(self, e):
        try:
            self._root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")
        except:
            pass

    def _quit(self):
        if _HAS_KEYBOARD:
            try:
                keyboard.unhook_all()
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
    p.add_argument("--setup", action="store_true", help="Re-enter API key")
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

    CM7Widget(
        hotkey=args.hotkey,
        backend=args.backend,
        api_key=api_key,
        auto_paste=not args.no_paste,
        on_transcription=(lambda t: None) if args.no_paste else None,
    ).run()
