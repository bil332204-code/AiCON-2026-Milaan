"""Exercise retry after a remote write commits but its response is lost."""
import importlib.util
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient

@pytest.mark.parametrize('failed_stage', ['orders', 'statement', 'claims', 'confirm', 'reconcile'])
def test_resume_does_not_duplicate_evidence(tmp_path, monkeypatch, failed_stage):
    monkeypatch.setenv('STORE_DB',str(tmp_path/'store.db'))
    spec=importlib.util.spec_from_file_location('demo_store',Path(__file__).resolve().parents[1]/'demo-store/server.py')
    store=importlib.util.module_from_spec(spec);spec.loader.exec_module(store)
    remote={'revision':1,'orders':[],'statements':[],'claims':[],'jobs':[]}
    counts={}; failed=False
    def call(session,method,path,**kwargs):
        nonlocal failed
        stage=None
        if path=='/api/batches':
            counts['batch']=counts.get('batch',0)+1
            return {'id':'batch-1','revision':remote['revision']}
        name=path.rsplit('/',1)[-1]
        if method=='GET':
            if name=='batch-1':return {'id':'batch-1','revision':remote['revision']}
            return {'items':remote[name]}
        if method=='PATCH':
            stage='confirm';remote['claims'][0]['fields_checked']=True
        elif name=='orders':
            stage=name;remote[name].append({'id':'order-1'})
        elif name=='statement':
            stage=name;remote['statements'].append({'id':'stmt-1'})
        elif name=='claims':
            stage=name;remote[name].append({'id':'claim-1','order_id':'order-1','version':1,'fields_checked':False})
        elif name=='reconcile':
            stage=name
            if not remote['jobs']:remote['jobs'].append({'id':'job-1'})
        else:raise AssertionError((method,path))
        counts[stage]=counts.get(stage,0)+1
        remote['revision']+=1
        if stage==failed_stage and not failed:
            failed=True
            raise httpx.ReadTimeout('response lost after remote write')
        if stage=='reconcile':return remote['jobs'][0]
        return {'batch':{'id':'batch-1','revision':remote['revision']},'items':remote['orders'],'claim':remote['claims'][0] if remote['claims'] else None}
    monkeypatch.setattr(store,'call',call)
    store.SESSIONS['test']={'owner':'owner-1','token':'test','email':'test@example.com','expires':float('inf')}
    with TestClient(store.app) as c:
        c.cookies.set('demo_session','test')
        r=c.post('/api/orders',json={'name':'Ali Khan','product':'mug'});assert r.status_code==201
        oid=r.json()['id']
        assert c.post(f'/api/orders/{oid}/sync',json={'mode':'fixture'}).status_code==502
        assert c.get('/api/orders').json()['items'][0]['sync_state']=='sync_failed'
        r=c.post(f'/api/orders/{oid}/sync',json={'mode':'fixture'})
        assert r.status_code==200,r.text
        assert r.json()['state']=='processing'
        assert counts['batch']==1
        assert all(len(remote[x])==1 for x in ['orders','statements','claims','jobs'])
        assert counts['orders']==counts['statement']==counts['claims']==1
        assert c.post(f'/api/orders/{oid}/sync',json={'mode':'fixture'}).status_code==200


def test_demo_statement_export_protects_synthetic_spreadsheet_cells(tmp_path, monkeypatch):
    """CSV from the separate demo store must preserve customer input as literal text."""
    import csv
    import io
    monkeypatch.setenv('STORE_DB', str(tmp_path / 'store.db'))
    spec = importlib.util.spec_from_file_location(
        'demo_store_export', Path(__file__).resolve().parents[1] / 'demo-store/server.py')
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    names = ['=1+1', '+SUM(1)', '-2+3', '@SUM(A1:A2)', '\t=5', '\r+5', '   =9', 'Synthetic Buyer']
    sample = store.csv_bytes(['counterparty'], [[name] for name in names])
    exported = list(csv.reader(io.StringIO(sample.decode('utf-8'))))
    assert [row[0] for row in exported[1:]] == [
        ("'" + name) if index < 7 else name for index, name in enumerate(names)]
    statement = store.bank_csv({'amount': 350000, 'reference': 'SYNTHETIC123',
        'bank_at': '2026-10-09T14:22:00+05:00', 'name': '=CMD(1)', 'scenario': 'matched'})
    rows = list(csv.DictReader(io.StringIO(statement.decode('utf-8'))))
    assert len(rows) == 1
    assert rows[0]['counterparty'] == "'=CMD(1)"
    assert rows[0]['amount'] == '3500.00'
