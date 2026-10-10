from collections import Counter
from datetime import timedelta
from .parsing import paisa, parse_time, norm_ref, full_ref

from matching.names import name_similarity

RULES_VERSION = "milaan-rules-1.1-aicon"

def compute_matches(orders, claims, statements, lines, allocated_keys):
    """Pure deterministic rules enhanced with AiCON Pakistani name similarity."""
    refs = Counter((c.account_id, norm_ref(c.fields.get("transaction_id"))) for c in claims if full_ref(c.fields.get("transaction_id")))
    hashes = Counter(c.sha256 for c in claims)
    credit_counts = Counter(l.credit_key for l in lines if l.direction == "CREDIT")
    output = []
    for order in orders:
        proofs = [c for c in claims if c.order_id == order.id]
        claim = proofs[0] if len(proofs) == 1 else None
        row = {"order_id": order.id, "claim_id": claim.id if claim else None, "machine_verdict": "review", "final_status": "review",
               "reason_code": "NO_PROOF", "reason": "No payment proof is linked to this order.", "evidence": [], "candidate_ids": [], "selected_line_id": None}
        def decision(code, reason, status="review"):
            row.update(reason_code=code, reason=reason, machine_verdict=status, final_status=status)
        if len(proofs) > 1: decision("MULTIPLE_PROOFS", "Several proofs are linked to the order. Resolve them before allocation.")
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
            elif re_failed(f.get("status_text")):
                decision("STATUS_CONFLICT", "The screenshot indicates a failed, pending or reversed payment.")
            elif amount != order.amount_due_paisa:
                decision("AMOUNT_CONFLICT", "The claimed amount differs from the order total.")
            elif not stmt or not stmt.complete or not stmt.coverage_start <= at <= stmt.coverage_end:
                decision("COVERAGE", "Complete statement coverage for the claim is not established.")
            elif any(credit_counts[l.credit_key] > 1 for l in candidates):
                decision("DUPLICATE_CREDIT", "Source records contain ambiguous duplicate credits; correct the statement.")
            elif any(l.credit_key in allocated_keys for l in candidates):
                decision("CREDIT_ALREADY_USED", "A candidate credit is already assigned in this seller's retained records.")
            elif len(exact) == 1:
                credit = exact[0]
                if credit.amount_paisa != amount:
                    decision("AMOUNT_CONFLICT", "The reference matches, but the statement amount differs.")
                elif abs((credit.posted_at-at).total_seconds()) > 86400:
                    decision("DATE_CONFLICT", "The same reference appears with a conflicting date.")
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
