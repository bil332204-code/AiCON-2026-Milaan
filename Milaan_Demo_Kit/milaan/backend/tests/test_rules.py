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
