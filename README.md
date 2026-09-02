# StoryForge

StoryForge is a local-first studio for turning an idea into a researched, narrated documentary video.

## Phase 1: foundation

This first version exposes a small API that confirms the app is running and accepts a documentary topic. Future phases will add local AI generation, research, scripts, scenes, voice, visuals, and video assembly.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to use the interactive API screen.
