# AiCON — Milaan

Codebase for the AiCON 2026 project. This archive contains several components:

- `aicon_unified_app.py`: standalone Gradio interface.
- `Milaan_Demo_Kit/milaan/`: backend and frontend.
- `Milaan_Demo_Kit/demo-store/`: simulated demo-store scenarios.
- `matching/`: name matching utilities and related models.

## Setup

Read `Milaan_Demo_Kit/README_FIRST.md` and each component's setup instructions.
The Gradio app uses `requirements.txt` and `START_AICON_APP.bat`.
Environment variables must be configured locally; do not commit credentials or runtime data.

The original source archive included local virtual environments, private configuration,
and runtime-generated data; these were intentionally excluded from this archive.
