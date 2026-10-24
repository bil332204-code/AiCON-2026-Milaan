"""Private provenance metadata must not bypass import, revision or ownership checks."""
import hashlib
import json
from conftest import fresh_batch, register

CSV = 'order_ref,customer_name,amount_due,account_id\nSYNTHETIC-1,Ali Synthetic,100,wallet'


def test_provenance_is_private_and_import_is_atomic(env, auth):
    client, _, _ = env
    batch = fresh_batch(client, auth)
    url = f'/api/batches/{batch["id"]}/orders'
    provenance = {'source_sha256': 'a'*64, 'mapping': {'order_ref': 'Order ID'}, 'timezone': '+05:00'}
    invalid = client.post(url, headers=auth, files={'file': ('orders.csv', CSV+'\nBAD,Ali,NaN,wallet')},
                          data={'expected_revision': batch['revision'], 'provenance': json.dumps(provenance)})
    assert invalid.status_code == 422
    assert client.get(url, headers=auth).json()['items'] == []
    response = client.post(url, headers=auth, files={'file': ('orders.csv', CSV)},
                           data={'expected_revision': batch['revision'], 'provenance': json.dumps(provenance)})
    assert response.status_code == 201, response.text
    events = client.get(f'/api/batches/{batch["id"]}/audit', headers=auth).json()['items']
    detail = next(e['detail'] for e in events if e['action'] == 'orders_imported')
    assert detail['count'] == 1 and detail['rejected'] == 0
    assert detail['provenance']['client_declared_source'] == provenance
    assert detail['provenance']['stored_csv_sha256'] == hashlib.sha256(CSV.encode()).hexdigest()
    other = register(client, 'other-importer@example.com')
    assert client.get(f'/api/batches/{batch["id"]}/audit', headers=other).status_code == 404


def test_invalid_provenance_never_saves_records(env, auth):
    client, _, _ = env
    batch = fresh_batch(client, auth)
    url = f'/api/batches/{batch["id"]}/orders'
    for metadata in ['not json', '{"source_sha256":"not-a-hash"}', json.dumps({'source_sha256':'a'*64,'mapping':{'secret':'value'}})]:
        response = client.post(url, headers=auth, files={'file': ('orders.csv', CSV)},
                               data={'expected_revision': batch['revision'], 'provenance': metadata})
        assert response.status_code == 422
        assert client.get(url, headers=auth).json()['items'] == []
