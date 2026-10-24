"""Normalized import contract; all records are synthetic."""
import pytest
from app.parsing import csv_rows, parse_statement, parse_orders
HEADER = 'posted_at,direction,amount,counterparty,transaction_id'
ROW = '2026-10-09T14:00,CREDIT,100,"Ali, Khan",REF12345'

def test_bom_quotes_and_declared_account():
    line = parse_statement(('\ufeff'+HEADER+'\r\n'+ROW).encode(), 'seller', 'wallet')[0]
    assert line['counterparty'] == 'Ali, Khan'
    assert line['account_id'] == 'wallet'
    assert line['amount_paisa'] == 10000

@pytest.mark.parametrize('raw', [
    HEADER+'\n'+ROW+'\n'+ROW,
    HEADER+'\n'+ROW.replace('CREDIT', 'UNKNOWN'),
    HEADER+'\n'+ROW.replace(',100,', ',NaN,'),
    HEADER+'\n'+ROW.replace('2026-10-09T14:00', '2026-02-30T14:00'),
    HEADER+'\n'+ROW.replace('2026-10-09T14:00', '14:00'),
    HEADER+',currency\n'+ROW+',USD',
    HEADER+',account_id\n'+ROW+',other-wallet',
    'posted_at,amount\n2026-10-09T14:00,100',
])
def test_invalid_statement_rejected(raw):
    with pytest.raises(ValueError): parse_statement(raw.encode(), 'seller', 'wallet')

def test_blank_reference_is_retained_without_invention():
    line = parse_statement((HEADER+'\n'+ROW.replace('REF12345', '')).encode(), 'seller', 'wallet')[0]
    assert line['transaction_id'] == ''

def test_limits_and_encoding():
    for raw in [b'a\n'+b'x'*2_000_000, b'a\n'+b'x\n'*2001, b'a\n\xff']:
        with pytest.raises(ValueError): csv_rows(raw)

def test_orders_duplicate_and_missing_headers():
    for raw in [b'order_ref\nx', b'order_ref,customer_name,amount_due,account_id\nx,Ali,100,a\nx,Ali,100,a']:
        with pytest.raises(ValueError): parse_orders(raw)
