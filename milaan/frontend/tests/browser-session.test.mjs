import test from 'node:test';
import assert from 'node:assert/strict';
import {MilaanAPI} from '../dist/milaan-api.js';
test('cookie sessions keep only CSRF in memory and attach it to unsafe requests',async t=>{
 const original=globalThis.fetch;t.after(()=>{globalThis.fetch=original;});const requests=[];
 globalThis.fetch=async(url,options)=>{requests.push(options);return new Response(JSON.stringify({user:{id:'synthetic'},csrf_token:'synthetic-csrf',expires_at:'2099-01-01T00:00:00Z'}),{status:200});};
 const api=new MilaanAPI('http://example.test');await api.login('synthetic@example.com','synthetic-password',true);
 assert.equal(api.token,null);assert.equal(api.authenticated,true);assert.equal(JSON.parse(requests[0].body).session_mode,'cookie');assert.equal(JSON.parse(requests[0].body).remember_me,true);
 await api.request('/api/batches',{method:'POST',body:{name:'Synthetic'}});assert.equal(requests[1].headers['X-CSRF-Token'],'synthetic-csrf');assert.equal(requests[1].credentials,'include');
 await api.request('/api/batches');assert.equal(requests[2].headers['X-CSRF-Token'],undefined);api.clearSession();
});
test('an expired or rejected session immediately clears private authentication state',async t=>{
 const original=globalThis.fetch;t.after(()=>{globalThis.fetch=original;});globalThis.fetch=async()=>new Response(JSON.stringify({detail:'Session expired'}),{status:401});
 const api=new MilaanAPI();let cleared=0;api.onUnauthorized=()=>cleared++;api.adopt({csrf_token:'synthetic',expires_at:'2099-01-01T00:00:00Z'});
 await assert.rejects(()=>api.request('/api/batches'));assert.equal(api.authenticated,false);assert.equal(api.csrf,null);assert.equal(cleared,1);
});
test('absolute session expiry fires without another user action',async()=>{
 const api=new MilaanAPI();let resolve;const expired=new Promise(r=>resolve=r);api.onUnauthorized=resolve;
 api.adopt({csrf_token:'synthetic',expires_at:new Date(Date.now()+20).toISOString()});
 await Promise.race([expired,new Promise((_,reject)=>setTimeout(()=>reject(Error('Expiry timer did not fire')),200))]);assert.equal(api.authenticated,false);api.clearSession();
});
test('explicit remote API mode preserves temporary bearer integration',async t=>{
 const original=globalThis.fetch;t.after(()=>{globalThis.fetch=original;});let payload;
 globalThis.fetch=async(url,options)=>{payload=JSON.parse(options.body);return new Response(JSON.stringify({access_token:'synthetic-native-token',expires_at:'2099-01-01T00:00:00Z'}),{status:200});};
 const api=new MilaanAPI('https://remote.example');api.sessionMode='bearer';await api.login('synthetic@example.com','synthetic-password');assert.equal(payload.session_mode,'bearer');assert.equal(api.cookieSession,false);assert.equal(api.token,'synthetic-native-token');api.clearSession();
});
