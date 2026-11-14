"""Read bank and mobile-wallet statement PDFs into rows the seller can check.

Nothing here is saved. The seller reviews (and can edit) the rows in the browser,
then imports them through the normal statement validation in parsing.parse_statement.
PDF text is untrusted data: it is only pattern-matched, never executed or followed.
"""
from __future__ import annotations

import io
import re
from datetime import datetime

MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PAGES = 60
MAX_ROWS = 2000

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE_RE = re.compile(
    r"(?P<d1>\d{1,2})[/.\-](?P<m1>\d{1,2})[/.\-](?P<y1>\d{4}|\d{2})"          # 02/11/2026, 02-11-26
    r"|(?P<y2>\d{4})-(?P<m2>\d{1,2})-(?P<d2>\d{1,2})"                          # 2026-11-02
    r"|(?P<d3>\d{1,2})[\s\-](?P<m3>" + _MON + r")[\s\-,]*(?P<y3>\d{4}|\d{2})"  # 02 Nov 2026, 02-Nov-26
    r"|(?P<m4>" + _MON + r")\s+(?P<d4>\d{1,2}),?\s+(?P<y4>\d{4})",             # Nov 2, 2026
    re.I)
TIME_RE = re.compile(r"\b(?P<h>\d{1,2}):(?P<mi>\d{2})(?::(?P<s>\d{2}))?\s*(?P<ap>[ap]\.?m\.?)?", re.I)
AMOUNT_RE = re.compile(r"(?<![\w.])(?:(?:rs\.?|pkr)\s*)?(?P<sign>[+-])?(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+\.\d{2})(?P<crdr>\s*(?:cr|dr)\b)?(?![\w])", re.I)
LABELLED_REF_RE = re.compile(
    r"(?:tid|trx\s*id|txn\s*id|transaction\s*(?:id|no\.?|#)|ref(?:erence)?\s*(?:no\.?|#|id)?|rrn|stan)\s*[:#.\-]?\s*(?P<ref>[A-Za-z0-9][A-Za-z0-9\-]{4,40})",
    re.I)
PERIOD_RE = re.compile(r"(?:statement\s+period|period|from|for\s+the\s+period)\s*:?\s*(?P<a>.{6,30}?)\s+(?:to|till|until|-|–)\s+(?P<b>.{6,30})", re.I)

CREDIT_WORDS = re.compile(r"\b(received|receive|credit(?:ed)?|deposit|incoming|inward|refund\s+from|from)\b|\bcr\b", re.I)
DEBIT_WORDS = re.compile(r"\b(sent|send|debit(?:ed)?|withdraw(?:al)?|outgoing|outward|paid\s+to|payment\s+to|transfer\s+to|bill\s+payment|to)\b|\bdr\b", re.I)
SKIP_WORDS = re.compile(r"\b(opening|closing|brought\s+forward|carried\s+forward|total|balance\s+b/?f|balance\s+c/?f)\b", re.I)
NAME_PREFIX = re.compile(
    r"^.*?\b(?:money\s+received\s+from|received\s+from|transfer(?:red)?\s+from|ibft\s+from|raast\s+(?:transfer\s+)?from|"
    r"funds?\s+transfer\s+from|from|money\s+sent\s+to|sent\s+to|transfer(?:red)?\s+to|ibft\s+to|paid\s+to|payment\s+to|to)\b\s*", re.I)


CHANNEL_WORDS = re.compile(r"^(?:(?:inward|outward|incoming|outgoing|ibft|raast|ift|ft|funds?|online|mobile|transfer|deposit|credit|1link)\b\s*)+", re.I)


class StatementPDFError(ValueError):
    """A problem the seller can fix (wrong file, password, scanned image)."""


def _year(y: str) -> int:
    y = int(y)
    return y + 2000 if y < 100 else y


def parse_date(text: str):
    """Return (date, span) for the first date in text, day-first like Pakistani statements."""
    m = DATE_RE.search(text)
    if not m:
        return None, None
    g = m.groupdict()
    try:
        if g["d1"]:
            d, mo, y = int(g["d1"]), int(g["m1"]), _year(g["y1"])
        elif g["y2"]:
            d, mo, y = int(g["d2"]), int(g["m2"]), int(g["y2"])
        elif g["d3"]:
            d, mo, y = int(g["d3"]), MONTHS[g["m3"][:3].lower()], _year(g["y3"])
        else:
            d, mo, y = int(g["d4"]), MONTHS[g["m4"][:3].lower()], int(g["y4"])
        return datetime(y, mo, d), m.span()
    except (ValueError, KeyError):
        return None, None


def parse_clock(text: str):
    m = TIME_RE.search(text)
    if not m:
        return None
    h, mi, s = int(m["h"]), int(m["mi"]), int(m["s"] or 0)
    ap = (m["ap"] or "").lower().replace(".", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h > 23 or mi > 59 or s > 59:
        return None
    return h, mi, s


def iso_pkt(day: datetime, clock) -> str:
    h, mi, s = clock or (12, 0, 0)
    return day.replace(hour=h, minute=mi, second=s).strftime("%Y-%m-%dT%H:%M:%S+05:00")


def money(num: str) -> str:
    value = num.replace(",", "")
    if "." not in value:
        value += ".00"
    whole, frac = value.split(".")
    return f"{int(whole)}.{(frac + '00')[:2]}"


def _lines(page):
    """Group words into visual lines, keeping x positions."""
    words = page.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=1.5, y_tolerance=2)
    rows = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if rows and abs(rows[-1][0] - w["top"]) <= 3:
            rows[-1][1].append(w)
        else:
            rows.append([w["top"], [w]])
    return [sorted(ws, key=lambda w: w["x0"]) for _, ws in rows]


HEADER_KEYS = {
    "debit": re.compile(r"^(debit|debits|withdrawal|withdrawals|dr|paid\s*out|money\s*out|out)$", re.I),
    "credit": re.compile(r"^(credit|credits|deposit|deposits|cr|paid\s*in|money\s*in|in)$", re.I),
    "amount": re.compile(r"^(amount|amount\(pkr\)|amount\s*\(rs\)|transaction\s*amount)$", re.I),
    "balance": re.compile(r"^(balance|running\s*balance|closing\s*balance)$", re.I),
    "ref": re.compile(r"^(reference|ref|ref\.?\s*no|reference\s*no|tid|transaction\s*id|trx\s*id|cheque\s*no|instrument)$", re.I),
}


def _header_columns(line_words):
    text = " ".join(w["text"] for w in line_words).lower()
    if "date" not in text:
        return None
    cols = {}
    i = 0
    while i < len(line_words):
        # try two-word headers first ("Reference No", "Paid In")
        for span in (2, 1):
            chunk = line_words[i:i + span]
            label = " ".join(w["text"] for w in chunk).strip(":").strip()
            for key, rx in HEADER_KEYS.items():
                if key not in cols and rx.match(label):
                    cols[key] = ((chunk[0]["x0"] + chunk[-1]["x1"]) / 2, chunk[0]["x0"], chunk[-1]["x1"])
                    i += span - 1
                    break
            else:
                continue
            break
        i += 1
    if ("debit" in cols and "credit" in cols) or "amount" in cols:
        return cols
    return None


def _nearest_column(x_center, cols):
    best, dist = None, None
    for key in ("debit", "credit", "amount", "balance"):
        if key in cols:
            d = abs(cols[key][0] - x_center)
            if dist is None or d < dist:
                best, dist = key, d
    return best


def _find_ref(text: str, amounts_text: list[str]):
    m = LABELLED_REF_RE.search(text)
    if m and any(ch.isdigit() for ch in m["ref"]):
        return m["ref"].strip("-")
    for token in re.findall(r"[A-Za-z0-9\-]{6,40}", text):
        digits = sum(ch.isdigit() for ch in token)
        if digits >= 5 and token not in amounts_text and not DATE_RE.fullmatch(token) and not re.fullmatch(r"\d{1,3}(,\d{3})+", token):
            return token.strip("-")
    return ""


def _counterparty(description: str, ref: str) -> str:
    text = description
    if ref:
        text = text.replace(ref, " ")
    text = LABELLED_REF_RE.sub(" ", text)
    text = re.sub(r"\b(tid|trx\s*id|txn\s*id|ref(?:erence)?\s*no\.?|rrn)\b\s*:?", " ", text, flags=re.I)
    named = NAME_PREFIX.sub("", text, count=1) if NAME_PREFIX.search(text) else text
    named = CHANNEL_WORDS.sub("", named.strip())
    named = re.sub(r"\s{2,}", " ", named).strip(" -:,|")
    return (named or re.sub(r"\s{2,}", " ", text).strip(" -:,|") or "Unknown")[:200]


def _row_from_line(words, cols):
    text = " ".join(w["text"] for w in words)
    if SKIP_WORDS.search(text):
        return None
    day, span = parse_date(text)
    if not day or span[0] > max(25, len(text) // 3):
        return None
    rest = text[:span[0]] + " " + text[span[1]:]
    clock = parse_clock(rest)
    if clock:
        rest = TIME_RE.sub(" ", rest, count=1)

    found = []  # (amount string, column or None, sign hint)
    for i, w in enumerate(words):
        m = AMOUNT_RE.fullmatch(w["text"].strip())
        if m:
            col = _nearest_column((w["x0"] + w["x1"]) / 2, cols) if cols else None
            hint = (m["sign"] or "") + ((m["crdr"] or "").strip().lower())
            raw = w["text"]
            nxt = words[i + 1]["text"].strip().lower() if i + 1 < len(words) else ""
            if not hint and nxt in {"cr", "dr", "cr.", "dr."}:
                hint = nxt[:2]
                raw = w["text"] + " " + words[i + 1]["text"]
            found.append((m["num"], col, hint, raw))
    if not found:  # amounts written with a space after "Rs."
        for m in AMOUNT_RE.finditer(rest):
            if DATE_RE.fullmatch(m.group(0).strip()):
                continue
            found.append((m["num"], None, (m["sign"] or "") + ((m["crdr"] or "").strip().lower()), m.group(0)))
    if not found:
        return None

    checks = []
    direction, amount = None, None
    if cols:
        by_col = {c: a for a, c, _, _ in found if c}
        if "credit" in by_col and by_col["credit"]:
            direction, amount = "CREDIT", by_col["credit"]
        elif "debit" in by_col and by_col["debit"]:
            direction, amount = "DEBIT", by_col["debit"]
        elif "amount" in by_col:
            amount = by_col["amount"]
            hint = next((h for a, c, h, _ in found if c == "amount"), "")
            if hint in {"+", "cr"}:
                direction = "CREDIT"
            elif hint in {"-", "dr"}:
                direction = "DEBIT"
    if amount is None:
        candidates = [f for f in found if f[1] != "balance"]
        if not candidates:
            return None
        amount, _, hint, _ = candidates[0]
        if hint in {"+", "cr"}:
            direction = "CREDIT"
        elif hint in {"-", "dr"}:
            direction = "DEBIT"

    description = rest
    for _, _, _, raw in sorted(found, key=lambda f: -len(f[3])):
        description = re.sub(r"(?<![\w.,])" + re.escape(raw.strip()) + r"(?![\w.,])", " ", description)
    description = re.sub(r"(?<!\w)(?:rs\.?|pkr)(?!\w)", " ", description, flags=re.I)
    description = re.sub(r"\s{2,}", " ", description).strip(" -:,|")

    if direction is None:
        credit, debit = CREDIT_WORDS.search(description), DEBIT_WORDS.search(description)
        if credit and not debit:
            direction = "CREDIT"
        elif debit and not credit:
            direction = "DEBIT"
        elif credit and debit:
            direction = "CREDIT" if credit.start() < debit.start() else "DEBIT"
        else:
            direction = "CREDIT"
            checks.append("direction")

    amounts_text = [raw for _, _, _, raw in found]
    ref = _find_ref(description, amounts_text)
    if not ref:
        checks.append("transaction_id")
    if not clock:
        checks.append("time")
    return {
        "posted_at": iso_pkt(day, clock),
        "direction": direction,
        "amount": money(amount),
        "counterparty": _counterparty(description, ref),
        "transaction_id": ref,
        "description": description[:300],
        "needs_check": checks,
    }


def _period(text: str):
    for m in PERIOD_RE.finditer(text[:3000]):
        a, _ = parse_date(m["a"])
        b, _ = parse_date(m["b"])
        if a and b and b >= a:
            return {"start": a.strftime("%Y-%m-%dT00:00:00+05:00"), "end": b.strftime("%Y-%m-%dT23:59:59+05:00")}
    return None


def _account_hint(text: str) -> str:
    m = re.search(r"(?:account|a/c|iban|wallet|mobile)\s*(?:no\.?|number|#)?\s*:?\s*(?P<acc>[A-Z]{2}\d{2}[A-Z0-9 ]{10,30}|[\d][\d\- ]{6,24}\d)", text[:3000], re.I)
    return re.sub(r"\s+", " ", m["acc"]).strip() if m else ""


def read_statement_pdf(raw: bytes) -> dict:
    if not raw.startswith(b"%PDF"):
        raise StatementPDFError("This file is not a PDF. Upload the statement PDF from your bank or wallet app.")
    if len(raw) > MAX_PDF_BYTES:
        raise StatementPDFError("This PDF is larger than 10 MB. Download a shorter date range and try again.")
    try:
        import pdfplumber
        from pdfminer.pdfdocument import PDFPasswordIncorrect
    except ImportError as exc:  # pragma: no cover - deployment problem
        raise StatementPDFError("PDF reading is not installed on this server.") from exc

    rows, warnings, texts = [], [], []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if len(pdf.pages) > MAX_PAGES:
                raise StatementPDFError(f"This PDF has more than {MAX_PAGES} pages. Download a shorter date range.")
            cols = None
            for page in pdf.pages:
                lines = _lines(page)
                texts.append("\n".join(" ".join(w["text"] for w in ws) for ws in lines))
                for ws in lines:
                    header = _header_columns(ws)
                    if header:
                        cols = header  # header repeats on each page; keep the latest
                        continue
                    row = _row_from_line(ws, cols)
                    if row:
                        rows.append(row)
                        if len(rows) > MAX_ROWS:
                            raise StatementPDFError(f"This statement has more than {MAX_ROWS} transactions. Download a shorter date range.")
                    elif rows and not parse_date(" ".join(w["text"] for w in ws))[0]:
                        # wrapped description line belonging to the previous transaction
                        extra = " ".join(w["text"] for w in ws).strip()
                        if extra and len(extra) < 120 and not AMOUNT_RE.search(extra) and not SKIP_WORDS.search(extra):
                            prev = rows[-1]
                            prev["description"] = (prev["description"] + " " + extra)[:300]
                            if not prev["transaction_id"]:
                                prev["transaction_id"] = _find_ref(extra, [])
                                if prev["transaction_id"] and "transaction_id" in prev["needs_check"]:
                                    prev["needs_check"].remove("transaction_id")
    except StatementPDFError:
        raise
    except PDFPasswordIncorrect:
        raise StatementPDFError("This PDF is password-protected. Open it, save a copy without the password, and upload that.") from None
    except Exception as exc:
        if "password" in str(exc).lower() or "encrypt" in str(exc).lower():
            raise StatementPDFError("This PDF is password-protected. Open it, save a copy without the password, and upload that.") from None
        raise StatementPDFError("This PDF could not be read. Try downloading it again from your bank or wallet app.") from None

    full_text = "\n".join(texts)
    if not full_text.strip():
        raise StatementPDFError("This PDF is a scanned image with no text. Download the original statement PDF from your bank or wallet app instead of a scan or photo.")
    if not rows:
        raise StatementPDFError("No transactions were found in this PDF. Check that it is a statement with dates and amounts, or upload a CSV instead.")

    period = _period(full_text)
    if not period:
        warnings.append("The statement period was not printed in the PDF. Enter the first and last day it covers.")
    if any(r["needs_check"] for r in rows):
        warnings.append("Some rows need a quick check (highlighted). Fix them before importing.")
    return {"rows": rows, "period": period, "account_hint": _account_hint(full_text),
            "credits": sum(r["direction"] == "CREDIT" for r in rows), "warnings": warnings}
