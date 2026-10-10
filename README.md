# AiCON Source Code

This repository contains separate applications from the provided AiCON archive:

- `aicon_unified_app.py`: a standalone Gradio interface.
- `Milaan_Demo_Kit/milaan/`: Milaan backend and frontend.
- `Milaan_Demo_Kit/demo-store/`: simulated store for demo payment scenarios.
- `matching/`: name similarity and matching-related code.
- `test_assets/`: sample inputs.
- `models/`: pre-existing model artifacts (not necessarily used by running applications).

## Getting started

Follow `Milaan_Demo_Kit/README_FIRST.md` and the component-level instructions.
For the Gradio app, see `requirements.txt` and `START_AICON_APP.bat`.

Copy `Milaan_Demo_Kit/milaan/backend/.env.example` to `.env` and configure as needed.
For the Gradio app, `API_KEY` must be supplied via a local environment variable or `.env` file. Never commit secrets.

The original ZIP included a virtual environment and runtime databases/uploads. Those are excluded from version control; installing dependencies and initializing a new database may be necessary.

## Upload on Windows

1. Extract this entire ZIP file.
2. Open the `AiCON` folder.
3. Double-click `PUSH_TO_GITHUB.bat`.
4. Complete GitHub authentication when prompted; do not share your password or personal access token in chat.
5. Confirm all files are visible at `https://github.com/bil332204-code/AiCON-2026-Milaan`.

The push script is configured only for `bil332204-code/AiCON-2026-Milaan` and does not use force-push.
