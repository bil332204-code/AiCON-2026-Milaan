"""Statement PDF reading. Fixtures are invented; regenerate with tests/fixtures/make_statement_pdfs.py."""
from pathlib import Path

import pytest

from app.parsing import parse_statement
from app.statement_pdf import StatementPDFError, read_statement_pdf, parse_date, parse_clock

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return (FIX / name).read_bytes()


def summary(result):
    return [(r["direction"], r["amount"], r["counterparty"], r["transaction_id"]) for r in result["rows"]]


def test_bank_table_uses_debit_and_credit_columns_and_ignores_balance():
    result = read_statement_pdf(load("statement_bank_table.pdf"))
    assert summary(result) == [
        ("CREDIT", "3500.00", "HIRA KHAN", "FT2611024471"),
        ("CREDIT", "4200.00", "SANA MALIK", "FT2611025530"),
        ("DEBIT", "2150.00", "Bill payment K-Electric", "BP7730021"),
        ("CREDIT", "1200.00", "AYESHA NOOR", "RST903311774"),
        ("CREDIT", "6000.00", "HAMZA AHMED", "FT2611047720"),
    ]
    assert result["rows"][0]["posted_at"] == "2026-11-02T14:22:00+05:00"
    assert result["period"] == {"start": "2026-11-01T00:00:00+05:00", "end": "2026-11-07T23:59:59+05:00"}
    assert result["account_hint"] == "0123-4567890"
    assert result["credits"] == 4


def test_wallet_list_reads_direction_from_words():
    result = read_statement_pdf(load("statement_wallet_list.pdf"))
    assert summary(result) == [
        ("CREDIT", "3500.00", "Hira Khan", "03847562911"),
        ("DEBIT", "1000.00", "Bilal Traders", "03847569002"),
        ("CREDIT", "2800.00", "Usman Tariq", "03847570118"),
        ("CREDIT", "2100.00", "Mariam Ali", "03847581234"),
    ]
    assert all(not r["needs_check"] for r in result["rows"])


def test_amount_column_with_cr_dr_markers_wrapped_reference_and_missing_time():
    result = read_statement_pdf(load("statement_amount_column.pdf"))
    assert summary(result) == [
        ("CREDIT", "900.00", "ZAIN MALIK", "556677889"),
        ("DEBIT", "1250.00", "POS purchase Imtiaz Store", ""),
        ("CREDIT", "3300.00", "NIDA SALEEM", "991122334"),
    ]
    assert all("time" in r["needs_check"] for r in result["rows"])
    assert "transaction_id" in result["rows"][1]["needs_check"]
    assert result["warnings"]


@pytest.mark.parametrize("raw, message", [
    (b"not a pdf", "not a PDF"),
    ((FIX / "statement_scanned.pdf").read_bytes(), "scanned image"),
])
def test_unreadable_files_get_a_plain_explanation(raw, message):
    with pytest.raises(StatementPDFError, match=message):
        read_statement_pdf(raw)


def test_rows_import_through_the_normal_statement_validation():
    result = read_statement_pdf(load("statement_wallet_list.pdf"))
    csv = "posted_at,direction,amount,counterparty,transaction_id\n" + "".join(
        f'{r["posted_at"]},{r["direction"]},{r["amount"]},{r["counterparty"]},{r["transaction_id"]}\n' for r in result["rows"])
    rows = parse_statement(csv.encode(), "owner", "wallet-main")
    assert [r["amount_paisa"] for r in rows] == [350000, 100000, 280000, 210000]


@pytest.mark.parametrize("text, expected", [
    ("02/11/2026", (2026, 11, 2)), ("2-11-26", (2026, 11, 2)), ("2026-11-02", (2026, 11, 2)),
    ("02 Nov 2026", (2026, 11, 2)), ("02-Nov-2026", (2026, 11, 2)), ("Nov 2, 2026", (2026, 11, 2)),
])
def test_date_formats_are_day_first(text, expected):
    day, _ = parse_date(text)
    assert (day.year, day.month, day.day) == expected


def test_twelve_hour_clock():
    assert parse_clock("02:05 PM") == (14, 5, 0)
    assert parse_clock("12:10 am") == (0, 10, 0)
    assert parse_clock("25:99") is None


def test_endpoint_requires_sign_in_and_returns_rows(env, auth):
    client = env[0]
    pdf = load("statement_bank_table.pdf")
    assert client.post("/api/statements/read-pdf", files={"file": ("s.pdf", pdf, "application/pdf")}).status_code == 401
    r = client.post("/api/statements/read-pdf", headers=auth, files={"file": ("s.pdf", pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rows"]) == 5 and body["filename"] == "s.pdf" and len(body["source_sha256"]) == 64
    bad = client.post("/api/statements/read-pdf", headers=auth, files={"file": ("s.pdf", b"hello", "application/pdf")})
    assert bad.status_code == 422 and "not a PDF" in bad.json()["detail"]
