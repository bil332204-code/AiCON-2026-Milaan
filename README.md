# Milaan — live receipt reconciliation workspace

**[Open Milaan](https://milaan-studio.bil332204.chatgpt.site)** · **[Open workspace](https://milaan-studio.bil332204.chatgpt.site/workspace)** · **[Portfolio](https://bilal-ahmed-builds.cyou/projects/milaan)**

The live cinematic website includes a private workspace with hosted ChatGPT sign-in, persistent batches, receipt image uploads, order and bank CSV imports, explainable SHIP / HOLD / REVIEW recommendations, and CSV exports.

### Try the live app

1. Open the workspace and continue with ChatGPT.
2. Create a batch and download the CSV templates.
3. Upload orders and bank transactions; declare statement coverage accurately.
4. Attach a receipt to its order and confirm the visible amount, reference, timestamp, and payment status.
5. Compare evidence and inspect each recommendation.

Manual receipt confirmation works without an AI key. Optional Gemini extraction requires your own key and explicit consent; extracted fields still need review. The bank input is an uploaded CSV, not a direct bank connection. Results depend on the evidence supplied and do not independently prove that a bank transfer settled.

The hosted application passed 19 matching/API tests, TypeScript checking, and a production build. Production deployment succeeded; full browser interaction and live Gemini calls have not been verified. The hosted application is maintained in its Sites Git source; this GitHub branch contains the separate local demo kit below.

---

## Local demo kit — receipt checking with a separate connected demo store

Post-hackathon corrected demo kit, 12 October 2026.

Milaan compares order totals, receipt evidence and receiving-bank records, returning explainable **SHIP / HOLD / REVIEW** recommendations. AiCON Pakistani-name matching is integrated into the checker. The separate demo shop sends orders and simulated evidence to Milaan through authenticated APIs.

## Run it

1. Windows: run `SETUP.bat` and configure your own operator login.
2. Run `START_DEMO.bat`.
3. Open Milaan at http://127.0.0.1:8000 and the store at http://127.0.0.1:8090.
4. Sign in with the same operator in both. Place an order in the store and choose Quick fixture test or Test receipt reading.

See [setup](README_FIRST.md), [5–7 minute live demo guide](DEMO_GUIDE_ROMAN_URDU.md), and [verification and limitations](INTEGRATION_REPORT.md).

## What is real in this demo?

The two running applications, authentication, uploads, database records, background reconciliation, manual receipt confirmation and live result polling are real. Payments and bank records are explicitly simulated. Fixture mode supplies known receipt fields; receipt mode requires AI or manual reading. Gemini calls require your own configuration and have not been verified here.

## Validation

43 backend tests, 25 AiCON matching tests, 19 frontend tests and 5 interrupted-sync tests passed. Live HTTP tests cover all five store scenarios plus the manual receipt-confirmation flow. Windows launch scripts and live Gemini/SMTP calls remain unverified.

```sh
cd milaan/backend
python -m pytest tests matching/tests
cd ../..
python -m pytest tests/test_store_sync.py
python tests/live_demo_check.py
node --test milaan/frontend/tests/*.test.mjs
```

This branch contains the user-supplied Milaan demo kit as the root project. The separate Gradio prototype from the previous repository root is not part of this application. `main` retains the earlier submission history.
