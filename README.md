# CM7 Dictation Widget

HAL 9000-themed voice dictation widget. Hold **F8** (or click the eye) to record, release to transcribe and paste using Groq's Whisper API.

![Python](https://img.shields.io/badge/python-3.8+-blue)

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run:
   ```
   run_dictation.bat
   ```
   On first launch you'll be prompted to enter your **Groq API key**.
   Get one free at [console.groq.com](https://console.groq.com).

3. To change your API key later:
   ```
   py cm7_dictation_v2.py --setup
   ```

## Usage

| Action | Effect |
|--------|--------|
| Hold **F8** | Record audio |
| Release **F8** | Transcribe & paste text at cursor |
| Click the eye | Same as F8 |
| Right-click | Quit |
| Drag | Move the widget |

## Options

```
py cm7_dictation_v2.py --backend groq     # (default) Groq cloud API
py cm7_dictation_v2.py --backend local    # Local faster-whisper (needs GPU)
py cm7_dictation_v2.py --backend mock     # Test mode
py cm7_dictation_v2.py --hotkey ctrl+f8   # Custom hotkey
py cm7_dictation_v2.py --no-paste         # Transcribe only, don't auto-paste
py cm7_dictation_v2.py --api-key gsk_...  # Pass key directly
py cm7_dictation_v2.py --setup            # Re-enter API key
```

## API Key Storage

Your key is saved to `config.ini` (gitignored) in the project directory. It is **never** committed to the repo.
