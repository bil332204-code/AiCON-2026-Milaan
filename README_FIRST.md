# Milaan + separate demo store

**Canonical local setup entry point.** These root instructions replace older setup instructions inside the inherited folders.

Milaan is the receipt / statement checker. The demo shop is a separate app, database and process. It sends orders and evidence through authenticated Milaan APIs. No payment gateway is connected and no money is charged.

## Windows: first run

1. Extract this ZIP to a **new folder**. Keep your existing project as a backup. Stop your old servers if they use port 8000 or 8090.
2. Double-click **SETUP.bat**. Internet is required to install Python packages. It tries Python 3.12 first, otherwise your `python` command. It creates a fresh `.venv`; do not copy your old one.
3. Enter your operator email and a new password of at least 10 characters. Remember these; use the same credentials in both apps. This privately configured demo operator can sign in without SMTP. Public new signups still use email verification.
4. Double-click **START_DEMO.bat**. Keep both terminal windows open. Wait for both to say `Application startup complete`.
5. Open **http://127.0.0.1:8000** for Milaan and **http://127.0.0.1:8090** for the separate demo store.
6. In Milaan click **Use your own files** to enter/sign in, then open **Saved batches**, and ensure Backend address is `http://127.0.0.1:8000`. In the store, connect with the same credentials.
7. Follow `DEMO_GUIDE_ROMAN_URDU.md`.

After the first setup, only run START_DEMO.bat. To stop, press Ctrl+C in both server windows.

**Python:** API tests were run on Python 3.12.14 on Linux. Python 3.13 is targeted by the Windows setup but has not been executed here; Windows launch scripts have also not been executed here. Prefer Python 3.12 to create `.venv`, then rerun SETUP.bat.

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
.venv/bin/python -m pip install -c milaan/backend/constraints-py312.txt -r milaan/backend/requirements.txt
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

## Troubleshooting and verification scope

Run all root commands from the cloned repository, not the inherited backend folder.
Python 3.12 virtual environment creation, pinned installation, SQLite migrations,
both application launches and synthetic HTTP workflows were executed on Linux.
The interactive operator prompt, Windows batch files and Python 3.13 were not
executed in this release pass. Automated operator startup and login use isolated
synthetic test credentials, never a shared account for ongoing use.

If a command reports a missing module, use the root `.venv/bin/python` explicitly
and reinstall `milaan/backend/requirements.txt`; do not mix system and venv Python.
If a port is occupied, inspect the existing process and stop your earlier instance
with Ctrl+C, or use another port. Never kill an unknown process. When changing the
backend port, set `MILAAN_URL` for the demo-store process and the frontend Backend
address to the same URL. Uvicorn fails with a bind error for occupied ports.

For isolated loopback development without an operator or SMTP, launch Milaan with
`REQUIRE_EMAIL_VERIFICATION=false` before the uvicorn command and register your own
account. This is an explicit development-only override; keep verification enabled
for public deployments. Do not invent or commit credentials. Services must restart
after a cloud snapshot restores; installed dependencies and data persist separately.

Before migrating existing data, back up the database and uploads together. See
[privacy](docs/PRIVACY.md), [import contracts](docs/IMPORT_CONTRACTS.md) and
[release validation](docs/RELEASE_REPORT.md). Nested guides are historical/reference
material where they differ from this guide.


## V3 browser authentication

The integrated UI now uses HttpOnly browser sessions, with password visibility,
verified signup, recovery and finite remember-me. Existing local passwords and data
remain usable. If your older account has no recorded email verification, confirm its
email in Account & content before password recovery can be enabled. SMTP must be
configured for verification and reset delivery; no shared default credentials exist.
Keep development HTTP bound to loopback. Use the root Dockerfile and
[V3 deployment guide](docs/V3_DEPLOYMENT.md) for the new same-origin production path.
The separately hosted Sites website is not updated by these repository changes.
