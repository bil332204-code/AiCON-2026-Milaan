"""Synthetic fixture, isolated by batch/account; never uploaded to an AI provider."""
from datetime import timedelta
from hashlib import sha256
from .models import Batch, Order, Statement, StatementLine, Claim, now
from .parsing import parse_time, credit_identity
from .jobs import audit

CASES = [
    ("1042", "Hira", "3500", "14:22", "DEMO1042", True),
    ("1043", "Sana", "4200", "16:05", "", False),
    ("1044", "Usman", "2800", "16:40", "DEMO1044", False),
    ("1045", "Ayesha", "1200", "11:14", "DEMO1045", True),
    ("1046", "Hamza", "6000", "12:35", "DEMO1046", True),
    ("1047", "Mariam", "2100", "13:09", "DEMO1047", True),
    ("1048", "Ali", "1800", "15:45", "DEMO1048", False),
    ("1049", "Ahmed", "2500", "14:50", "DEMO1049", True),
    ("1050", "Sara", "2500", "14:50", "DEMO1049", False),
    ("1051", "Nida", "3300", "17:11", "DEMO1051", True),
    ("1052", "Zain", "900", None, "DEMO1052", False),
    ("1053", "Hassan", "4000", "21:15", "DEMO1053", False),
]

def seed_demo(db, owner_id, settings):
    batch = Batch(owner_id=owner_id, name="Milaan sample · 12 orders", is_demo=True,
                  expires_at=now() + timedelta(hours=settings.retention_hours))
    db.add(batch); db.flush()
    account = "sample-" + batch.id
    stamp = lambda t: "2026-10-09T" + t + ":00+05:00"
    statement = Statement(batch_id=batch.id, account_id=account, provider_pair="synthetic-fixture",
                          coverage_start=parse_time(stamp("08:00")), coverage_end=parse_time(stamp("20:00")),
                          complete=True, references_verified=True, filename="SYNTHETIC-demo-statement.csv")
    db.add(statement); db.flush()
    def line(name, amount, at, ref):
        row = dict(account_id=account, posted_at=parse_time(stamp(at)), amount_paisa=int(amount)*100,
                   direction="CREDIT", counterparty=name, transaction_id=ref, currency="PKR")
        row["credit_key"] = credit_identity(owner_id, account, ref, row["posted_at"], row["amount_paisa"], name)
        db.add(StatementLine(batch_id=batch.id, statement_id=statement.id, **row))
    for ref, name, amount, at, transaction, has_credit in CASES:
        order = Order(batch_id=batch.id, order_ref="#"+ref, customer_name=name,
                      amount_due_paisa=int(amount)*100, account_id=account)
        db.add(order); db.flush()
        fields = dict(is_payment_receipt=True, provider_app="SYNTHETIC SAMPLE", amount_pkr=amount,
                      datetime_local=stamp(at) if at else None, transaction_id=transaction,
                      sender_name=name, receiver_hint="Sample store", status_text="Successful",
                      unreadable_fields=[] if at else ["datetime_local"])
        db.add(Claim(batch_id=batch.id, order_id=order.id, account_id=account, filename="SAMPLE-"+ref+".json",
                     sha256=sha256((batch.id+ref).encode()).hexdigest(), image_path=None,
                     fields=fields, fields_checked=bool(at), extraction_mode="sample",
                     extraction_status="ready" if at else "needs_review"))
        if has_credit: line(name, amount, at, transaction)
    line("Sana A", "4200", "16:04", "SAMPLE4201")
    line("Sana B", "4200", "16:09", "SAMPLE4202")
    audit(db, batch.id, owner_id, "synthetic_demo_created", {"sample_data": True, "orders": 12})
    return batch
