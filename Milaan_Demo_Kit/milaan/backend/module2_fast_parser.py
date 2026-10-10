#!/usr/bin/env python3
"""
Bank-agnostic statement parser.

Usage:
    python module2_fast_parser.py statement.pdf [BANK] [PASSWORD]
    python module2_fast_parser.py statement.pdf BANK [PASSWORD] --dump     (prints sample text of page 2)

How it avoids debit/credit confusion
------------------------------------
Column order is never used. Each row gives us its numbers + the running balance.
We compare the balance with the previous row's balance:
    balance went up   by the amount -> credit
    balance went down by the amount -> debit
This works for any bank and any column order, with or without "0" fillers,
whole numbers or decimals, ascending or descending statements.

Easypaisa statements (Opening | Incoming | Outgoing | Closing, date on its own line) have a
different layout, so they are detected automatically and read by x-position instead.
The same rule applies there: direction = closing - opening.

Speed: regex/text extraction only. The LLM (Ollama) is used only for date-lines
the code could not read, and it never decides debit/credit.
Requires: pip install "pdfplumber>=0.10" requests python-dotenv
"""
import os, re, sys, csv, time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import pdfplumber
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
WORKERS = int(os.getenv("PARSER_WORKERS", "4"))

DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y", "%d-%b-%y",
                "%d/%m/%y", "%d %b %y", "%Y-%m-%d", "%d-%B-%Y", "%d %B %Y"]
DATE_RE = (r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
           r"|\d{1,2}[\- ][A-Za-z]{3,9}[\- ,]+\d{2,4}"
           r"|\d{4}-\d{2}-\d{2})")
LINE_RE = re.compile(rf"^\s*{DATE_RE}(?:\s+{DATE_RE})?(?:\s+(.*))?$")   # date [value-date] rest
NUM_FULL = re.compile(r"\(?-?\d[\d,]*(?:\.\d{1,2})?\)?(?:CR|DR|Cr|Dr)?")
AMT = r"(\(?-?[\d,]+\.\d{2}\)?(?:CR|DR|Cr|Dr)?)"
OPENING_RE = re.compile(r"opening\s*balance\s*:?\s*(?:PKR|Rs\.?)?\s*" + AMT, re.I)
CLOSING_RES = [re.compile(r"closing\s*balance\s*:?\s*(?:PKR|Rs\.?)?\s*" + AMT, re.I),
               re.compile(r"\bbalance\s*:\s*(?:PKR|Rs\.?)\s*" + AMT, re.I)]
OPEN_ROW_RE = re.compile(r"opening\s*balance|brought\s*forward|\bb/f\b", re.I)
CLOSE_ROW_RE = re.compile(r"closing\s*balance|carried\s*forward|\bc/f\b", re.I)
FOOTER_RE = re.compile(r"page\s*\d+\s*(of|/)|www\.|kindly visit|schedule of charges|system generated|"
                       r"computer generated|signature|statement of account|transaction performed|^note\s*:", re.I)
CREDIT_WORDS = re.compile(r"\b(salary|deposit|credit|received|refund|profit|incoming|ibft in|raast in|from)\b", re.I)


def to_num(tok):
    """'1,234.50' -> 1234.5 ; '(500.00)', '-500', '500.00Dr' -> negative."""
    t = tok.strip()
    neg = t.startswith("(") or t.startswith("-") or bool(re.search(r"dr$", t, re.I))
    num = float(re.sub(r"[^\d.]", "", re.sub(r"(?i)(cr|dr)$", "", t)))
    return -num if neg else num


def parse_date(s):
    s = re.sub(r"[,\s]+", " ", s.strip())
    for f in DATE_FORMATS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def parse_tail(text):
    """Trailing numbers of a line: up to 2 amount-columns + balance.
    Returns (head_text, [(value, token), ...], balance) or None."""
    text = re.sub(r"(\d)\s+(CR|DR|Cr|Dr)\b", r"\1\2", text)
    toks = text.split()
    nums = []
    while toks and len(nums) < 3 and NUM_FULL.fullmatch(toks[-1]):
        nums.append(toks.pop())
    nums.reverse()
    if len(nums) < 2 or "." not in nums[-1]:      # balance always has decimals
        return None
    cands = [(abs(to_num(t)), t) for t in nums[:-1]]
    return " ".join(toks), cands, to_num(nums[-1])


def apply_tail(row, text, first):
    t = parse_tail(text)
    if not t:
        return False
    head, cands, bal = t
    row["head"] = head if first else (row["head"] + " " + head).strip()
    row["cands"], row["balance"] = cands, bal
    return True


def extract_rows(pdf, xtol, pages=None):
    rows, texts = [], []
    for pno, page in enumerate(pdf.pages, 1):
        if pages is not None and pno not in pages:
            continue
        cur, prev_bottom = None, None
        for ln in page.extract_text_lines(x_tolerance=xtol, strip=True, return_chars=False):
            text = ln["text"].strip()
            if not text:
                continue
            texts.append(text)
            h = max(ln["bottom"] - ln["top"], 1.0)
            near = prev_bottom is not None and (ln["top"] - prev_bottom) < 1.3 * h   # wrapped line of same row
            prev_bottom = ln["bottom"]
            m = LINE_RE.match(text)
            d = parse_date(m.group(1)) if m else None
            if d:
                rest = m.group(3) or ""
                if near and cur is not None and parse_tail(rest) is None:
                    d = None                      # a bare date inside a wrapped description
                else:
                    cur = dict(date=d, head=rest, cands=[], balance=None, page=pno, raw=text)
                    rows.append(cur)
                    apply_tail(cur, rest, True)
                    continue
            if cur is not None and near and not FOOTER_RE.search(text):
                cur["raw"] += " " + text
                if cur["balance"] is not None or not apply_tail(cur, text, False):
                    cur["head"] = (cur["head"] + " " + text).strip()
            else:
                cur = None
    return rows, texts


def split_markers(rows):
    """Remove opening/closing-balance rows; return (rows, opening_balance_from_rows)."""
    opening, clean = None, []
    for r in rows:
        if r["balance"] is not None and OPEN_ROW_RE.search(r["head"]):
            opening = r["balance"] if opening is None else opening
            continue
        if r["balance"] is not None and CLOSE_ROW_RE.search(r["head"]):
            continue
        clean.append(r)
    return clean, opening


def score(seq):
    n = 0
    for a, b in zip(seq, seq[1:]):
        d = abs(b["balance"] - a["balance"])
        if any(abs(v - d) < 0.02 for v, _ in b["cands"]):
            n += 1
    return n


def resolve(rows, opening):
    good = [r for r in rows if r["balance"] is not None]
    seq = good if score(good) >= score(good[::-1]) else good[::-1]   # newest-first statements
    prev = opening
    for r in seq:
        r["debit"] = r["credit"] = 0.0
        amt = idx = credit = None
        if prev is None:
            status = "first_row_unverified"
        else:
            delta = round(r["balance"] - prev, 2)
            for i, (v, _) in enumerate(r["cands"]):
                if abs(v - abs(delta)) < 0.02:
                    amt, idx, credit = v, i, delta >= 0
                    break
            status = "ok" if amt is not None else "balance_mismatch"
        if amt is None:
            nz = [(i, v) for i, (v, _) in enumerate(r["cands"]) if v > 0]
            if len(nz) == 1:
                idx, amt = nz[0]
                credit = bool(CREDIT_WORDS.search(r["head"]))
            elif not nz:
                amt, credit = 0.0, False
            else:
                status = "ambiguous"
        if amt is None:
            r["debit"] = r["credit"] = ""
        else:
            r["credit" if credit else "debit"] = amt
        extra = [t for i, (v, t) in enumerate(r["cands"]) if i != idx and v > 0]
        r["desc"] = re.sub(r"\s+", " ", (r["head"] + " " + " ".join(extra)).strip())
        r["status"] = status
        prev = r["balance"]
    unparsed = [r for r in rows if r["balance"] is None]
    for r in unparsed:
        r.update(desc=r["head"], debit="", credit="", status="unparsed")
    return seq + unparsed


def choose_xtol(pdf):
    """Some PDFs squeeze spaces out of words. Pick the tolerance that keeps numbers intact
    and keeps the most spaces in descriptions (tested on the first pages only)."""
    sample = range(1, min(4, len(pdf.pages)) + 1)
    best, best_score = 3, (-1, -1)
    for xt in (1.5, 3):
        rows, _ = extract_rows(pdf, xt, pages=set(sample))
        rows, op = split_markers(rows)
        out = resolve(rows, op)
        sc = (sum(r["status"] == "ok" for r in out), sum(r["desc"].count(" ") for r in out))
        if sc > best_score:
            best, best_score = xt, sc
    return best


# --------------------------------------------------------------------------- Easypaisa
# Layout:  Date | Transaction Detail | Opening Balance | Incoming | Outgoing | Closing Balance
#   "Oct 9, 2026 Bank Transfer - NAME - 3,957.36 - (200.00) 3,757.36"
#   "01:42 PM PK20MEZN************0710"
#   "Transaction ID | Amount | Tax | Fees | Discount | Total"
#   "57091796885 200.00 0.00 0.00 0.00 200.00"
# The date/time can sit on a different y than the description, and the brackets are NOT reliable
# (an incoming amount can be printed as "(2,700.00)"), so direction = closing - opening.
EP_AMT = re.compile(r"^\(?[\d,]+\.\d{2}\)?$")


def group_lines(words, tol=2.5):
    ws = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines = []
    for w in ws:
        if lines and abs(w["top"] - lines[-1]["top"]) <= tol:
            lines[-1]["words"].append(w)
        else:
            lines.append({"top": w["top"], "words": [w]})
    for ln in lines:
        ln["words"].sort(key=lambda w: w["x0"])
    return lines


def is_easypaisa(pdf):
    for pg in pdf.pages[:2]:
        t = pg.extract_text(x_tolerance=1.5) or ""
        if re.search(r"easypaisa", t, re.I) and "Opening" in t and "Closing" in t:
            return True
    return False


def ep_page_rows(words, pno):
    lines = group_lines(words)

    # header row gives the column positions (defaults = what the sample statement uses)
    header_top, xo, xi, xg, xc = -1, 280, 361, 427, 501
    for ln in lines:
        t = {w["text"]: w["x0"] for w in ln["words"]}
        if "Opening" in t and "Closing" in t:
            header_top = ln["top"]
            xo, xi, xg, xc = t["Opening"], t.get("Incoming", xi), t.get("Outgoing", xg), t["Closing"]
            break
    op_lo, op_hi, in_hi, out_hi = xo + 10, xi - 10, xg - 10, xc - 15

    # 1) anchor = a line with an opening balance AND a closing balance
    anchors = []
    for ln in lines:
        if ln["top"] <= header_top:
            continue
        ws = ln["words"]
        op = [w for w in ws if op_lo <= w["x0"] < op_hi and EP_AMT.match(w["text"])]
        cl = [w for w in ws if w["x0"] >= out_hi and EP_AMT.match(w["text"])]
        if op and cl:
            inc = [w["text"] for w in ws if op_hi <= w["x0"] < in_hi and w["text"] != "-"]
            outg = [w["text"] for w in ws if in_hi <= w["x0"] < out_hi and w["text"] != "-"]
            anchors.append({"top": ln["top"], "opening": to_num(op[0]["text"]),
                            "closing": to_num(cl[0]["text"]),
                            "col_amt": abs(to_num((inc or outg or ["0"])[0])), "desc": []})

    # 2) dates / times from the left column
    left = []
    for ln in lines:
        if ln["top"] > header_top:
            lw = [w["text"] for w in ln["words"] if w["x0"] < 80]
            if lw:
                left.append(" ".join(lw))
    left_text = " ".join(left)
    dates = re.findall(r"([A-Z][a-z]{2} \d{1,2}, \d{4})", left_text)
    times = re.findall(r"(\d{1,2}:\d{2} [AP]M)", left_text)

    # 3) description + transaction id: lines from this anchor down to the next anchor
    ids = []
    for i, a in enumerate(anchors):
        top0 = a["top"] - 0.5
        top1 = anchors[i + 1]["top"] - 0.5 if i + 1 < len(anchors) else 1e9
        for ln in lines:
            if not (top0 <= ln["top"] < top1):
                continue
            ws = ln["words"]
            f = ws[0]
            if f["text"] == "Transaction" and f["x0"] < 100:
                continue                                  # "Transaction ID | Amount | Tax ..."
            if re.match(r"^\d{8,}$", f["text"]) and f["x0"] < 100 and len(ws) >= 4:
                ids.append(f["text"])
                continue
            if f["text"] == "This":
                continue                                  # page footer
            a["desc"] += [w["text"] for w in ws if 80 <= w["x0"] < 290]
        while a["desc"] and a["desc"][-1] == "-":
            a["desc"].pop()

    counts_ok = len(anchors) == len(dates) == len(times) == len(ids)
    res = []
    for k, a in enumerate(anchors):
        ds = dates[k] if k < len(dates) else ""
        ts = times[k] if k < len(times) else ""
        try:
            d = datetime.strptime(ds, "%b %d, %Y").date()
        except ValueError:
            d = None
        res.append({"a": a, "date": d, "time": ts, "id": ids[k] if k < len(ids) else "",
                    "page": pno, "counts_ok": counts_ok})
    return res


def parse_easypaisa(pdf):
    rows = []                                             # newest first, as printed
    for pno, page in enumerate(pdf.pages, 1):
        words = page.extract_words(x_tolerance=1.5, y_tolerance=3)
        rows += ep_page_rows(words, pno)
    out = []
    for i, r in enumerate(rows):
        a = r["a"]
        delta = round(a["closing"] - a["opening"], 2)
        status = "ok"
        if abs(abs(delta) - a["col_amt"]) > 0.01:
            status = "balance_mismatch"
        if not r["counts_ok"] or r["date"] is None:
            status = "check_dates"
        if i + 1 < len(rows) and abs(a["opening"] - rows[i + 1]["a"]["closing"]) > 0.01:
            status = "chain_break"                        # older row should close where this one opens
        out.append({"date": r["date"] or "", "desc": " ".join(a["desc"]),
                    "debit": -delta if delta < 0 else 0.0, "credit": delta if delta > 0 else 0.0,
                    "balance": a["closing"], "status": status, "page": r["page"],
                    "time": r["time"], "txn_id": r["id"]})
    out.reverse()                                         # oldest first, like the other banks
    return out


# --------------------------------------------------------------------------- LLM fallback
def llm_fill(rows):
    """Ask the LLM only for amount+balance of date-lines the code could not read."""
    bad = [r for r in rows if r["balance"] is None]
    if not bad:
        return 0
    batches = [bad[i:i + 15] for i in range(0, len(bad), 15)]

    def work(batch):
        prompt = ("Each line below is one bank transaction. For each line output exactly one line: "
                  "description|amount|balance\n"
                  "amount = the single transaction amount, balance = the running balance. "
                  "Numbers only, no commas. Output nothing else.\n\n" + "\n".join(r["raw"] for r in batch))
        try:
            resp = requests.post(f"{OLLAMA_URL}/api/generate",
                                 json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                                       "options": {"temperature": 0, "num_predict": 60 * len(batch)}},
                                 headers={"ngrok-skip-browser-warning": "true"}, timeout=180)
            lines = [l for l in resp.json()["response"].splitlines() if "|" in l]
        except Exception as e:
            print(f"  LLM fallback not available ({type(e).__name__}); leaving {len(batch)} rows as 'unparsed'")
            return 0
        if len(lines) != len(batch):
            return 0
        n = 0
        for r, l in zip(batch, lines):
            p = l.split("|")
            try:
                amt, bal = abs(float(p[-2].replace(",", ""))), float(p[-1].replace(",", ""))
                r["cands"], r["balance"] = [(amt, p[-2])], bal
                r["head"] = "|".join(p[:-2]).strip() or r["head"]
                n += 1
            except (ValueError, IndexError):
                pass
        return n

    with ThreadPoolExecutor(WORKERS) as ex:
        return sum(ex.map(work, batches))


def save_csv(path, out):
    outfile = os.path.splitext(path)[0] + "_transactions.csv"
    try:
        f = open(outfile, "w", newline="", encoding="utf-8-sig")   # utf-8-sig: opens cleanly in Excel
    except PermissionError:                                        # the old CSV is open in Excel
        outfile = os.path.splitext(outfile)[0] + f"_{int(time.time())}.csv"
        print(f"NOTE: the CSV is open in another program, saving as {os.path.basename(outfile)} instead.")
        f = open(outfile, "w", newline="", encoding="utf-8-sig")
    with f:
        w = csv.writer(f)
        w.writerow(["date", "description", "debit", "credit", "balance", "status", "page", "time", "txn_id"])
        for r in out:
            w.writerow([r["date"], r["desc"], r["debit"], r["credit"],
                        "" if r["balance"] is None else r["balance"], r["status"], r["page"],
                        r.get("time", ""), r.get("txn_id", "")])
    return outfile


def main():
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    path = args[0]
    bank = args[1] if len(args) > 1 else "?"
    pw = args[2] if len(args) > 2 else None
    t0 = time.time()

    with pdfplumber.open(path, password=pw) as pdf:   # unlocked locally; password never leaves this PC
        pages = len(pdf.pages)
        if "--dump" in flags:
            pg = pdf.pages[1] if pages > 1 else pdf.pages[0]
            print("\n".join((pg.extract_text(x_tolerance=1.5) or "(no text on this page)").splitlines()[:45]))
            return
        easy = is_easypaisa(pdf)
        if easy:
            if bank.upper() not in ("EASYPAISA", "EP"):
                print(f"NOTE: this is an Easypaisa statement (you typed {bank}); using the Easypaisa reader.")
            bank = "EASYPAISA"
            out = parse_easypaisa(pdf)
            text, filled = "", 0
        else:
            xt = choose_xtol(pdf)
            rows, texts = extract_rows(pdf, xt)
            text = "\n".join(texts)

    if not easy:
        if len(text) < 50 * pages:
            print("WARNING: this PDF looks scanned (little or no text). It needs OCR first.")
        rows, opening_row = split_markers(rows)
        filled = llm_fill(rows)
        m = OPENING_RE.search(text)
        opening = opening_row if opening_row is not None else (to_num(m.group(1)) if m else None)
        out = resolve(rows, opening)

    outfile = save_csv(path, out)

    ok = sum(r["status"] in ("ok", "first_row_unverified") if easy else r["status"] == "ok" for r in out)
    print(f"[{bank}] {pages} pages, {len(out)} rows, {ok} verified by balance, "
          f"{len(out) - ok} need review, {filled} filled by LLM, {time.time() - t0:.1f}s")

    if easy:
        bad = [r for r in out if r["status"] != "ok"]
        for r in bad[:10]:
            print(f"  review: page {r['page']} {r['date']} {r['time']} status={r['status']} {r['desc'][:50]}")
        if not bad:
            print("Every row's opening balance matches the previous row's closing balance: nothing missing.")
    else:
        chain = [r for r in out if r["balance"] is not None]
        closings = [to_num(x) for rx in CLOSING_RES for x in rx.findall(text)]
        if chain and closings:
            if any(abs(chain[-1]["balance"] - c) < 0.02 for c in closings):
                print(f"Closing balance {chain[-1]['balance']:,.2f} matches the statement: nothing missing at the end.")
            else:
                print(f"WARNING: last balance {chain[-1]['balance']:,.2f} differs from the statement's closing "
                      f"balance {closings[0]:,.2f}. Some rows may be missing.")
    print(f"Saved: {outfile}")


if __name__ == "__main__":
    main()