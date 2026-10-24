> Inherited component reference. For this repository, follow [canonical local setup](../../README_FIRST.md); root instructions take precedence. Hosted features are separately maintained and unverified here.

# Milaan update: demo navigation and email verification

## Update your two existing folders (Windows)
1. Stop BOTH old CMD windows with Ctrl+C.
2. Copy your existing milaan-backend folder somewhere safe as a backup (especially .env and data).
3. Extract the new backend ZIP into a temporary location. Copy its contents INTO your existing milaan-backend folder. Choose Replace for matching code files. Do not delete the old folder. This ZIP contains no .env, .venv or data; your Gemini key, Python environment and records remain in place.
4. Extract the new cinematic ZIP. Copy its contents INTO your existing milaan-cinematic folder, replacing matching files.
5. Add the settings below to the EXISTING backend .env. Keep the Gemini and database settings already there. If a setting already exists, edit it rather than adding duplicates.

```env
REQUIRE_EMAIL_VERIFICATION=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=youraddress@gmail.com
SMTP_FROM=youraddress@gmail.com
SMTP_PASSWORD=your_google_app_password
```

For Gmail: enable Google 2-Step Verification, then create an App Password at https://myaccount.google.com/apppasswords (if your account supports it). Put that App Password in SMTP_PASSWORD, not your normal Google password. Use your full Gmail address for SMTP_USER and SMTP_FROM. Keep credentials in .env only; do not paste them into chat or the frontend. For another email provider, use its SMTP host, port, sender and credentials.
Google settings reference: https://support.google.com/mail/answer/7104828

6. Double-click UPDATE_AND_START.bat inside the existing backend folder. This runs the new migration and starts port 8000. No new Python packages are needed for this update.
7. Double-click START_WEBSITE.bat inside milaan-cinematic. Open http://localhost:8080 and press Ctrl+F5 once.

## Use the website
- See Milaan in action: instant fictional demo, no account or email needed.
- Open workspace -> Create a new account: use a real email address, your name and a password of at least 10 characters. Send code -> check your inbox/spam -> enter the six digits -> Verify email & continue.
- A code expires in 10 minutes, has 5 guesses, and works once. Resend after 60 seconds (maximum 5 emails per hour per pending email). Only a successfully verified signup creates an account. Codes and passwords are stored as salted hashes; codes are never returned by the API.
- Existing accounts keep their existing login and records. This update enforces email verification for NEW signups; it does not claim historical accounts were verified.
- Without working SMTP settings, existing login and the offline demo still work; new signup shows a delivery error and creates no account.

## Add your real records
1. Sign in -> New batch -> enter a name.
2. Import center -> Orders -> Get template. Fill that CSV and upload it. Keep its headers.
3. Download the statement template. Fill it from your receiving account export. Select that same account ID and the actual statement start/end period before uploading the statement CSV. Declare completeness/reference correspondence only when verified.
4. Select the order a receipt belongs to, then upload its image. Repeat for other orders.
5. Read pending with AI -> consent to cloud reading. Inspect extracted fields and correct uncertain values. Save receipt fields for each edited receipt.
6. Reconcile this batch -> inspect Ship/Hold/Review -> open an order for evidence -> Export results.
7. Account & content edits the shop name, branding text, customer message drafts and FAQs.

## Verification performed
34 backend tests and 19 frontend tests passed. DOM automation against a real local backend covered the demo hash navigation, signup/verification, saved samples, CSV and image uploads, receipt edits, reconciliation, review, content and logout. Email delivery was replaced with a test mail sink for automated testing. Actual Gmail/SMTP delivery needs your credentials and has not been tested here. No new graphical browser audit was available. Gemini delivery was not tested with a live key.

## Manual migration command (alternative to UPDATE_AND_START.bat)
Run in the existing backend folder:
```bat
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
