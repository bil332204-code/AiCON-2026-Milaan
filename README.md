# Milaan — Payment Reconciliation & Evidence Review

**AiCON 2026 | Build With AI**

Milaan is a payment reconciliation project for comparing store orders, payment evidence, and bank-statement records. It supports rule-based matching, discrepancy review, and exportable reconciliation results. This repository also includes a **simulated demo store** and a **separate Gradio application** for document processing and reconciliation.

> **Demo scope:** Store purchases and bank entries in the demo store are simulated. A receipt image alone is not proof of a successful bank transfer. This project should not be represented as a live bank or payment-gateway integration.

## What the code includes

| Component | Purpose |
| --- | --- |
| Milaan backend | FastAPI service for orders, receipts, statements, reconciliation jobs, reviews, and exports |
| Milaan frontend | Seller workspace interface bundled with the demo kit |
| Demo store | Simulated orders and payment scenarios connected to Milaan APIs |
| Standalone Gradio app | Separate PDF/receipt processing and reconciliation interface |
| Matching utilities | Pakistani-name normalization and similarity features, plus ML-related research/training files |

These are distinct components. Do not assume that every utility or model artifact is used by the live Milaan matching path.

## Five demo payment scenarios

| Scenario | What it tests | Fixture-oriented decision |
| --- | --- | --- |
| Correct payment | Matching order and bank credit | `SHIP / EXACT_MATCH` |
| Missing payment | Receipt claim without corresponding bank credit | `HOLD / NOT_FOUND` |
| Wrong amount | Mismatch between claimed and recorded amounts | `REVIEW / AMOUNT_CONFLICT` |
| Reused proof | The same payment proof associated with multiple orders | `REVIEW / REUSED_PROOF` |
| Name variation | Different spellings/abbreviations in customer and bank names | `REVIEW / POSSIBLE_MATCH` |

These are **coded demo scenarios and expected fixture outcomes**, not a claim that every case has been independently verified in a live deployment.

## How reconciliation works

```text
Demo store / seller workspace
           |
           v
Orders + payment evidence + bank statement records
           |
           v
      Milaan API
           |
           v
 Normalization & rule-based matching
           |
           v
  SHIP / HOLD / REVIEW decision
           |
           v
Review workspace + saved results + CSV export
```

Milaan's active reconciliation logic is rule-based, with name-similarity assistance. The repository contains machine-learning code and model artifacts, but their presence does **not** establish that a trained ML model performs the live reconciliation decisions.

## Repository map

```text
AiCON/
├── aicon_unified_app.py          # Standalone Gradio application
├── module2_fast_parser.py        # Statement parsing utility
├── matching/                     # Name matching and ML-related code
├── models/                       # Saved model artifacts
├── requirements.txt              # Gradio-side dependencies
├── START_AICON_APP.bat           # Windows Gradio launcher
└── Milaan_Demo_Kit/
    ├── README_FIRST.md           # Demo kit setup entry point
    ├── demo-store/               # Simulated checkout and scenarios
    └── milaan/
        ├── backend/              # FastAPI and reconciliation logic
        └── frontend/             # Frontend distribution
```

## Getting started

**Prerequisites:** Python and the dependencies documented by each component. Some optional features require external API credentials.

1. Clone this repository:
   ```bash
   git clone https://github.com/bil332204-code/AiCON-2026-Milaan.git
   cd AiCON-2026-Milaan
   ```
2. Open **`AiCON/Milaan_Demo_Kit/README_FIRST.md`** for the demo kit's component-specific setup and run instructions. If the repository contents are placed at the root instead of under `AiCON/`, adjust the path accordingly.
3. For the separate Gradio application, install the dependencies listed in `AiCON/requirements.txt` and consult `AiCON/START_AICON_APP.bat`.
4. Create local environment configuration from the relevant example files, where provided. Supply your own API credentials only for optional integrations that require them.
5. Start the required backend and interface according to the component-specific documentation.

**Security:** Never commit `.env` files, real credentials, private receipts, or local customer/payment databases. If a credential was included in a previously shared archive, rotate it before publishing.

## Technical highlights

- Order, receipt, and statement record handling
- Reconciliation verdicts with explainable reason codes
- Amount, duplicate-proof, and candidate-match review paths
- Pakistani-name similarity support
- Manual review and export workflows
- Optional AI-assisted receipt extraction requiring appropriate configuration and consent
- Separate PDF-processing and Gradio demonstration code

## Limitations

- Demo-store transactions and bank statements are simulated.
- Automatic recommendations are not evidence of settlement with a real financial institution.
- Optional AI integrations depend on configured services and should not be assumed to work offline.
- The standalone Gradio interface is not automatically part of the Milaan frontend.
- Saved ML artifacts are not evidence of active model inference or measured model accuracy.
- This README describes source-code capabilities; it is not a certification of production readiness.

---

**Built for AiCON 2026 — Build With AI.**

*Engineering focus: transparent payment-evidence reconciliation, traceable decisions, and human review of ambiguous cases.*
