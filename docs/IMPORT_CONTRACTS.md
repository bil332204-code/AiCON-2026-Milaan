# Local import and matching contracts

No import queries a bank or proves settlement. Normalize source exports explicitly;
never invent a missing reference, amount, timestamp or coverage period.

Both modes use UTF-8 CSV (optional BOM), quoted fields including escaped quotes,
unique nonempty case-insensitive header names, at most 2,000 records and 2,000,000
bytes. Amounts are positive PKR decimals with at most two fractional digits;
valid thousands separators and PKR/Rs prefixes are accepted. Currency defaults to
PKR. Dates require `YYYY-MM-DDTHH:MM[:SS][Z|±HH:MM]`; missing offsets mean
Asia/Karachi, never the browser's local timezone. Date-only and impossible dates fail.

## Orders

Required: `order_ref,customer_name,amount_due,account_id`.
Optional: `currency` (PKR). References must be unique within the import.
The API uses strict schema validation and rejects unknown columns; the browser
ignores additional columns. Normalize headers before moving files between modes.

## Receiving statements

| Field | Saved FastAPI mode | Browser-local mode |
|---|---|---|
| posted_at, direction, amount | Required and nonempty | Required and nonempty |
| account_id | Declared in multipart request; CSV may omit it; if supplied must match | Required per record; may contain several accounts |
| transaction_id | Header required; blank is retained as weak evidence | Required nonempty |
| counterparty | Header required; may be blank | Optional; display fallback is not evidence |
| currency | Omitted defaults to PKR; explicit value must be PKR | Omitted defaults to PKR; case normalized |
| duplicate record | Same time, direction, amount, normalized reference and counterparty rejected | Same account, direction, amount, time and normalized reference rejected, irrespective of name |

Directions are CREDIT or DEBIT, case-insensitive. Debits never allocate payment.
The saved API accepts one statement per declared account; conflicting CSV accounts
are rejected. Browser coverage is shared across all supplied accounts. Both require
an explicit complete coverage declaration, and verified sender/receiver reference
correspondence for automatic SHIP. Coverage must come from the export, not be
inferred from the first/last record.

### Statement PDFs

`POST /api/statements/read-pdf` reads a text-based bank or wallet statement PDF
(up to 10 MB / 60 pages / 2,000 rows) and returns proposed rows; nothing is stored.
Debit/credit come from the statement's Debit/Credit (or Amount with Cr/Dr or +/-)
columns when a header is found, otherwise from wording such as "received from" or
"sent to". Rows without a time, Transaction ID or clear direction are flagged in
`needs_check`. The printed statement period is pre-filled when found; otherwise the
seller enters it. The seller edits/removes rows and confirms coverage before the
browser imports them through the same CSV validation above. Scanned or
password-protected PDFs are rejected with an explanation.

## Critical matching contract

Automatic SHIP requires confirmed receipt fields, a recognized successful status,
matching account and order amount, complete coverage, verified reference
correspondence, and exactly one uncontested credit with matching full reference,
amount and a timestamp within 24 hours. Accepted statuses (trimmed, case-insensitive):
`success`, `successful`, `completed`, `paid`, `payment successful`, `transaction successful`.
Blank, pending, failed, unknown and compound ambiguous status text yield
REVIEW / STATUS_CONFLICT. Unconfirmed fields yield review before status evaluation.
Duplicate proofs and ambiguous credits require review. Amount/time and Pakistani
name similarity suggest candidates; they never independently authorize SHIP.

Browser results are local to the current batch and cannot enforce retained
cross-batch uniqueness. Saved-backend decisions are authoritative for saved batches:
account-scoped credit keys and database uniqueness prevent retained credit reuse.
Human decisions are explicit overrides with reasons and selected eligible credit;
they preserve the machine verdict and do not execute shipping or payments.

## V2 reviewed mapping

The Import center now previews and maps source columns before submitting normalized
CSV. See Milestone A for timezone selection, row rejection,
warning behavior and private fingerprint/mapping provenance. Direct API clients may
continue to submit canonical CSV unchanged. The API accepts optional `provenance`
JSON; it does not trust this client-declared metadata as bank verification. Import
rows remain subject to the canonical server contract above.
