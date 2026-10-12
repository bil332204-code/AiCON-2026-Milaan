# Milaan — receipt checking with a separate connected demo store

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
