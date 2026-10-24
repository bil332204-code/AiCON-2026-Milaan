> Inherited component reference. For this repository, follow [canonical local setup](../../README_FIRST.md); root instructions take precedence. Hosted features are separately maintained and unverified here.

> Version 1.2: demo navigation fixed; email verification supported. Read UPDATE_GUIDE.md for updating both folders and configuring email.

# Milaan cinematic website — connected frontend

The animated Milaan website now connects to your previously supplied FastAPI backend. No frontend build, Node installation, or additional Python packages are needed to run it.

## Bilal: ab kya karna hai

1. Extract this ZIP into a separate folder, for example `D:\milaan-cinematic`. Keep your existing backend folder, `.env`, database and uploads.
2. Keep the backend running. If it stopped, open CMD and run:

```bat
cd /d D:\milaan-backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

3. If the old plain integration demo is still using port 8080, press Ctrl+C in **that second terminal only**. Keep the backend terminal open.
4. In the new cinematic folder, double-click **START_WEBSITE.bat**. It uses your installed Python 3, including Python 3.13.
5. Open **http://localhost:8080**. If the old demo appears, stop its server and hard-refresh with Ctrl+F5 after starting this one.
6. Click **Open workspace**. Backend address: `http://127.0.0.1:8000`.
7. Sign in with the account you created in the earlier backend demo. Your saved batches will appear. Or choose **Create a new account**.
8. Click **Saved sample** to create and reconcile the 12-order server sample. Expected: 5 Ship, 2 Hold, 5 Review.

The landing page's **Explore the demo** button still offers a fictional browser-local preview without registration. **Open workspace**, **Saved batches** and **Use your own files** use the connected backend.

## Real records, from the website

1. Click **New batch**, give it a name, then upload your orders CSV. Use **Get template** for the exact columns.
2. In **Import a statement**, enter the stable receiving-account ID, actual export start/end in Pakistan time, and the relevant declarations. Then choose the CSV. Use one CSV per account; bank PDF layouts need conversion first.
3. Under **Payment receipts**, choose the order a screenshot belongs to, then upload it. Repeat for other orders. Multiple images selected together all belong to the order you explicitly chose.
4. Enter amount, full reference, date/time and sender. Confirm after inspecting the original receipt, then press **Save receipt fields**. Edits remain unsaved until this button is pressed.
5. Click **Reconcile this batch**. The website polls the server job and loads saved results.
6. Open a result to inspect the receipt and candidate credits. For a manual match, choose an available credit and provide a review reason. Decisions save on the server.
7. **Export results** downloads the backend CSV. **Activity log** shows the loaded audit events for this batch.

After a run, inputs are locked. **Import center → Reset and edit** releases current allocations and clears current results so you can correct source records. Earlier decisions remain in the audit history until batch deletion or expiry.

## Enable Gemini reading

Manual entry works immediately. For actual image extraction, edit the **backend's `.env`**:

```dotenv
EXTRACTION_PROVIDER=gemini
GEMINI_API_KEY=your-private-key
GEMINI_MODEL=your-supported-model-id
```

Restart the backend and reopen **Account & content** to refresh provider status. Use **Read pending with AI** or a receipt's **Read with AI** button. The confirmation explains that pending images will be sent to Google. A finished job can still contain failed or uncertain receipts; inspect each status and both reads. Two matching reads do not establish accuracy.

The API key belongs only on the server. This frontend never asks for it. A real call needs to be verified with your own account and chosen model.

## Accounts and content

**Account & content** saves your shop name, branding, customer-message drafts and FAQ through the backend content API. These settings are private per seller. Product name changes the signed-in workspace title; workspace welcome changes its heading; messages appear in the review drawer; saved FAQs appear in Help.

The session token stays in memory. Refreshing requires login again, while backend records remain saved. Logout revokes the current token. The browser remembers only the backend address.

Default batch expiry is **seven days**. Backend `BATCH_RETENTION_HOURS` applies to new batches. Expiry, deletion or reset releases their credit allocations. This frontend does not change retention.

## Online website versus your laptop

The hosted cinematic site can connect to a deployed **HTTPS** backend through the sign-in dialog. It does not deploy or tunnel the Python backend for you. Use this local download while your API runs on your laptop.

For a deployed backend, include the frontend's exact origin in CORS:

```dotenv
CORS_ORIGINS=https://milaan-studio.bil332204.chatgpt.site,http://localhost:8080,http://127.0.0.1:8080
```

Keep any other origins you still need. The original backend `.env.example` already includes local port-8080 origins. Restart the backend after editing `.env`. The hosted HTTPS page intentionally rejects an HTTP backend URL.

## Verification

19 Node tests passed for demo rules, timezone/reference mapping, allocation availability and connection URL validation. DOM automation against a real FastAPI/Uvicorn server covered registration, saved sample, CSV imports, authenticated receipt preview, manual confirmation, reconciliation, review persistence, content saving and logout.

No live Gemini call was made. No new cross-browser visual audit was available; the existing scene and animations were preserved. Backend tests and provider mocks remain in the separate backend ZIP.

Developer checks: `npm test` and `npm run check`. The site itself is plain HTML/CSS/ES modules in `dist/`.
