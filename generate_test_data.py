"""
generate_test_data.py
Creates realistic test assets for:
  - 10 Customer Store Orders
  - 10 Payment Screenshot Receipts (JPEG images with simulated banking UI)
  - 1 Bank Statement PDF with 20 records (including genuine credits, faulty amounts, 
    unrelated ATM debits, utility bills, vendor payments)
"""

import os
import csv
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF
from datetime import datetime, timezone

OUT_DIR = Path("test_assets")
RECEIPTS_DIR = OUT_DIR / "receipts"
OUT_DIR.mkdir(exist_ok=True)
RECEIPTS_DIR.mkdir(exist_ok=True)

# ── 1. The 10 Orders Definition ───────────────────────────────────────────────
ORDERS = [
    {
        "order_ref": "ORD-001",
        "customer_name": "Tariq Mahmood",
        "amount": 2500.0,
        "product": "Studio Mug x2",
        "scenario": "CLEAN_MATCH",
        "desc": "Exact amount, name and reference match -> SHIP",
        "receipt": {
            "ref": "TXN-TM-8801",
            "amount": 2500.0,
            "sender": "Tariq Mahmood",
            "status": "Successful",
            "date": "2026-10-10T10:00:00Z"
        }
    },
    {
        "order_ref": "ORD-002",
        "customer_name": "Mohammad Bilal Hussain",
        "amount": 4200.0,
        "product": "Canvas Tote Bag",
        "scenario": "URDU_TRANSLITERATION",
        "desc": "Pakistani variant (Mohammad->Muhammad, Hussain->Husain) -> SHIP",
        "receipt": {
            "ref": "TXN-BH-8802",
            "amount": 4200.0,
            "sender": "Muhammad Bilal Husain",
            "status": "Successful",
            "date": "2026-10-10T10:15:00Z"
        }
    },
    {
        "order_ref": "ORD-003",
        "customer_name": "Zubair Siddiqui",
        "amount": 1850.0,
        "product": "Leather Journal",
        "scenario": "NAME_TYPO",
        "desc": "Customer spelling typo (Zubayr Siddiki) handled by AiCON fuzzy matcher -> SHIP",
        "receipt": {
            "ref": "TXN-ZS-8803",
            "amount": 1850.0,
            "sender": "Zubayr Siddiki",
            "status": "Successful",
            "date": "2026-10-10T10:30:00Z"
        }
    },
    {
        "order_ref": "ORD-004",
        "customer_name": "Muhammad Ali",
        "amount": 3100.0,
        "product": "Everyday Notebook x3",
        "scenario": "INITIALS_MATCH",
        "desc": "Initials format (M. Ali vs Muhammad Ali) matched by AiCON -> SHIP",
        "receipt": {
            "ref": "TXN-MA-8804",
            "amount": 3100.0,
            "sender": "M. Ali",
            "status": "Successful",
            "date": "2026-10-10T10:45:00Z"
        }
    },
    {
        "order_ref": "ORD-005",
        "customer_name": "Usman Ghani",
        "amount": 5000.0,
        "product": "Desk Organizer Set",
        "scenario": "WRONG_AMOUNT",
        "desc": "Underpayment: customer claims / paid PKR 4000 instead of PKR 5000 -> REVIEW",
        "receipt": {
            "ref": "TXN-UG-8805",
            "amount": 4000.0,
            "sender": "Usman Ghani",
            "status": "Successful",
            "date": "2026-10-10T11:00:00Z"
        }
    },
    {
        "order_ref": "ORD-006",
        "customer_name": "Hamza Riaz",
        "amount": 3500.0,
        "product": "Wireless Mouse Pad",
        "scenario": "FAKE_RECEIPT",
        "desc": "Fraud check: Fake screenshot submitted, no money in bank statement -> HOLD",
        "receipt": {
            "ref": "FAKE-RECEIPT-9999",
            "amount": 3500.0,
            "sender": "Hamza Riaz",
            "status": "Successful",
            "date": "2026-10-10T11:15:00Z"
        }
    },
    {
        "order_ref": "ORD-007",
        "customer_name": "Kamran Akmal",
        "amount": 2100.0,
        "product": "Ceramic Mug",
        "scenario": "FAILED_TRANSACTION",
        "desc": "Failed transfer: screenshot indicates Payment Failed/Cancelled -> REVIEW",
        "receipt": {
            "ref": "TXN-FAIL-1007",
            "amount": 2100.0,
            "sender": "Kamran Akmal",
            "status": "Failed",
            "date": "2026-10-10T11:30:00Z"
        }
    },
    {
        "order_ref": "ORD-008",
        "customer_name": "Fatima Noor",
        "amount": 6000.0,
        "product": "Artisan Backpack",
        "scenario": "FAMILY_PAYER",
        "desc": "Family member (Waqas Ahmed) paid on behalf of customer -> AMBIGUOUS / POSSIBLE MATCH",
        "receipt": {
            "ref": "TXN-FP-8808",
            "amount": 6000.0,
            "sender": "Waqas Ahmed",
            "status": "Successful",
            "date": "2026-10-10T11:45:00Z"
        }
    },
    {
        "order_ref": "ORD-009",
        "customer_name": "Saad Sheikh",
        "amount": 2500.0,
        "product": "Studio Mug x2",
        "scenario": "DUPLICATE_CLAIM",
        "desc": "Duplicate proof: Reused the exact receipt from another order -> REVIEW / REUSED_PROOF",
        "receipt": {
            "ref": "TXN-DUP-ALREADY-USED",  # Reused from another claim
            "amount": 2500.0,
            "sender": "Saad Sheikh",
            "status": "Successful",
            "date": "2026-10-10T10:00:00Z"
        }
    },
    {
        "order_ref": "ORD-010",
        "customer_name": "Ayesha Khan",
        "amount": 1200.0,
        "product": "Pocket Notebook",
        "scenario": "NO_PROOF",
        "desc": "Customer placed order but never submitted receipt proof -> REVIEW / NO_PROOF",
        "receipt": None
    }
]

# Write Orders CSV
orders_csv_path = OUT_DIR / "orders.csv"
with open(orders_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["order_ref", "customer_name", "amount_due", "account_id"])
    for o in ORDERS:
        writer.writerow([o["order_ref"], o["customer_name"], f"{o['amount']:.2f}", "demo-store-main"])

print(f"[1/3] Created 10 orders in {orders_csv_path}")

# ── 2. Generate Payment Screenshots (PIL Images) ─────────────────────────────
def generate_receipt_image(order_ref: str, r_info: dict, filename: Path):
    im = Image.new("RGB", (700, 520), "#0f172a") # modern dark mobile banking style
    draw = ImageDraw.Draw(im)

    # Card background
    draw.rounded_rectangle([30, 25, 670, 495], radius=16, fill="#1e293b", outline="#334155", width=2)

    try:
        font_large = ImageFont.truetype("arial.ttf", 26)
        font_med = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except OSError:
        font_large = font_med = font_small = ImageFont.load_default()

    status = r_info["status"]
    status_color = "#22c55e" if status == "Successful" else "#ef4444"

    # Header
    draw.text((50, 45), "Raast / IBFT Payment Receipt", fill="#94a3b8", font=font_small)
    draw.text((50, 75), f"Status: {status.upper()}", fill=status_color, font=font_large)

    # Amount box
    draw.rounded_rectangle([50, 120, 650, 185], radius=10, fill="#0f172a")
    draw.text((70, 132), "Total Paid", fill="#64748b", font=font_small)
    draw.text((70, 148), f"PKR {r_info['amount']:,.2f}", fill="#f8fafc", font=font_large)

    # Key details
    y = 205
    fields = [
        ("Transaction ID (Ref):", r_info["ref"]),
        ("Payer Name:", r_info["sender"]),
        ("Receiver Account:", "demo-store-main (AiCON Retail)"),
        ("Date & Time:", r_info["date"]),
        ("Linked Order:", order_ref),
    ]
    for label, val in fields:
        draw.text((50, y), label, fill="#94a3b8", font=font_med)
        draw.text((280, y), str(val), fill="#f8fafc", font=font_med)
        draw.line([50, y+30, 650, y+30], fill="#334155", width=1)
        y += 40

    draw.text((50, 465), "Verified Digital Payment Receipt - AiCON Testing", fill="#64748b", font=font_small)

    im.save(filename, "JPEG", quality=90)

for o in ORDERS:
    if o["receipt"]:
        fn = RECEIPTS_DIR / f"{o['order_ref']}_receipt.jpg"
        generate_receipt_image(o["order_ref"], o["receipt"], fn)

print(f"[2/3] Generated 9 payment screenshot receipts in {RECEIPTS_DIR}")

# ── 3. Bank Statement with 20 Records ─────────────────────────────────────────
# 6 Genuine incoming payments for orders (1, 2, 3, 4, 5, 8)
# 14 Unrelated / Faulty / Decoy records:
#   - 4 ATM cash withdrawals (Debit)
#   - 3 Utility bills (Debit)
#   - 3 Outgoing vendor IBFTs (Debit)
#   - 4 Unrelated customer deposits (Credit to wrong people/amounts)

BANK_RECORDS = [
    # 1. Clean match for Order 1
    {"date": "2026-10-10", "time": "10:02:00", "dir": "CREDIT", "amount": 2500.0, "sender": "TARIQ MAHMOOD", "ref": "TXN-TM-8801"},
    # 2. Transliteration for Order 2
    {"date": "2026-10-10", "time": "10:16:30", "dir": "CREDIT", "amount": 4200.0, "sender": "MUHAMMAD BILAL HUSAIN", "ref": "TXN-BH-8802"},
    # 3. Typo for Order 3
    {"date": "2026-10-10", "time": "10:32:00", "dir": "CREDIT", "amount": 1850.0, "sender": "ZUBAYR SIDDIKI", "ref": "TXN-ZS-8803"},
    # 4. Initials for Order 4
    {"date": "2026-10-10", "time": "10:48:15", "dir": "CREDIT", "amount": 3100.0, "sender": "M ALI", "ref": "TXN-MA-8804"},
    # 5. Underpayment for Order 5
    {"date": "2026-10-10", "time": "11:05:00", "dir": "CREDIT", "amount": 4000.0, "sender": "USMAN GHANI", "ref": "TXN-UG-8805"},
    # 6. Family payer for Order 8
    {"date": "2026-10-10", "time": "11:47:00", "dir": "CREDIT", "amount": 6000.0, "sender": "WAQAS AHMED", "ref": "TXN-FP-8808"},

    # --- 14 Faulty / Background / Noise Records ---
    # 7. Faulty: Decoy payment with same amount (PKR 2500) but completely different sender
    {"date": "2026-10-10", "time": "12:00:00", "dir": "CREDIT", "amount": 2500.0, "sender": "ARSLAN JAVED", "ref": "IBFT-DECOY-7701"},
    # 8. Background: K-Electric utility bill debit
    {"date": "2026-10-10", "time": "08:15:00", "dir": "DEBIT", "amount": 9450.0, "sender": "K-ELECTRIC BILL PAYMENT", "ref": "BILL-KE-9901"},
    # 9. Background: ATM Cash withdrawal
    {"date": "2026-10-10", "time": "09:00:00", "dir": "DEBIT", "amount": 5000.0, "sender": "ATM CASH WDL BLUE AREA", "ref": "ATM-WDL-1092"},
    # 10. Background: Vendor packaging payment
    {"date": "2026-10-10", "time": "09:30:00", "dir": "DEBIT", "amount": 18500.0, "sender": "PACKAGING SOLUTIONS LTD", "ref": "IBFT-VEND-3021"},
    # 11. Faulty: Unrelated deposit
    {"date": "2026-10-10", "time": "12:30:00", "dir": "CREDIT", "amount": 15000.0, "sender": "SADIA MALIK", "ref": "RAAST-UNREL-4401"},
    # 12. Background: Bank fee / FED charges
    {"date": "2026-10-10", "time": "13:00:00", "dir": "DEBIT", "amount": 58.0, "sender": "FED ON DIGITAL SERVICES", "ref": "BANK-CHG-0012"},
    # 13. Faulty: Decoy payment
    {"date": "2026-10-10", "time": "13:15:00", "dir": "CREDIT", "amount": 3500.0, "sender": "KASHIF MEHMOOD", "ref": "TXN-MISMATCH-5501"},
    # 14. Background: Office internet bill
    {"date": "2026-10-10", "time": "14:00:00", "dir": "DEBIT", "amount": 4200.0, "sender": "PTCL BROADBAND BILL", "ref": "BILL-PTCL-8802"},
    # 15. Background: ATM withdrawal
    {"date": "2026-10-10", "time": "14:45:00", "dir": "DEBIT", "amount": 10000.0, "sender": "ATM CASH WDL F-10 ISB", "ref": "ATM-WDL-4481"},
    # 16. Faulty: Random small credit
    {"date": "2026-10-10", "time": "15:20:00", "dir": "CREDIT", "amount": 750.0, "sender": "FAHEEM BUTT", "ref": "RAAST-SM-9021"},
    # 17. Background: Raw material inventory
    {"date": "2026-10-10", "time": "16:00:00", "dir": "DEBIT", "amount": 25000.0, "sender": "TEXTILE WHOLESALER", "ref": "IBFT-SUPPLY-6101"},
    # 18. Faulty: Reversed transaction
    {"date": "2026-10-10", "time": "16:30:00", "dir": "CREDIT", "amount": 2100.0, "sender": "REVERSAL / DISPUTED CREDIT", "ref": "REV-TXN-7782"},
    # 19. Background: Mobile topup
    {"date": "2026-10-10", "time": "17:00:00", "dir": "DEBIT", "amount": 1000.0, "sender": "JAZZ PREPAID LOAD", "ref": "TELCO-TOPUP-1190"},
    # 20. Faulty: Large unrelated company dividend
    {"date": "2026-10-10", "time": "17:45:00", "dir": "CREDIT", "amount": 55000.0, "sender": "ENGRO CORP DIVIDEND", "ref": "CORP-DIV-9921"},
]

# Write PDF Statement using FPDF
pdf = FPDF(orientation="P", unit="mm", format="A4")
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()
pdf.set_font("Helvetica", "B", 16)
pdf.cell(0, 10, "MEEZAN BANK - OFFICIAL ACCOUNT STATEMENT", ln=True, align="C")

pdf.set_font("Helvetica", "", 10)
pdf.cell(0, 6, "Account Title: AiCON Online Retail Store (demo-store-main)", ln=True)
pdf.cell(0, 6, "IBAN: PK64MEZN0001234567890102  |  Currency: PKR", ln=True)
pdf.cell(0, 6, "Statement Period: 2026-10-10 to 2026-10-10  |  Generated on: 10-Oct-2026", ln=True)
pdf.ln(4)

# Table Header
pdf.set_font("Helvetica", "B", 9)
pdf.set_fill_color(220, 230, 242)
pdf.cell(24, 7, "Date", 1, 0, "C", True)
pdf.cell(65, 7, "Description / Sender", 1, 0, "L", True)
pdf.cell(38, 7, "Reference / Txn ID", 1, 0, "L", True)
pdf.cell(20, 7, "Type", 1, 0, "C", True)
pdf.cell(28, 7, "Amount (PKR)", 1, 1, "R", True)

pdf.set_font("Helvetica", "", 8)
balance = 150000.0
for r in BANK_RECORDS:
    amt = r["amount"]
    if r["dir"] == "CREDIT":
        balance += amt
    else:
        balance -= amt

    pdf.cell(24, 6, r["date"], 1, 0, "C")
    pdf.cell(65, 6, r["sender"][:34], 1, 0, "L")
    pdf.cell(38, 6, r["ref"][:20], 1, 0, "L")
    pdf.cell(20, 6, r["dir"], 1, 0, "C")
    pdf.cell(28, 6, f"{amt:,.2f}", 1, 1, "R")

pdf_stmt_path = OUT_DIR / "bank_statement_20_records.pdf"
pdf.output(str(pdf_stmt_path))
print(f"[3/3] Generated 20-record Bank Statement PDF: {pdf_stmt_path}")

# Also save CSV version for fast direct matching / API fallback
csv_stmt_path = OUT_DIR / "bank_statement_20_records.csv"
with open(csv_stmt_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["posted_at", "direction", "amount", "counterparty", "transaction_id", "account_id", "currency"])
    for r in BANK_RECORDS:
        iso_time = f"{r['date']}T{r['time']}+00:00"
        writer.writerow([iso_time, r["dir"], f"{r['amount']:.2f}", r["sender"], r["ref"], "demo-store-main", "PKR"])

print(f"      Saved CSV mirror: {csv_stmt_path}")
print("\nAll 10 orders, 10 screenshot receipts, and 20 bank records generated successfully!")
