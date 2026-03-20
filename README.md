# CM7 Dictation Widget

HAL 9000-themed voice dictation widget with text-to-speech. Hold **F8** to dictate, press **F9** to read clipboard text aloud using your ElevenLabs voice.

Works on **Windows** and **macOS**.

![Python](https://img.shields.io/badge/python-3.8+-blue)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run:
   ```
   # Windows
   run_dictation.bat

   # macOS
   bash run_dictation.sh
   ```
   On first launch you'll be prompted to enter your **Groq API key**.
   Get one free at [console.groq.com](https://console.groq.com).

3. (Optional) Set up text-to-speech with your ElevenLabs voice:
   ```
   python3 cm7_dictation_v2.py --tts-setup
   ```
   You'll need your **API key** and **Voice ID** from [elevenlabs.io](https://elevenlabs.io).

### macOS Notes

- On first run, macOS will ask for **Accessibility** and **Microphone** permissions — grant both.
- Install PortAudio for pyaudio: `brew install portaudio` before `pip install pyaudio`.

## Usage

| Action | Effect |
|--------|--------|
| Hold **F8** | Record audio |
| Release **F8** | Transcribe & paste text at cursor |
| **Ctrl+C** then **F9** | Read clipboard text aloud (ElevenLabs) |
| Press **F9** (while speaking) | Stop playback |
| Click the eye | Same as F8 |
| Right-click | Quit |
| Drag | Move the widget |

The eye glows **red/orange** while recording and **blue/cyan** while speaking.

## Options

```
python3 cm7_dictation_v2.py --backend groq     # (default) Groq cloud API
python3 cm7_dictation_v2.py --backend local    # Local faster-whisper (needs GPU)
python3 cm7_dictation_v2.py --backend mock     # Test mode
python3 cm7_dictation_v2.py --hotkey ctrl+f8   # Custom dictation hotkey
python3 cm7_dictation_v2.py --tts-hotkey f10   # Custom TTS hotkey (default: f9)
python3 cm7_dictation_v2.py --no-paste         # Transcribe only, don't auto-paste
python3 cm7_dictation_v2.py --api-key gsk_...  # Pass Groq key directly
python3 cm7_dictation_v2.py --setup            # Re-enter Groq API key
python3 cm7_dictation_v2.py --tts-setup        # Configure ElevenLabs TTS
```

## API Key Storage

Keys are saved to `config.ini` (gitignored) in the project directory. They are **never** committed to the repo.
