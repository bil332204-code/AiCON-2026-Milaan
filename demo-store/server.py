"""Separate local demonstration store; communicates with Milaan through its public API only."""
import os,secrets,sqlite3,json,io,csv,time,threading
from pathlib import Path
from datetime import datetime,timedelta,timezone
import httpx
from PIL import Image,ImageDraw,ImageFont
from fastapi import FastAPI,HTTPException,Request,Response,Depends
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field

ROOT=Path(__file__).parent
MILAAN=os.getenv('MILAAN_URL','http://127.0.0.1:8000').rstrip('/')
DB=Path(os.getenv('STORE_DB',str(ROOT/'data'/'store.db')));DB.parent.mkdir(parents=True,exist_ok=True)
SESSIONS={};LOCK=threading.Lock()
PRODUCTS=[{'id':'mug','name':'Studio mug','price':150000},{'id':'notebook','name':'Everyday notebook','price':85000},{'id':'bag','name':'Canvas tote','price':250000}]
app=FastAPI(title='Separate demo store — simulated payments')
with sqlite3.connect(DB) as db:db.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY,owner TEXT NOT NULL,payload TEXT NOT NULL)')

class Connect(BaseModel):email:str;password:str
class Checkout(BaseModel):
    name:str=Field(min_length=2,max_length=100)
    product:str
    quantity:int=Field(ge=1,le=10,default=1)
    scenario:str='matched'
class Sync(BaseModel):mode:str='fixture'

def session(request:Request):
    sid=request.cookies.get('demo_session');s=SESSIONS.get(sid)
    if not s or s['expires']<time.time():raise HTTPException(401,'Connect your Milaan seller account first')
    return s

def call(s,method,path,**kwargs):
    try:
        with httpx.Client(timeout=40,trust_env=False) as client:
            r=client.request(method,MILAAN+path,headers={'Authorization':'Bearer '+s['token'],**kwargs.pop('headers',{})},**kwargs)
    except httpx.HTTPError:
        raise HTTPException(502, 'Milaan is not reachable. Start the checker, then retry.') from None
    if r.status_code>=400:
        try:detail=r.json().get('detail','Request failed')
        except ValueError:detail='Backend error'
        raise HTTPException(r.status_code if r.status_code<500 else 502,detail)
    return r.json() if r.content else None

def saved(o):
    with sqlite3.connect(DB) as db:db.execute('INSERT OR REPLACE INTO orders VALUES (?,?,?)',(o['id'],o['owner'],json.dumps(o)))
def owned(id,s):
    with sqlite3.connect(DB) as db:row=db.execute('SELECT payload FROM orders WHERE id=? AND owner=?',(id,s['owner'])).fetchone()
    if not row:raise HTTPException(404,'Order not found')
    return json.loads(row[0])
def csv_bytes(headers,rows):
    f=io.StringIO();w=csv.writer(f);w.writerow(headers);w.writerows(rows);return f.getvalue().encode()
def receipt(o):
    im=Image.new('RGB',(850,620),'#f7faf4');d=ImageDraw.Draw(im)
    try:font=ImageFont.truetype('DejaVuSans.ttf',23);title=ImageFont.truetype('DejaVuSans.ttf',32)
    except OSError:font=ImageFont.load_default(size=23);title=font
    d.text((35,28),'DEMO — NOT A REAL PAYMENT',fill='#ad3232',font=title)
    lines=['SIMULATED PAYMENT RECEIPT','Status: Successful',f"Sender: {o['name']}",f"Amount: PKR {o['receipt_amount']/100:.2f}",f"Reference: {o['receipt_reference']}",f"Date: {o['paid_at']}",f"Order: {o['id']}",'Receiver: demo-store-main','Generated for Milaan integration testing only.']
    for i,line in enumerate(lines):d.text((35,100+i*49),line,fill='#173c33',font=font)
    f=io.BytesIO();im.save(f,'JPEG',quality=92);return f.getvalue()
def bank_csv(o):
    # Bank simulator state is independent of the receipt claim.
    amount=o['amount'];ref=o['reference'];at=o['bank_at'];name=o['name']
    if o['scenario']=='missing':amount+=77700;ref='UNRELATED-'+o['id'];name='Unrelated sender'
    if o['scenario']=='name':name='Muhammad Ahmed'
    return csv_bytes(['posted_at','direction','amount','counterparty','transaction_id'],[[at,'CREDIT',f'{amount/100:.2f}',name,ref]])

@app.get('/api/status')
def status(request:Request):
    try:s=session(request);return {'connected':True,'email':s['email'],'milaan_url':MILAAN}
    except HTTPException:return {'connected':False,'milaan_url':MILAAN}
@app.post('/api/connect')
def connect(body:Connect,response:Response):
    try:
        with httpx.Client(timeout=20,trust_env=False) as client:r=client.post(MILAAN+'/api/auth/login',json=body.model_dump())
    except httpx.HTTPError:raise HTTPException(502,'Milaan is not reachable. Start Milaan first.')
    if r.status_code!=200:raise HTTPException(401,'Milaan login failed. Check your seller email and password.')
    info=r.json();sid=secrets.token_urlsafe(32);SESSIONS[sid]={'token':info['access_token'],'owner':info['user']['id'],'email':info['user']['email'],'expires':time.time()+12*3600}
    response.set_cookie('demo_session',sid,httponly=True,samesite='strict',max_age=43200)
    return {'connected':True,'email':info['user']['email']}
@app.post('/api/disconnect')
def disconnect(request:Request,response:Response):
    s=SESSIONS.pop(request.cookies.get('demo_session'),None)
    if s:
        try:call(s,'POST','/api/auth/logout')
        except (HTTPException,httpx.HTTPError):pass
    response.delete_cookie('demo_session');return {'connected':False}
@app.get('/api/products')
def products():return {'items':PRODUCTS}
@app.get('/api/orders')
def orders(s=Depends(session)):
    with sqlite3.connect(DB) as db:rows=db.execute('SELECT payload FROM orders WHERE owner=? ORDER BY rowid DESC',(s['owner'],)).fetchall()
    return {'items':[json.loads(r[0]) for r in rows]}
@app.post('/api/orders',status_code=201)
def checkout(body:Checkout,s=Depends(session)):
    if body.scenario not in {'matched','missing','wrong_amount','duplicate','name'}:raise HTTPException(422,'Unknown demo scenario')
    p=next((x for x in PRODUCTS if x['id']==body.product),None)
    if not p:raise HTTPException(422,'Unknown product')
    id='DEMO-'+secrets.token_hex(5).upper();at=datetime.now(timezone.utc).replace(microsecond=0)-timedelta(hours=2)
    amount=p['price']*body.quantity;ref='BANK-'+secrets.token_hex(7).upper()
    o={'id':id,'owner':s['owner'],'name':'M Ahmed' if body.scenario=='name' else body.name,'product':p['name'],'quantity':body.quantity,'amount':amount,'receipt_amount':amount+10000 if body.scenario=='wrong_amount' else amount,'reference':ref,'receipt_reference':'****1234' if body.scenario=='name' else ref,'paid_at':at.isoformat(),'bank_at':(at+timedelta(minutes=60 if body.scenario=='name' else 2)).isoformat(),'coverage_start':(at-timedelta(hours=3)).isoformat(),'coverage_end':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'scenario':body.scenario,'batch_id':None,'sync_state':'ready'}
    saved(o);return o
@app.get('/api/orders/{id}/receipt.jpg')
def receipt_download(id:str,s=Depends(session)):return Response(receipt(owned(id,s)),media_type='image/jpeg',headers={'Content-Disposition':'attachment; filename="DEMO-receipt.jpg"'})
@app.get('/api/orders/{id}/statement.csv')
def statement_download(id:str,s=Depends(session)):return Response(bank_csv(owned(id,s)),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="DEMO-statement.csv"'})
@app.get('/api/orders/{id}/results')
def results(id:str,s=Depends(session)):
    o=owned(id,s)
    if not o['batch_id']:raise HTTPException(409,'Send this order to Milaan first')
    return call(s,'GET',f"/api/batches/{o['batch_id']}/results")
@app.post('/api/orders/{id}/sync')
def sync(id:str,body:Sync,s=Depends(session)):
    if body.mode not in {'fixture','receipt'}:raise HTTPException(422,'Select fixture or receipt mode')
    if not LOCK.acquire(blocking=False):raise HTTPException(409,'A sync is running. Wait for it to finish.')
    o=None
    try:
        o=owned(id,s)
        if o['batch_id'] and o['sync_state'] not in {'uploading','sync_failed'}:
            return {'batch_id':o['batch_id'],'state':o['sync_state'],'message':'Already sent. Open this batch in Milaan.'}
        if o.get('mode') and o['mode'] != body.mode:
            raise HTTPException(409, 'Resume using the original sync mode.')
        if o['batch_id']:
            b=call(s,'GET',f"/api/batches/{o['batch_id']}")
        else:
            b=call(s,'POST','/api/batches',json={'name':f"DEMO STORE · {o['id']} · {o['scenario']}"})
        o.update(batch_id=b['id'],sync_state='uploading',mode=body.mode,sync_error=None);saved(o)
        bid=b['id'];count=2 if o['scenario']=='duplicate' else 1
        order_rows=[[o['id']+('-B' if i else ''),o['name'],f"{o['amount']/100:.2f}",'demo-store-main'] for i in range(count)]
        remote_orders=call(s,'GET',f'/api/batches/{bid}/orders')['items']
        if not remote_orders:
            data=call(s,'POST',f'/api/batches/{bid}/orders',data={'expected_revision':b['revision']},files={'file':('orders.csv',csv_bytes(['order_ref','customer_name','amount_due','account_id'],order_rows),'text/csv')});b=data['batch'];remote_orders=data['items']
        if not call(s,'GET',f'/api/batches/{bid}/statements')['items']:
            data=call(s,'POST',f'/api/batches/{bid}/statement',data={'expected_revision':b['revision'],'account_id':'demo-store-main','coverage_start':o['coverage_start'],'coverage_end':o['coverage_end'],'complete':'true','references_verified':'true'},files={'file':('DEMO-statement.csv',bank_csv(o),'text/csv')});b=data['batch']
        existing_claims=call(s,'GET',f'/api/batches/{bid}/claims')['items']
        for remote in remote_orders:
            linked=[c for c in existing_claims if c['order_id']==remote['id']]
            if len(linked)>1:raise HTTPException(409,'Multiple receipts exist. Review the saved batch in Milaan.')
            if linked:claim=linked[0]
            else:
                data=call(s,'POST',f'/api/batches/{bid}/claims',data={'expected_revision':b['revision'],'order_id':remote['id']},files={'file':('DEMO-receipt.jpg',receipt(o),'image/jpeg')});b=data['batch'];claim=data['claim']
            if body.mode=='fixture' and not claim['fields_checked']:
                data=call(s,'PATCH',f"/api/claims/{claim['id']}",json={'expected_version':claim['version'],'confirmed':True,'fields':{'is_payment_receipt':True,'amount_pkr':f"{o['receipt_amount']/100:.2f}",'datetime_local':o['paid_at'],'transaction_id':o['receipt_reference'],'status_text':'Successful','sender_name':o['name']}});b=data['batch']
        if body.mode=='fixture':
            job=call(s,'POST',f'/api/batches/{bid}/reconcile',headers={'Idempotency-Key':'store-'+o['id']})
            o['sync_state']='processing';o['job_id']=job['id']
        else:o['sync_state']='awaiting_receipt_read'
        o['mode']=body.mode;saved(o)
        return {'batch_id':bid,'state':o['sync_state'],'message':'Open Saved batches in Milaan. Fixture mode supplies known test fields; Receipt mode requires AI/manual reading.'}
    except (HTTPException,httpx.HTTPError) as exc:
        if o is not None:
            o['sync_state']='sync_failed';o['sync_error']='Sync interrupted. Resume with the same mode; uploaded evidence is retained.';saved(o)
        if isinstance(exc,HTTPException):raise
        raise HTTPException(502,'Connection to Milaan failed. Retry sync to resume.') from None
    finally:LOCK.release()
app.mount('/',StaticFiles(directory=ROOT/'static',html=True),name='demo-store')
