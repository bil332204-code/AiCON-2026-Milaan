from types import SimpleNamespace as NS
import pytest
from app.parsing import paisa, parse_time, csv_rows, full_ref
from app.matcher import compute_matches

@pytest.mark.parametrize('value', ['-1', '0', 'NaN', '1.001', '1,23', '1e6', '', None])
def test_invalid_money(value):
    with pytest.raises(ValueError): paisa(value)

def test_exact_money_and_timezone():
    assert paisa('1,234.56') == 123456
    assert parse_time('2026-10-09T14:22') == parse_time('2026-10-09T09:22:00Z')
    assert not full_ref('XX1234') and not full_ref('123...') and full_ref('AB123456')
    with pytest.raises(ValueError): csv_rows(b'a,b\n"unterminated')

def fixtures():
    at = parse_time('2026-10-09T14:00:00+05:00')
    order = NS(id='o', account_id='a', amount_due_paisa=10000)
    claim = NS(id='c', order_id='o', account_id='a', sha256='hash1', fields_checked=True,
               fields={'is_payment_receipt':True, 'amount_pkr':'100', 'datetime_local':'2026-10-09T14:00:00+05:00', 'transaction_id':'TX123456', 'status_text':'Success'})
    stmt = NS(account_id='a', references_verified=True, complete=True, coverage_start=parse_time('2026-10-09T08:00+05:00'), coverage_end=parse_time('2026-10-09T20:00+05:00'))
    line = NS(id='l', account_id='a', direction='CREDIT', currency='PKR', amount_paisa=10000, posted_at=at, transaction_id='TX123456', credit_key='k')
    return order, claim, stmt, line

@pytest.mark.parametrize('change,expected', [('unchecked','UNREADABLE'),('pending','STATUS_CONFLICT'),('amount','AMOUNT_CONFLICT'),('coverage','COVERAGE'),('reference','VERIFY_REFERENCE'),('debit','NOT_FOUND'),('used','CREDIT_ALREADY_USED')])
def test_conservative_rules(change, expected):
    o,c,s,l = fixtures(); used=set()
    if change=='unchecked': c.fields_checked=False
    if change=='pending': c.fields['status_text']='Pending'
    if change=='amount': c.fields['amount_pkr']='90'
    if change=='coverage': s.complete=False
    if change=='reference': s.references_verified=False
    if change=='debit': l.direction='DEBIT'
    if change=='used': used={'k'}
    result = compute_matches([o],[c],[s],[l],used)[0]
    assert result['reason_code']==expected and result['final_status']!='ship'

def test_duplicate_proof_and_statement_credit():
    o,c,s,l = fixtures()
    l2 = NS(**{**vars(l), 'id':'l2'})
    assert compute_matches([o],[c],[s],[l,l2],set())[0]['reason_code']=='DUPLICATE_CREDIT'
    o2 = NS(**{**vars(o), 'id':'o2'}); c2 = NS(**{**vars(c), 'id':'c2','order_id':'o2'})
    assert all(x['reason_code']=='REUSED_PROOF' for x in compute_matches([o,o2],[c,c2],[s],[l],set()))

@pytest.mark.parametrize('status', [None, '', 'Unknown', 'Processing', 'Not successful', 'Failed'])
def test_missing_or_ambiguous_status_cannot_ship(status):
    o,c,s,l=fixtures()
    c.fields['status_text']=status
    result=compute_matches([o],[c],[s],[l],set())[0]
    assert result['final_status']=='review'
    assert result['reason_code']=='STATUS_CONFLICT'


def test_refund_debit_or_reversed_status_prevents_automatic_ship():
    o,c,s,l=fixtures()
    debit=NS(**{**vars(l),'id':'refund','direction':'DEBIT'})
    result=compute_matches([o],[c],[s],[l,debit],set())[0]
    assert result['reason_code']=='REVERSAL' and result['final_status']=='review'
    c.fields['status_text']='Payment reversed'
    assert compute_matches([o],[c],[s],[l],set())[0]['reason_code']=='REVERSAL'


def test_delayed_posting_is_a_conflict_not_automatic_settlement():
    from datetime import timedelta
    o,c,s,l=fixtures();l.posted_at+=timedelta(hours=25)
    result=compute_matches([o],[c],[s],[l],set())[0]
    assert result['reason_code']=='DATE_CONFLICT' and result['final_status']=='review'
    assert 'delayed' in result['reason']


def test_whitespace_cannot_promote_a_short_reference_to_full_evidence():
    assert not full_ref('A B C')
    # Strengthening matching must not change retained financial source identities.
    import hashlib, json
    from app.parsing import credit_identity
    expected=hashlib.sha256(json.dumps(['owner','wallet','ABC'],ensure_ascii=False).encode()).hexdigest()
    assert credit_identity('owner','wallet','A B C',parse_time('2026-10-09T14:00'),10000,'Synthetic')==expected
    o,c,s,l=fixtures();c.fields['transaction_id']='A B C';l.transaction_id='ABC'
    assert compute_matches([o],[c],[s],[l],set())[0]['final_status']=='review'


@pytest.mark.parametrize('missing', [None, '', 'A B C', 'XX1234'])
def test_missing_or_partial_reference_never_automatically_ships(missing):
    order, claim, statement, credit = fixtures()
    claim.fields['transaction_id'] = missing
    possible = compute_matches([order], [claim], [statement], [credit], set())[0]
    assert possible['final_status'] == 'review'
    assert possible['reason_code'] == 'POSSIBLE_MATCH'
    no_credit = compute_matches([order], [claim], [statement], [], set())[0]
    assert no_credit['final_status'] == 'review'
    assert no_credit['reason_code'] == 'PARTIAL_REFERENCE'


def test_full_reference_statement_amount_mismatch_stays_review():
    order, claim, statement, credit = fixtures()
    credit.amount_paisa = 9900
    result = compute_matches([order], [claim], [statement], [credit], set())[0]
    assert (result['final_status'], result['reason_code']) == ('review', 'AMOUNT_CONFLICT')


def test_same_full_reference_on_two_orders_blocks_both_even_with_distinct_images():
    order, claim, statement, credit = fixtures()
    second_order = NS(**{**vars(order), 'id': 'o2'})
    second_claim = NS(**{**vars(claim), 'id': 'c2', 'order_id': 'o2', 'sha256': 'different-image'})
    result = compute_matches([order, second_order], [claim, second_claim], [statement], [credit], set())
    assert [(r['final_status'],r['reason_code']) for r in result] == [
        ('review', 'REUSED_PROOF'), ('review', 'REUSED_PROOF')]


def test_full_reference_amount_only_ships_with_all_safety_checks():
    order, claim, statement, credit = fixtures()
    result = compute_matches([order], [claim], [statement], [credit], set())[0]
    assert (result['final_status'], result['reason_code']) == ('ship', 'EXACT_MATCH')
    claim.fields_checked = False
    assert compute_matches([order], [claim], [statement], [credit], set())[0]['final_status'] == 'review'
