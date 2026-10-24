import test from 'node:test';
import assert from 'node:assert/strict';
import {previewImport,encodeCSV,fieldsFor} from '../dist/import-preview.js';
const mapping={posted_at:'date',direction:'type',amount:'value',transaction_id:'ref',counterparty:'person'};
const header='date,type,value,ref,person\n';
const options={account:'wallet',coverage:{start:'2026-10-09T08:00',end:'2026-10-09T20:00'}};
test('bank column mapping retains quoted evidence and explicit provenance times',()=>{
  const p=previewImport('\ufeff'+header+'2026-10-09T14:00,credit,100,REF123,"Ali, Khan"','statement',mapping,options);
  assert.equal(p.accepted,1);assert.equal(p.rejected,0);assert.equal(p.rows[0].account_id,'wallet');assert.equal(p.rows[0].posted_at,'2026-10-09T14:00+05:00');assert.equal(p.rows[0].counterparty,'Ali, Khan');
});
test('invalid and duplicate records return row-specific errors with exact counts',()=>{
  const row='2026-10-09T14:00,CREDIT,100,REF123,Ali';
  const p=previewImport(header+row+'\n'+row+'\n2026-10-09T14:00,CREDIT,no,REF456,Ali','statement',mapping,options);
  assert.equal(p.accepted,1);assert.equal(p.rejected,2);assert.deepEqual(p.errors.map(e=>e.record),[3,4]);assert.match(p.errors[0].message,/duplicate/);
});
test('blank references are not invented; repeated references warn without silently merging',()=>{
  const p=previewImport(header+'2026-10-09T14:00,CREDIT,100,,Ali\n2026-10-09T14:01,CREDIT,100,REF123,Ali\n2026-10-09T14:02,CREDIT,100,REF123,Ali','statement',mapping,options);
  assert.equal(p.rows[0].transaction_id,'');assert.equal(p.accepted,3);assert.equal(p.warnings.length,2);
});
test('mapping requires reference column, rejects duplicate source mapping and account conflicts',()=>{
  assert.equal(previewImport(header+'2026-10-09T14:00,CREDIT,100,REF123,Ali','statement',{...mapping,transaction_id:''},options).rejected,1);
  assert.throws(()=>previewImport(header+'x,x,1,x,x','statement',{...mapping,amount:'date'},options),/only one/);
  const p=previewImport(header+'2026-10-09T14:00,CREDIT,100,REF123,other','statement',{...mapping,counterparty:'',account_id:'person'},options);assert.equal(p.rejected,1);
});
test('timezone selection is explicit and existing offsets survive unchanged',()=>{
  const p=previewImport(header+'2026-10-09T09:00,CREDIT,100,REF123,Ali','statement',mapping,{...options,timezone:'Z'});
  assert.equal(p.rows[0].posted_at,'2026-10-09T09:00Z');
  const q=previewImport(header+'2026-10-09T09:00Z,CREDIT,100,REF123,Ali','statement',mapping,options);assert.equal(q.rows[0].posted_at,'2026-10-09T09:00Z');
});
test('outside coverage, invalid date, currency and missing mappings cannot be accepted',()=>{
  for(const at of ['2026-02-30T14:00','2026-10-09T23:00','14:00'])assert.equal(previewImport(header+`${at},CREDIT,100,REF123,Ali`,'statement',mapping,options).rejected,1);
  assert.equal(previewImport('order_ref,customer_name,amount_due,account_id,currency\n1,Ali,100,a,USD','orders',Object.fromEntries(fieldsFor('orders').map(f=>[f,f]))).rejected,1);
});
test('normalized CSV quotes original values without manufacturing evidence',()=>{
  assert.match(encodeCSV(['name'],[{name:'=value,"x"'}]),/"=value,""x"""/);
});
test('browser-local incomplete references fail visibly while saved mode retains weak evidence',()=>{
  const text=header+'2026-10-09T14:00,CREDIT,100,,Ali';
  assert.equal(previewImport(text,'statement',mapping,{...options,local:true}).rejected,1);
  assert.equal(previewImport(text,'statement',mapping,options).accepted,1);
});
