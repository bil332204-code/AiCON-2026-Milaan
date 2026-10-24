# Repeatable 5–7 minute synthetic demo

1. (1 minute) Start both services using README_FIRST. Sign in with your own
   configured operator, connect the store with the same credentials, and explain
   that all shop payments and bank records are simulated.
2. (2 minutes) In the store choose **Quick fixture test** for each scenario:
   matched → SHIP / EXACT_MATCH; missing → HOLD / NOT_FOUND; wrong_amount →
   REVIEW / AMOUNT_CONFLICT; duplicate → REVIEW / REUSED_PROOF for both claims;
   name → REVIEW / POSSIBLE_MATCH. Wait for live results after each sync.
3. (1 minute) Open the saved batch in Milaan and inspect receipt, statement
   candidates and reason codes. Explain that name similarity suggests a candidate,
   never an automatic payment approval. Fixture fields are supplied, not AI reads.
4. (1–2 minutes) Choose **Test receipt reading** on a new order. With no Gemini
   configured, inspect the synthetic image and manually enter its amount, full
   reference, timestamp, sender and successful status. Confirm and save fields,
   reconcile, then inspect the result. With configured Gemini, cloud consent is
   required and extracted fields still require review; no live AI claim is made here.
5. (1 minute) Record a human decision with a reason and an eligible unallocated
   credit, then export CSV. Explain seven-day default retention and export before
   expiry. Evidence does not prove settlement or send a payment/shipping action.

Automated equivalent: `.venv/bin/python tests/live_demo_check.py` uses temporary
databases and temporary ports, checks all five scenarios plus manual confirmation,
and terminates only its own processes. It does not test browser clicks or live AI.
