export function localTime(value) {
  if(!value||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(value))return '';
  if(!/(?:Z|[+-]\d{2}:\d{2})$/.test(value))return value.slice(0,16);
  const time=Date.parse(value);return Number.isFinite(time)?new Date(time+5*3600000).toISOString().slice(0,16):'';
}
const amount=value=>{const n=Number(String(value||'').replace(/^(?:PKR|Rs\.?)\s*/i,'').replaceAll(',',''));return Number.isFinite(n)&&n>0?Math.round(n*100):null;};
export function mapRemote(batch, orders, claims, statements, lines, results, events) {
  const mappedOrders = orders.map(o => ({id:o.order_ref,name:o.customer_name,due:o.amount_due_paisa,account:o.account_id,serverId:o.id}));
  const orderLookup = new Map(mappedOrders.map(o=>[o.serverId,o]));
  const mappedClaims = claims.map(c=>({id:c.id,order:orderLookup.get(c.order_id)?.id||'',serverOrder:c.order_id,
    name:c.fields.sender_name||'',amount:amount(c.fields.amount_pkr),
    ref:c.fields.transaction_id||'',at:localTime(c.fields.datetime_local),account:c.account_id,confirmed:c.fields_checked,
    mode:c.extraction_mode,filename:c.filename,digest:c.sha256,version:c.version,fields:c.fields,
    text:c.read_a||c.read_b?JSON.stringify({first_read:c.read_a,second_read:c.read_b,status:c.extraction_status,error:c.extraction_error},null,2):'',
    ocrStatus:c.extraction_status==='pending'?'Read with AI':c.extraction_status.replaceAll('_',' '),extractionStatus:c.extraction_status,hasImage:!!c.image_url,url:null}));
  const claimLookup=new Map(mappedClaims.map(c=>[c.id,c]));
  const mapLine=l=>({id:l.id,name:l.counterparty,amount:l.amount_paisa,ref:l.transaction_id,time:Date.parse(l.posted_at),account:l.account_id,available:l.available});
  const statementAccount=mappedOrders.find(o=>!statements.some(s=>s.account_id===o.account))?.account||statements[0]?.account_id||mappedOrders[0]?.account||'';
  const first=statements.find(s=>s.account_id===statementAccount);
  return {remote:batch,orders:mappedOrders,claims:mappedClaims,lines:lines.map(mapLine),statements,statementAccount,
    mode:batch.is_demo?'demo':'own',ordersFile:'Saved order records',statementFile:statements.map(s=>s.filename).join(', '),
    coverage:{start:localTime(first?.coverage_start),end:localTime(first?.coverage_end),complete:first?.complete||false},referenceVerified:first?.references_verified||false,
    results:results.map(r=>({id:orderLookup.get(r.order_id)?.id||r.order.order_ref.replace(/^#/,''),order:orderLookup.get(r.order_id),claim:claimLookup.get(r.claim_id),
      status:r.final_status,machine:r.machine_verdict,code:r.reason_code,reason:r.reason,candidates:r.candidates.map(mapLine),allocated:r.selected_line_id,
      matchId:r.id,version:r.version,evidence:r.evidence,decision:r.reviewer_reason?{reason:r.reviewer_reason}:null})),
    activity:events.map(e=>({title:e.action.replaceAll('_',' '),detail:JSON.stringify(e.detail),at:Date.parse(e.created_at)}))};
}
