import csv, io, re, hashlib, json
from decimal import Decimal
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from .schemas import OrderInput

PKT = ZoneInfo("Asia/Karachi")

def paisa(value):
    s = re.sub(r"^(PKR|Rs\.?)\s*", "", str(value).strip(), flags=re.I)
    if len(s) > 32: raise ValueError("Amount out of range")
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", s):
        raise ValueError("Use a positive decimal amount with at most two decimal places")
    result = int(Decimal(s.replace(",", "")) * 100)
    if not 0 < result <= 100_000_000_000: raise ValueError("Amount out of range")
    return result

def parse_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?", value):
        raise ValueError("Use a full ISO timestamp, e.g. 2026-10-09T14:22:00+05:00")
    d = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if d.tzinfo is None: d = d.replace(tzinfo=PKT)
    try: return d.astimezone(timezone.utc).replace(tzinfo=None)
    except OverflowError: raise ValueError("Timestamp is outside the supported UTC range") from None

def norm_ref(s): return re.sub(r"\s", "", str(s or "")).upper()
def _identity_full_ref_v1(s): return bool(s) and len(str(s).strip()) >= 5 and not re.search(r"[.*…•]|xx|masked|last\s*\d", str(s), re.I)

def full_ref(s):
    # Formatting whitespace is not additional reference evidence.
    return _identity_full_ref_v1(s) and len(norm_ref(s)) >= 5


def csv_rows(raw, max_rows=2000):
    if len(raw) > 2_000_000: raise ValueError("CSV exceeds 2 MB")
    try: text = raw.decode("utf-8-sig")
    except UnicodeDecodeError: raise ValueError("CSV must be UTF-8")
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try: rows = [r for r in reader if any(x.strip() for x in r)]
    except csv.Error as exc: raise ValueError("Malformed CSV quoting or field size") from exc
    if len(rows) < 2: raise ValueError("CSV needs headers and data rows")
    if len(rows) > max_rows + 1: raise ValueError("Too many CSV rows")
    heads = [x.strip().lower() for x in rows[0]]
    if not all(heads) or len(set(heads)) != len(heads): raise ValueError("CSV headers must be unique and non-empty")
    output = []
    for i, row in enumerate(rows[1:], 2):
        if len(row) != len(heads): raise ValueError(f"CSV row {i} has the wrong number of columns")
        output.append(dict(zip(heads, (x.strip() for x in row))))
    return output

def parse_orders(raw, max_rows=2000):
    output, seen = [], set()
    for i, r in enumerate(csv_rows(raw, max_rows), 2):
        try:
            item = OrderInput.model_validate(r)
            if item.order_ref in seen: raise ValueError("Duplicate order reference")
            seen.add(item.order_ref)
            output.append({"order_ref": item.order_ref, "customer_name": item.customer_name,
                           "amount_due_paisa": paisa(item.amount_due), "account_id": item.account_id, "currency": "PKR"})
        except Exception as exc: raise ValueError(f"Orders row {i}: check column names, PKR amount and unique references") from exc
    return output

def credit_identity(owner_id, account_id, ref, posted, amount, name):
    # Strong full references are account-scoped. Weak records get a conservative fingerprint.
    parts = [owner_id, account_id, norm_ref(ref)]
    # Keep historical credit keys stable even as evidence-strength validation improves.
    if not _identity_full_ref_v1(ref): parts += [posted.isoformat(), str(amount), name.strip().upper()]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()

def parse_statement(raw, owner_id, account_id, max_rows=2000):
    output, seen = [], set()
    required = {"posted_at", "direction", "amount", "counterparty", "transaction_id"}
    for i, r in enumerate(csv_rows(raw, max_rows), 2):
        if not required.issubset(r): raise ValueError("Statement requires headers: posted_at,direction,amount,counterparty,transaction_id (account_id and currency are optional)")
        if r.get("account_id", account_id) != account_id: raise ValueError(f"Row {i}: account differs from the declared account")
        if r.get("currency", "PKR") != "PKR": raise ValueError("Only PKR is supported")
        direction = r["direction"].upper()
        if direction not in {"CREDIT", "DEBIT"}: raise ValueError(f"Row {i}: direction must be CREDIT or DEBIT")
        if len(r["transaction_id"]) > 150 or len(r["counterparty"]) > 200: raise ValueError("Statement text field too long")
        try:
            posted = parse_time(r["posted_at"])
        except ValueError as exc:
            raise ValueError(f"Statement row {i}, posted_at: {exc}") from exc
        try:
            amount = paisa(r["amount"])
        except ValueError as exc:
            raise ValueError(f"Statement row {i}, amount: {exc}") from exc
        fingerprint = (posted, direction, amount, norm_ref(r["transaction_id"]), r["counterparty"])
        if fingerprint in seen: raise ValueError(f"Row {i}: duplicate statement record")
        seen.add(fingerprint)
        output.append({"posted_at": posted, "direction": direction, "amount_paisa": amount,
                       "counterparty": r["counterparty"], "transaction_id": r["transaction_id"],
                       "account_id": account_id, "currency": "PKR",
                       "credit_key": credit_identity(owner_id, account_id, r["transaction_id"], posted, amount, r["counterparty"])})
    return output

def safe_cell(value):
    s = str(value if value is not None else "")
    return "'" + s if re.match(r"^(?:[\t\r]|\s*[=+@-])", s) else s

def csv_export(headers, rows):
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(headers)
    for row in rows: writer.writerow([safe_cell(x) for x in row])
    return out.getvalue()
