import test from 'node:test';
import assert from 'node:assert/strict';
import {mapRemote,localTime} from '../dist/remote-state.js';
import {validateBackendURL} from '../dist/backend-ui.js';
test('backend configuration prevents accidental HTTP use on the hosted HTTPS page',()=>{
  assert.equal(validateBackendURL('http://127.0.0.1:8000','http:'),'http://127.0.0.1:8000');
  assert.throws(()=>validateBackendURL('http://127.0.0.1:8000','https:'));
  assert.throws(()=>validateBackendURL('https://user:secret@example.com','https:'));
  assert.throws(()=>validateBackendURL('https://example.com/api','https:'));
});
test('Pakistan input timestamps stay stable and invalid AI dates remain editable',()=>{
  assert.equal(localTime('2026-10-09T09:22:00Z'),'2026-10-09T14:22');
  assert.equal(localTime('2026-10-09T14:22'),'2026-10-09T14:22');
  assert.equal(localTime('date unreadable'),'');
});
test('server order identity and allocation availability survive the dashboard mapping',()=>{
  const orders=[{id:'o1',order_ref:'#1',customer_name:'A',amount_due_paisa:100,account_id:'wallet'}, {id:'o2',order_ref:'1',customer_name:'B',amount_due_paisa:100,account_id:'wallet'}];
  const row={order_id:'o1',claim_id:null,order:orders[0],final_status:'review',machine_verdict:'review',reason_code:'CREDIT_ALREADY_USED',reason:'Used credit',id:'m1',version:2,evidence:[],candidates:[{id:'l1',amount_paisa:100,available:false}]};
  const state=mapRemote({id:'batch'},orders,[],[],[],[row],[]);
  assert.equal(state.orders[0].id,'#1');assert.equal(state.orders[1].id,'1');
  assert.equal(state.results[0].matchId,'m1');assert.equal(state.results[0].candidates[0].available,false);
});
