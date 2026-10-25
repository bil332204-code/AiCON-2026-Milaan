"""Local ephemeral container check. No public ports, real users, email or deployments."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import uuid

IMAGE=os.getenv('MILAAN_SMOKE_IMAGE','milaan-v3-review:local')
name='milaan-v3-smoke-'+uuid.uuid4().hex[:10]
volume=name+'-data'

def docker(*args,check=True,input=None):
    return subprocess.run(['docker',*args],input=input,text=True,capture_output=True,check=check)

def wait_ready():
    for _ in range(40):
        result=docker('exec',name,'python','-c',"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')",check=False)
        if result.returncode==0:return
        time.sleep(.25)
    raise RuntimeError('Container did not become ready')

CREATE='''
import json,sys,httpx,os
p=json.load(sys.stdin)
assert os.getuid()!=0
with httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False) as c:
    assert c.get('/workspace',follow_redirects=False).status_code==303
    assert 'cinematic.css' in c.get('/').text
    assert c.get('/cinematic.css').status_code==200
    r=c.post('/api/auth/register',json={'email':'container@example.com','password':p['password'],'display_name':'Synthetic container user'});assert r.status_code==201
    r=c.post('/api/auth/login',json={'email':'container@example.com','password':p['password'],'session_mode':'cookie','remember_me':True});assert r.status_code==200
    assert 'access_token' not in r.json() and 'HttpOnly' in r.headers['set-cookie']
    csrf=r.json()['csrf_token']
    assert c.post('/api/batches',json={'name':'Rejected CSRF request'}).status_code==403
    r=c.post('/api/batches',headers={'X-CSRF-Token':csrf},json={'name':'Synthetic persistent container batch'});assert r.status_code==201
    print(json.dumps({'batch_id':r.json()['id'],'cookie':c.cookies.get('milaan_session')}))
'''
RESTORE='''
import json,sys,httpx
p=json.load(sys.stdin)
with httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False) as c:
    c.cookies.set('milaan_session',p['cookie'])
    r=c.get('/api/auth/session');assert r.status_code==200
    assert c.get('/api/batches/'+p['batch_id']).status_code==200
    assert c.post('/api/auth/logout',headers={'X-CSRF-Token':r.json()['csrf_token']}).status_code==204
    assert c.get('/api/batches/'+p['batch_id']).status_code==401
'''
try:
    docker('volume','create',volume)
    docker('run','--detach','--name',name,'--volume',volume+':/app/data',
           '-e','APP_ENV=development','-e','REQUIRE_EMAIL_VERIFICATION=false',
           '-e','RUN_WORKER_IN_API=false',IMAGE)
    wait_ready()
    first=docker('exec','-i',name,'python','-c',CREATE,input=json.dumps({'password':secrets.token_urlsafe(24)}))
    # Credentials remain only in this process's memory and pipe; never print them.
    state=json.loads(first.stdout)
    docker('restart',name);wait_ready()
    docker('exec','-i',name,'python','-c',RESTORE,input=json.dumps(state))
    print('Container checks passed: non-root app, cinematic assets, CSRF, persistent data/session after restart, logout revocation.')
finally:
    docker('rm','--force',name,check=False)
    docker('volume','rm',volume,check=False)
