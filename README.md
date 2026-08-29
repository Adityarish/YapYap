# SpeechForge Dictation

An AI-powered speech dictation desktop application that runs **completely locally** — no cloud, no LLMs, no privacy compromise. Real-time speech is cleaned, corrected, and pasted to your cursor in under 1500ms.

## Quick Start

### Option 1: Download ZIP (Recommended)

1. [**Download the latest ZIP**](https://github.com/ImAust1n/YapYap/archive/refs/heads/main.zip)
2. Extract the folder
3. Open the `Speech2Text2` folder
4. Double-click **`Start.bat`** — that's it!

The launcher will automatically:
- Create a Python virtual environment
- Install all dependencies
- Start the backend server
- Launch the Electron desktop app

### Option 2: Clone with Git

```bash
git clone https://github.com/ImAust1n/YapYap.git
cd YapYap/Speech2Text2
Start.bat
```

## Batch Scripts

| Script | Purpose |
|---|---|
| `Start.bat` | Installs dependencies and launches the app |
| `Stop.bat` | Stops the backend server and closes all windows |
| `Update.bat` | Pulls latest code and updates dependencies |
| `Uninstall.bat` | Removes `.venv`, `node_modules`, models, and logs |

## How to Use

1. Run `Start.bat` — the app will appear in your system tray
2. Press **`Ctrl+Shift+D`** anywhere to activate dictation
3. Speak — text appears live at your cursor
4. Press the shortcut again or wait for the session to end

## Architecture

- **Backend** (`backend/app.py`) — FastAPI server running the STT + NLP pipeline
- **Frontend** (`electron-app/`) — Electron overlay app with global hotkey
- **Pipeline**: Audio → Whisper STT → Filler Removal → Repetition Detection → Grammar Correction → Tone Control → Formatting → Paste

## Requirements

- Windows 10/11
- Python 3.10+
- Node.js 18+
- Git

All Python and Node dependencies are installed automatically by `Start.bat`.

## Development

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

# Frontend (separate terminal)
cd electron-app
npm install
npm start
```
