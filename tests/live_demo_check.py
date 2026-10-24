"""Isolated live HTTP test. Uses temporary databases; never uses your .env credentials."""
import os,sys,tempfile,subprocess,time,socket
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]
def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def wait(url):
    for _ in range(100):
        try:
            if httpx.get(url,trust_env=False).status_code==200:return
        except httpx.HTTPError:pass
        time.sleep(.1)
    raise RuntimeError('Server did not start: '+url)
with tempfile.TemporaryDirectory() as tmp:
    p1,p2=port(),port();m=f'http://127.0.0.1:{p1}';store=f'http://127.0.0.1:{p2}'
    env={**os.environ,'DATABASE_URL':f'sqlite:///{tmp}/milaan.db','STORAGE_DIR':tmp+'/uploads','STORE_DB':tmp+'/store.db','MILAAN_URL':m,'DEMO_SELLER_EMAIL':'operator@example.com','DEMO_SELLER_PASSWORD':'demo-integration-test-pass','REQUIRE_EMAIL_VERIFICATION':'false','EXTRACTION_PROVIDER':'manual','GEMINI_API_KEY':'','RUN_WORKER_IN_API':'true'}
    backend=ROOT/'milaan/backend'
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=backend,env=env,check=True)
    processes=[]
    try:
        for module,cwd,p in [('app.main:app',backend,p1),('server:app',ROOT/'demo-store',p2)]:
            processes.append(subprocess.Popen([sys.executable,'-m','uvicorn',module,'--host','127.0.0.1','--port',str(p),'--log-level','error'],cwd=cwd,env=env))
        wait(m+'/api/health');wait(store+'/api/status')
        with httpx.Client(base_url=store,trust_env=False,timeout=40) as c:
            r=c.post('/api/connect',json={'email':env['DEMO_SELLER_EMAIL'],'password':env['DEMO_SELLER_PASSWORD']});assert r.status_code==200,r.text
            for scenario,expected in [('matched','ship'),('missing','hold'),('wrong_amount','review'),('duplicate','review'),('name','review')]:
                r=c.post('/api/orders',json={'name':'Ali Khan','product':'mug','scenario':scenario});assert r.status_code==201,r.text
                oid=r.json()['id']
                assert c.get(f'/api/orders/{oid}/receipt.jpg').headers['content-type']=='image/jpeg'
                r=c.post(f'/api/orders/{oid}/sync',json={'mode':'fixture'});assert r.status_code==200,r.text
                for _ in range(60):
                    r=c.get(f'/api/orders/{oid}/results');assert r.status_code==200,r.text
                    items=r.json()['items']
                    if items:break
                    time.sleep(.2)
                assert items,r.text
                assert all(x['final_status']==expected for x in items),items
                if scenario=='name':assert 'pakistani_name_similarity' in str(items),items
                if scenario=='duplicate':assert len(items)==2,items
                print(scenario,[(x['final_status'],x['reason_code']) for x in items],flush=True)
            r=c.post('/api/orders',json={'name':'Receipt Test','product':'bag'});oid=r.json()['id']
            r=c.post(f'/api/orders/{oid}/sync',json={'mode':'receipt'});assert r.status_code==200,r.text
            assert r.json()['state']=='awaiting_receipt_read'
            assert c.get(f'/api/orders/{oid}/results').json()['items']==[]
            # Complete real HTTP receipt mode with a human-confirmed reading, without an AI key.
            bid=r.json()['batch_id']
            login=httpx.post(m+'/api/auth/login',json={'email':env['DEMO_SELLER_EMAIL'],'password':env['DEMO_SELLER_PASSWORD']},trust_env=False)
            headers={'Authorization':'Bearer '+login.json()['access_token']}
            claim=httpx.get(m+f'/api/batches/{bid}/claims',headers=headers,trust_env=False).json()['items'][0]
            order=next(x for x in c.get('/api/orders').json()['items'] if x['id']==oid)
            fields={'is_payment_receipt':True,'amount_pkr':f"{order['receipt_amount']/100:.2f}",'datetime_local':order['paid_at'],'transaction_id':order['receipt_reference'],'status_text':'Successful','sender_name':order['name']}
            checked=httpx.patch(m+f"/api/claims/{claim['id']}",headers=headers,json={'expected_version':claim['version'],'confirmed':True,'fields':fields},trust_env=False)
            assert checked.status_code==200,checked.text
            job=httpx.post(m+f'/api/batches/{bid}/reconcile',headers={**headers,'Idempotency-Key':'manual-receipt-demo'},trust_env=False)
            assert job.status_code==202,job.text
            for _ in range(60):
                items=c.get(f'/api/orders/{oid}/results').json()['items']
                if items:break
                time.sleep(.2)
            assert items and items[0]['final_status']=='ship',items
            # Persist a human override and verify exported data through actual HTTP.
            match=items[0]
            review=httpx.post(m+f"/api/matches/{match['id']}/decision",headers=headers,
                json={'expected_version':match['version'],'decision':'hold','reason':'Synthetic operator requests another check'},trust_env=False)
            assert review.status_code==200,review.text
            exported=httpx.get(m+f'/api/batches/{bid}/export.csv',headers=headers,trust_env=False)
            assert exported.status_code==200 and 'Synthetic operator requests another check' in exported.text
            assert httpx.get(m+f'/api/batches/{bid}/export.csv',trust_env=False).status_code==401
            print('Receipt mode: human-confirmed fields -> SHIP -> saved human HOLD -> private CSV export.',flush=True)
            assert httpx.get(store+f'/api/orders/{oid}/receipt.jpg',trust_env=False).status_code==401
            assert httpx.get(m+'/',trust_env=False).status_code==200
            print('Receipt mode waits for reading; private receipt requires login; Milaan frontend served.',flush=True)
    finally:
        for p in processes:p.terminate()
        for p in processes:p.wait(timeout=10)
