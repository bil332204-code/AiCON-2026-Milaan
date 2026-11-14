import test from 'node:test';
import assert from 'node:assert/strict';
import {parsePastedOrders,cleanAmount,ordersCSV,statementCSV,checkStatement,toLocalInput,fromLocalInput} from '../dist/seller-flow.js';

test('pasted orders accept commas, tabs, pipes and plain spaces, and skip a header row',()=>{
  const {orders,errors}=parsePastedOrders('Order, Name, Amount\n1042, Hira Khan, 3,500\n#1043\tSana Malik\tRs 4200\n1044 Usman Tariq 2800.5\n1045 | Ayesha Noor | 1,200.00');
  assert.deepEqual(errors,[]);
  assert.deepEqual(orders.map(o=>[o.order_ref,o.customer_name,o.amount_due]),[
    ['1042','Hira Khan','3500.00'],['1043','Sana Malik','4200.00'],['1044','Usman Tariq','2800.50'],['1045','Ayesha Noor','1200.00']]);
});

test('pasted orders explain problems line by line and block duplicates',()=>{
  const {orders,errors}=parsePastedOrders('1042, Hira, 100\nonly two\n1046, Ali, abc\n1042, Again, 50\n1047, Bilal, 10',['1047']);
  assert.equal(orders.length,1);
  assert.equal(errors.length,4);
  assert.match(errors[0],/Line 2/);assert.match(errors[1],/not an amount/);assert.match(errors[2],/already in this batch/);assert.match(errors[3],/1047/);
});

test('amounts must be positive with at most two decimals',()=>{
  assert.equal(cleanAmount('Rs. 3,500'),'3500.00');assert.equal(cleanAmount('0'),null);assert.equal(cleanAmount('12.345'),null);assert.equal(cleanAmount('1,23'),null);
});

test('CSV builders quote every cell so names with commas or quotes stay intact',()=>{
  assert.equal(ordersCSV([{order_ref:'1',customer_name:'Ali, "Jr"',amount_due:'10.00'}],'JazzCash'),'order_ref,customer_name,amount_due,account_id,currency\r\n"1","Ali, ""Jr""","10.00","JazzCash","PKR"');
  assert.match(statementCSV([{posted_at:'2026-11-02T14:22:00+05:00',direction:'CREDIT',amount:'3500.00',counterparty:'',transaction_id:''}]),/"Unknown",""$/);
});

test('reviewed statement rows must sit inside the declared period',()=>{
  const period={start:fromLocalInput('2026-11-01T00:00'),end:fromLocalInput('2026-11-07T23:59','59')};
  const good={posted_at:'2026-11-02T14:22:00+05:00',direction:'CREDIT',amount:'3500.00'};
  assert.deepEqual(checkStatement([good],period),[]);
  assert.match(checkStatement([{...good,posted_at:'2026-11-09T10:00:00+05:00'}],period)[0],/outside the statement period/);
  assert.match(checkStatement([{...good,amount:'abc'}],period)[0],/amount/);
  assert.match(checkStatement([],{start:'',end:''}).join(' '),/at least one/);
  assert.equal(toLocalInput('2026-11-02T14:22:00+05:00'),'2026-11-02T14:22');
});
