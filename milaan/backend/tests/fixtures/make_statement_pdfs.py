"""Regenerates the invented statement PDFs used by test_statement_pdf.py.

Run: python tests/fixtures/make_statement_pdfs.py  (needs reportlab; not a runtime dependency)
All names, accounts and transaction IDs are invented.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas

HERE = Path(__file__).parent
styles = getSampleStyleSheet()


def bank_table():
    doc = SimpleDocTemplate(str(HERE / "statement_bank_table.pdf"), pagesize=A4)
    rows = [["Date", "Description", "Reference No", "Debit", "Credit", "Balance"],
            ["01/11/2026", "Opening balance", "", "", "", "10,000.00"],
            ["02/11/2026 14:22", "IBFT from HIRA KHAN", "FT2611024471", "", "3,500.00", "13,500.00"],
            ["02/11/2026 16:05", "IBFT from SANA MALIK", "FT2611025530", "", "4,200.00", "17,700.00"],
            ["03/11/2026 09:10", "Bill payment K-Electric", "BP7730021", "2,150.00", "", "15,550.00"],
            ["03/11/2026 11:14", "Raast transfer from AYESHA NOOR", "RST903311774", "", "1,200.00", "16,750.00"],
            ["04/11/2026 12:35", "IBFT from HAMZA AHMED", "FT2611047720", "", "6,000.00", "22,750.00"]]
    doc.build([Paragraph("Sample Bank Ltd - Account Statement", styles["Title"]),
               Paragraph("Account: 0123-4567890 &nbsp; Statement Period: 01/11/2026 to 07/11/2026", styles["Normal"]),
               Spacer(1, 12), Table(rows)])


def wallet_list():
    c = canvas.Canvas(str(HERE / "statement_wallet_list.pdf"), pagesize=A4)
    y = 800
    for line in ["Mobile Wallet - Transaction History", "Account: 0300-1234567",
                 "From 09 Nov 2026 to 10 Nov 2026", "",
                 "09 Nov 2026 14:22  Money Received from Hira Khan  TID: 03847562911  Rs. 3,500.00",
                 "09 Nov 2026 15:40  Money Sent to Bilal Traders  TID: 03847569002  Rs. 1,000.00",
                 "09 Nov 2026 16:40  Money Received from Usman Tariq  TID: 03847570118  Rs. 2,800.00",
                 "10 Nov 2026 11:05  Money Received from Mariam Ali  TID: 03847581234  Rs. 2,100.00"]:
        c.drawString(40, y, line); y -= 18
    c.save()


def amount_column():
    """Single Amount column with Cr/Dr markers, date-only rows and a wrapped description."""
    c = canvas.Canvas(str(HERE / "statement_amount_column.pdf"), pagesize=A4)
    c.drawString(40, 800, "Online Banking - Account Activity   For the period 05-Nov-2026 to 06-Nov-2026")
    y = 770
    c.drawString(40, y, "Date"); c.drawString(130, y, "Details"); c.drawString(420, y, "Amount")
    for date, details, amount, wrap in [
        ("05-Nov-2026", "Inward IBFT ZAIN MALIK Ref No 556677889", "900.00 Cr", None),
        ("05-Nov-2026", "POS purchase Imtiaz Store", "1,250.00 Dr", None),
        ("06-Nov-2026", "Inward transfer NIDA SALEEM", "3,300.00 Cr", "Ref No 991122334"),
    ]:
        y -= 18
        c.drawString(40, y, date); c.drawString(130, y, details); c.drawString(420, y, amount)
        if wrap:
            y -= 14
            c.drawString(130, y, wrap)
    c.save()


def scanned_image():
    """A PDF with no text layer (just a drawn rectangle), like a phone scan."""
    c = canvas.Canvas(str(HERE / "statement_scanned.pdf"), pagesize=A4)
    c.rect(40, 600, 400, 150, fill=1)
    c.save()


if __name__ == "__main__":
    bank_table(); wallet_list(); amount_column(); scanned_image(); print("written")
