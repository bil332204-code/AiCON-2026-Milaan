from types import SimpleNamespace as NS
from app.parsing import parse_time
from app.matcher import compute_matches
from matching.names import name_similarity

def test_name_similarity_pakistani_variants():
    # Urdu transliteration and honorifics
    score1 = name_similarity("Muhammad Usman", "M. Usman").combined()
    assert score1 >= 0.85

    score2 = name_similarity("Syed Tariq Shah", "Tarik Shah").combined()
    assert score2 >= 0.70

    score3 = name_similarity("Fatima Zubair", "Fatima Zubair Siddiqui").combined()
    assert score3 >= 0.75

    # Completely different names
    score4 = name_similarity("Sara Khan", "Bilal Ahmed").combined()
    assert score4 < 0.40

def test_matcher_enriches_evidence_with_pakistani_name_similarity():
    at = parse_time('2026-10-09T14:00:00+05:00')
    order = NS(id='o-1', account_id='acct-1', customer_name="Muhammad Usman", amount_due_paisa=500000)
    claim = NS(id='c-1', order_id='o-1', account_id='acct-1', sha256='hash-test', fields_checked=True,
               fields={'is_payment_receipt': True, 'amount_pkr': '5000', 'datetime_local': '2026-10-09T14:00:00+05:00',
                       'transaction_id': 'TXN999999', 'status_text': 'Success'})
    stmt = NS(account_id='acct-1', references_verified=True, complete=True,
              coverage_start=parse_time('2026-10-09T08:00+05:00'), coverage_end=parse_time('2026-10-09T20:00+05:00'))
    line = NS(id='line-1', account_id='acct-1', direction='CREDIT', currency='PKR', amount_paisa=500000,
              posted_at=at, transaction_id='TXN999999', credit_key='k-1', counterparty='M. Usman')

    results = compute_matches([order], [claim], [stmt], [line], set())
    assert len(results) == 1
    r = results[0]
    assert r['reason_code'] == 'EXACT_MATCH'
    assert r['final_status'] == 'ship'

    # Check that pakistani_name_similarity is in evidence
    name_check = next((e for e in r['evidence'] if e['check'] == 'pakistani_name_similarity'), None)
    assert name_check is not None
    assert name_check['ok'] is True
    assert name_check['score'] >= 0.85
    assert name_check['matched_name'] == 'M. Usman'
    assert name_check['order_name'] == 'Muhammad Usman'
    assert 'signals' in name_check

def test_matcher_discovers_candidate_by_pakistani_name_within_24h():
    at = parse_time('2026-10-09T14:00:00+05:00')
    # Posted 3 hours later (180 minutes later, far beyond the 10 min window)
    posted_later = parse_time('2026-10-09T17:00:00+05:00')
    order = NS(id='o-2', account_id='acct-1', customer_name="Ayesha Ansari", amount_due_paisa=300000)
    claim = NS(id='c-2', order_id='o-2', account_id='acct-1', sha256='hash-test-2', fields_checked=True,
               fields={'is_payment_receipt': True, 'amount_pkr': '3000', 'datetime_local': '2026-10-09T14:00:00+05:00',
                       'transaction_id': 'PARTIAL', 'status_text': 'Success'})
    stmt = NS(account_id='acct-1', references_verified=True, complete=True,
              coverage_start=parse_time('2026-10-09T08:00+05:00'), coverage_end=parse_time('2026-10-09T20:00+05:00'))
    line = NS(id='line-delayed', account_id='acct-1', direction='CREDIT', currency='PKR', amount_paisa=300000,
              posted_at=posted_later, transaction_id='BANKREF777', credit_key='k-delayed', counterparty='Ayesha Ansari')

    results = compute_matches([order], [claim], [stmt], [line], set())
    r = results[0]
    # Discovered as candidate via Pakistani name similarity
    assert 'line-delayed' in r['candidate_ids']
    assert r['reason_code'] == 'POSSIBLE_MATCH'
    name_check = next((e for e in r['evidence'] if e['check'] == 'pakistani_name_similarity'), None)
    assert name_check is not None
    assert name_check['ok'] is True
    assert name_check['score'] >= 0.95
