from collections import Counter
from datetime import timedelta
from .parsing import paisa, parse_time, norm_ref, full_ref

from matching.names import name_similarity

RULES_VERSION = "milaan-rules-2.0-review"

def compute_matches(orders, claims, statements, lines, allocated_keys):
    """Pure deterministic rules enhanced with AiCON Pakistani name similarity."""
    refs = Counter((c.account_id, norm_ref(c.fields.get("transaction_id"))) for c in claims if full_ref(c.fields.get("transaction_id")))
    hashes = Counter(c.sha256 for c in claims)
    credit_counts = Counter(l.credit_key for l in lines if l.direction == "CREDIT")
    output = []
    order_lookup = {order.id: order for order in orders}
    for order in orders:
        proofs = [c for c in claims if c.order_id == order.id]
        claim = proofs[0] if len(proofs) == 1 else None
        row = {"order_id": order.id, "claim_id": claim.id if claim else None, "machine_verdict": "review", "final_status": "review",
               "reason_code": "NO_PROOF", "reason": "No payment proof is linked to this order.", "evidence": [], "candidate_ids": [], "selected_line_id": None}
        def decision(code, reason, status="review"):
            row.update(reason_code=code, reason=reason, machine_verdict=status, final_status=status)
        if len(proofs) > 1:
            code, reason, candidate_ids, evidence = multiple_payment_review(order, proofs, statements, lines, allocated_keys, refs, hashes)
            decision(code, reason)
            row["candidate_ids"], row["evidence"] = candidate_ids, evidence
        elif claim:
            f = claim.fields
            try:
                amount, at = paisa(f.get("amount_pkr")), parse_time(f.get("datetime_local"))
            except (ValueError, TypeError):
                amount, at = None, None
            stmt = next((s for s in statements if s.account_id == order.account_id), None)
            ref = f.get("transaction_id")
            credits = [l for l in lines if l.account_id == order.account_id and l.direction == "CREDIT" and l.currency == "PKR"]
            exact = [l for l in credits if full_ref(ref) and norm_ref(l.transaction_id) == norm_ref(ref)]
            nearby = [l for l in credits if amount and at and l.amount_paisa == amount and abs((l.posted_at-at).total_seconds()) <= 600]

            # AiCON: Pakistani name similarity candidate search
            cust_name = getattr(order, "customer_name", "") or ""
            name_candidates = []
            if name_similarity and cust_name and amount and at:
                for l in credits:
                    if l.amount_paisa == amount and abs((l.posted_at - at).total_seconds()) <= 86400:
                        cp = getattr(l, "counterparty", "") or ""
                        if cp and name_similarity(cust_name, cp).combined() >= 0.70:
                            name_candidates.append(l)

            candidates = list({l.id: l for l in exact + nearby + name_candidates}.values())
            row["candidate_ids"] = [l.id for l in candidates]

            best_name_score = 0.0
            best_name_details = None
            if name_similarity and cust_name:
                eval_pool = candidates if candidates else exact
                for c_line in eval_pool:
                    cp = getattr(c_line, "counterparty", "") or ""
                    if cp:
                        ns = name_similarity(cust_name, cp)
                        score = round(ns.combined(), 3)
                        if score > best_name_score:
                            best_name_score = score
                            best_name_details = {
                                "counterparty": cp,
                                "score": score,
                                "signals": ns.as_dict(),
                            }

            row["evidence"] = [
                {"check": "fields_checked", "ok": claim.fields_checked},
                {"check": "amount_equals_order", "ok": amount == order.amount_due_paisa, "claim_paisa": amount, "order_paisa": order.amount_due_paisa},
                {"check": "account_equals_order", "ok": claim.account_id == order.account_id},
                {"check": "full_reference", "ok": full_ref(ref)},
                {"check": "reference_correspondence_verified", "ok": bool(stmt and stmt.references_verified)},
            ]
            if best_name_details:
                row["evidence"].append({
                    "check": "pakistani_name_similarity",
                    "ok": best_name_score >= 0.70,
                    "score": best_name_score,
                    "matched_name": best_name_details["counterparty"],
                    "order_name": cust_name,
                    "signals": best_name_details["signals"],
                })
            if not f.get("is_payment_receipt", False) or not claim.fields_checked or not amount or not at:
                decision("UNREADABLE", "Extraction is incomplete, disagrees, or needs a human check.")
            elif claim.account_id != order.account_id:
                decision("ACCOUNT_CONFLICT", "Claim and order receiving accounts differ.")
            elif hashes[claim.sha256] > 1 or (full_ref(ref) and refs[(claim.account_id, norm_ref(ref))] > 1):
                decision("REUSED_PROOF", "The same image or full reference is claimed more than once.")
            elif reversal_status(f.get("status_text")) or (exact and any(
                l.account_id == order.account_id and l.currency == "PKR" and l.direction == "DEBIT"
                and norm_ref(l.transaction_id) == norm_ref(ref) for l in lines)):
                decision("REVERSAL", "Receipt status or a same-reference debit suggests a refund/reversal. Resolve the source evidence before allocating.")
                row["evidence"].append({"check": "possible_refund_or_reversal", "ok": False, "required": "Confirm whether the credit was reversed or refunded; do not treat a debit as payment."})
            elif not successful_status(f.get("status_text")):
                decision("STATUS_CONFLICT", "Payment status is missing, unrecognized, pending or unsuccessful. Check the receipt.")
            elif amount != order.amount_due_paisa:
                if len(exact) == 1 and exact[0].amount_paisa == amount:
                    extra = amount-order.amount_due_paisa
                    possible = [o.id for o in orders if o.id != order.id and o.account_id == order.account_id and o.amount_due_paisa == extra]
                    code = "UNDERPAYMENT" if extra < 0 else "COMBINED_PAYMENT" if possible else "OVERPAYMENT"
                    decision(code, "Source credit and receipt agree, but the order is only partly paid." if extra < 0 else "A larger source credit may cover other orders or an overpayment. Confirm its purpose and allocate explicit shares.")
                    row["evidence"].append({"check": "payment_difference", "ok": False, "receipt_paisa": amount,
                        "order_paisa": order.amount_due_paisa, "difference_paisa": extra, "possible_order_ids": possible,
                        "source_claim_id": claim.id, "required": "Review explicit allocations; no automatic shipping or refund."})
                else:
                    decision("AMOUNT_CONFLICT", "The claimed amount differs from the order total.")
            elif not stmt or not stmt.complete or not stmt.coverage_start <= at <= stmt.coverage_end:
                decision("COVERAGE", "Complete statement coverage for the claim is not established.")
                row["evidence"].append({"check": "statement_coverage", "ok": False, "claim_at": at.isoformat(),
                    "required": "Import and confirm complete receiving-account coverage; allow time for delayed posting."})
            elif any(credit_counts[l.credit_key] > 1 for l in candidates):
                decision("DUPLICATE_CREDIT", "Source records contain ambiguous duplicate credits; correct the statement.")
            elif any(l.credit_key in allocated_keys for l in candidates):
                decision("CREDIT_ALREADY_USED", "A candidate credit is already assigned in this seller's retained records.")
            elif len(exact) == 1:
                credit = exact[0]
                if credit.amount_paisa != amount:
                    decision("AMOUNT_CONFLICT", "The reference matches, but the statement amount differs.")
                elif abs((credit.posted_at-at).total_seconds()) > 86400:
                    decision("DATE_CONFLICT", "The same reference has delayed posting or a conflicting date; verify the source records.")
                elif not stmt.references_verified:
                    decision("VERIFY_REFERENCE", "Sender and receiver reference correspondence needs verification.")
                else:
                    decision("EXACT_MATCH", "One full reference and exact PKR credit match the order.", "ship")
                    row["selected_line_id"] = credit.id
            elif candidates:
                decision("POSSIBLE_MATCH", "Amount and time suggest a candidate. A person must choose.")
            elif not full_ref(ref):
                decision("PARTIAL_REFERENCE", "Ask for a complete transaction reference or clearer proof.")
            elif not stmt.references_verified:
                decision("VERIFY_REFERENCE", "Reference correspondence is unverified; inspect the statement before deciding.")
            elif at < stmt.coverage_start + timedelta(minutes=10) or at > stmt.coverage_end - timedelta(minutes=30):
                decision("POSTING_WINDOW", "Import a wider or newer statement to allow for posting delays.")
            else:
                decision("NOT_FOUND", "No candidate credit was found in the supplied statement.", "hold")
        if not proofs:
            proposal = combined_payment_proposal(order, order_lookup, claims, lines)
            if proposal:
                row.update(reason_code="COMBINED_PAYMENT", reason="A larger receipt-linked credit may cover this and another order. Confirm the relationship explicitly; no individual proof is assumed.",
                           candidate_ids=[proposal[0].id], evidence=[{"check": "combined_payment_proposal", "ok": False,
                           "source_claim_id": proposal[1].id, "required": "Confirm shared payment purpose and exact per-order shares."}])
        output.append(row)
    # Resolve shared-credit conflicts across the whole batch before making any allocation.
    chosen = Counter(r["selected_line_id"] for r in output if r["selected_line_id"])
    for r in output:
        if r["selected_line_id"] and chosen[r["selected_line_id"]] > 1:
            r.update(machine_verdict="review", final_status="review", selected_line_id=None,
                     reason_code="CONTESTED_CREDIT", reason="More than one order contests this credit.")
    return output

def re_failed(text):
    import re
    return bool(re.search(r"\b(failed|pending|reversed|cancelled|canceled|unsuccessful)\b", str(text or ""), re.I))

def successful_status(text):
    return str(text or "").strip().casefold() in {
        "success", "successful", "completed", "paid", "payment successful", "transaction successful"
    }


def reversal_status(text):
    import re
    return bool(re.search(r"\b(reversed|refunded|refund|reversal|chargeback)\b", str(text or ""), re.I))


def combined_payment_proposal(order, order_lookup, claims, lines):
    for claim in claims:
        source_order = order_lookup.get(claim.order_id)
        if not source_order or source_order.id == order.id or claim.account_id != order.account_id:
            continue
        fields = claim.fields
        try: amount = paisa(fields.get("amount_pkr"))
        except (ValueError, TypeError): continue
        if not claim.fields_checked or not fields.get("is_payment_receipt") or not successful_status(fields.get("status_text")):
            continue
        if amount != order.amount_due_paisa + source_order.amount_due_paisa or not full_ref(fields.get("transaction_id")):
            continue
        exact = [l for l in lines if l.account_id == order.account_id and l.direction == "CREDIT" and l.currency == "PKR"
                 and l.amount_paisa == amount and norm_ref(l.transaction_id) == norm_ref(fields.get("transaction_id"))]
        if len(exact) == 1:
            return exact[0], claim
    return None


def multiple_payment_review(order, proofs, statements, lines, allocated_keys, refs, hashes):
    evidence, candidates, amounts = [], [], []
    def finish(code, reason): return code, reason, list(dict.fromkeys(candidates)), evidence
    for claim in proofs:
        f = claim.fields
        try: amount, at = paisa(f.get("amount_pkr")), parse_time(f.get("datetime_local"))
        except (ValueError, TypeError): return finish("UNREADABLE", "Check every receipt amount and timestamp before reviewing split funding.")
        if not claim.fields_checked or not f.get("is_payment_receipt"):
            return finish("UNREADABLE", "Confirm every receipt before reviewing split funding.")
        if reversal_status(f.get("status_text")):
            return finish("REVERSAL", "A receipt indicates reversal/refund; resolve the original evidence first.")
        if not successful_status(f.get("status_text")):
            return finish("STATUS_CONFLICT", "Every contributing receipt needs a recognized successful payment status.")
        if claim.account_id != order.account_id:
            return finish("ACCOUNT_CONFLICT", "All receipts must use the order's receiving account.")
        ref = f.get("transaction_id")
        if hashes[claim.sha256] > 1 or (full_ref(ref) and refs[(claim.account_id, norm_ref(ref))] > 1):
            return finish("REUSED_PROOF", "Resolve duplicate receipts/references before reviewing split funding.")
        statement = next((s for s in statements if s.account_id == order.account_id), None)
        if not statement or not statement.complete or not statement.coverage_start <= at <= statement.coverage_end:
            return finish("COVERAGE", "Import complete coverage for every contributing receipt; delayed postings need wider coverage.")
        if not statement.references_verified:
            return finish("VERIFY_REFERENCE", "Verify sender/receiver reference correspondence for all parts.")
        exact = [l for l in lines if l.account_id == order.account_id and l.direction == "CREDIT" and l.currency == "PKR"
                 and full_ref(ref) and norm_ref(l.transaction_id) == norm_ref(ref)]
        candidates.extend(l.id for l in exact)
        if len(exact) > 1:
            return finish("DUPLICATE_CREDIT", "Multiple source credits share a contributing reference; correct the statement.")
        if not exact:
            return finish("MULTIPLE_PROOFS", "A contributing receipt lacks a unique full-reference credit; confirm each source part.")
        line = exact[0]
        if any(l.account_id == order.account_id and l.direction == "DEBIT" and l.currency == "PKR" and norm_ref(l.transaction_id) == norm_ref(ref) for l in lines):
            return finish("REVERSAL", "A same-reference debit may reverse a contributing credit; resolve the source first.")
        if line.credit_key in allocated_keys:
            return finish("CREDIT_ALREADY_USED", "A contributing credit is already reserved in retained records.")
        if line.amount_paisa != amount:
            return finish("AMOUNT_CONFLICT", "Receipt and statement amounts disagree for a contributing part.")
        if abs((line.posted_at-at).total_seconds()) > 86400:
            return finish("DATE_CONFLICT", "A contributing credit has delayed posting or a conflicting date.")
        amounts.append(amount)
        evidence.append({"check": "split_payment_source", "ok": True, "claim_id": claim.id, "statement_line_id": line.id, "amount_paisa": amount})
    total = sum(amounts)
    evidence.append({"check": "split_payment_total", "ok": total == order.amount_due_paisa,
                     "total_paisa": total, "order_paisa": order.amount_due_paisa,
                     "required": "Confirm the purpose of all parts and save an explicit allocation plan; this is not automatic SHIP."})
    return finish("UNDERPAYMENT" if total < order.amount_due_paisa else "OVERPAYMENT" if total > order.amount_due_paisa else "SPLIT_PAYMENT",
                  "Multiple checked receipt-linked credits total the supplied payment evidence. Review their purpose and explicitly allocate each part.")
