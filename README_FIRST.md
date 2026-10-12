# Milaan + separate demo store

**Start here.** These root instructions replace older setup instructions inside the inherited folders.

Milaan is the receipt / statement checker. The demo shop is a separate app, database and process. It sends orders and evidence through authenticated Milaan APIs. No payment gateway is connected and no money is charged.

## Windows: first run

1. Extract this ZIP to a **new folder**. Keep your existing project as a backup. Stop your old servers if they use port 8000 or 8090.
2. Double-click **SETUP.bat**. Internet is required to install Python packages. It tries Python 3.13 first, otherwise your `python` command. It creates a fresh `.venv`; do not copy your old one.
3. Enter your operator email and a new password of at least 10 characters. Remember these; use the same credentials in both apps. This privately configured demo operator can sign in without SMTP. Public new signups still use email verification.
4. Double-click **START_DEMO.bat**. Keep both terminal windows open. Wait for both to say `Application startup complete`.
5. Open **http://127.0.0.1:8000** for Milaan and **http://127.0.0.1:8090** for the separate demo store.
6. In Milaan click **Use your own files** to enter/sign in, then open **Saved batches**, and ensure Backend address is `http://127.0.0.1:8000`. In the store, connect with the same credentials.
7. Follow `DEMO_GUIDE_ROMAN_URDU.md`.

After the first setup, only run START_DEMO.bat. To stop, press Ctrl+C in both server windows.

**Python:** API tests were run on Python 3.12.14 on Linux. Python 3.13 is targeted by the Windows setup but has not been executed here; Windows launch scripts have also not been executed here. If package installation fails on 3.13, use Python 3.12 to create `.venv`, then rerun SETUP.bat.

## Gemini (optional receipt reading)

Edit **milaan/backend/.env** after setup:

```dotenv
EXTRACTION_PROVIDER=gemini
GEMINI_API_KEY=your_actual_key
GEMINI_MODEL=your_available_image_capable_model_id
```

Copy only the relevant Gemini settings from your old configuration; do not replace this new `.env` with an old database path. Restart Milaan, reopen its Settings, then use receipt-reading mode. No key is included. Gemini calls were not exercised here. Manual receipt checking and fixture tests work without a key.

For new-user email OTP, fill SMTP_HOST, SMTP_PORT, SMTP_SECURITY, SMTP_USER, SMTP_PASSWORD and SMTP_FROM. No SMTP delivery was tested here. The configured operator avoids this dependency during the demo.

## Linux / macOS

From this folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r milaan/backend/requirements.txt
.venv/bin/python setup_admin.py
cd milaan/backend
../../.venv/bin/python -m alembic upgrade head
../../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, from the root folder:

```sh
cd demo-store
../.venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8090
```

## Folders

- `milaan/backend`: receipt checking API, auth, jobs, database, AiCON name matching.
- `milaan/frontend`: restored cinematic Milaan receipt workspace, served by the backend.
- `demo-store`: separate shop and simulated bank evidence generator.
- `tests/live_demo_check.py`: isolated HTTP integration check using temporary databases.
- `INTEGRATION_REPORT.md`: verified scope and remaining limitations.

No Node build or third frontend server is needed. Keep `.env` private. This kit starts with new local data; it does not migrate your old business database automatically.
