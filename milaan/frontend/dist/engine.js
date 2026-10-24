export const money = p => new Intl.NumberFormat('en-PK',{maximumFractionDigits:2,minimumFractionDigits:p%100?2:0}).format(p/100);
export function paisa(value) {
  const s=String(value??'').trim().replace(/^(?:PKR|Rs\.?)[\s]*/i,'');
  if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$/.test(s)) throw Error('Use a positive amount such as 3,500.00.');
  const [whole,fraction='']=s.replaceAll(',','').split('.');
  const n=Number(whole)*100+Number(fraction.padEnd(2,'0'));
  if(!Number.isSafeInteger(n)||n<=0||n>100000000000)throw Error('Amount is outside the supported range.');
  return n;
}
export function timestamp(s){
  if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?$/.test(s||''))return NaN;
  const raw=s.replace(/(?:Z|[+-]\d{2}:\d{2})$/,'');
  const [date,time]=raw.split('T'),[y,m,d]=date.split('-').map(Number),[h,min,sec=0]=time.split(':').map(Number);
  if(m<1||m>12||d<1||d>new Date(Date.UTC(y,m,0)).getUTCDate()||h>23||min>59||sec>59)return NaN;
  return Date.parse(s+(/(?:Z|[+-]\d{2}:\d{2})$/.test(s)?'':'+05:00'));
}
export const normRef=s=>String(s||'').trim().toUpperCase().replace(/\s/g,'');
export const fullRef=s=>!!s&&!/[.*…•]|[xX]{2}|masked|last\s*\d/i.test(s)&&String(s).replace(/\s/g,'').length>=5;
export function parseCSV(text){
  if(new TextEncoder().encode(text).length>2_000_000)throw Error('CSV must be smaller than 2 MB.');
  text=text.replace(/^\uFEFF/,'');const rows=[];let row=[],cell='',quoted=false,closed=false;
  for(let i=0;i<text.length;i++){
    const ch=text[i];
    if(quoted){if(ch==='"'){if(text[i+1]==='"'){cell+='"';i++;}else{quoted=false;closed=true;}}else cell+=ch;continue;}
    if(ch==='"'){if(cell||closed)throw Error('Unexpected quote in CSV.');quoted=true;}
    else if(ch===','||ch==='\n'||ch==='\r'){row.push(cell.trim());cell='';closed=false;if(ch!==','){if(ch==='\r'&&text[i+1]==='\n')i++;if(row.some(Boolean))rows.push(row);row=[];}}
    else{if(closed&&!/\s/.test(ch))throw Error('Invalid text after a quoted field.');cell+=ch;}
  }
  if(quoted)throw Error('An opening quote is not closed.');row.push(cell.trim());if(row.some(Boolean))rows.push(row);
  if(rows.length<2)throw Error('CSV needs a header and at least one data row.');
  const headers=rows.shift().map(x=>x.toLowerCase());
  if(new Set(headers).size!==headers.length||headers.some(x=>!x))throw Error('CSV headers must be unique and non-empty.');
  if(rows.length>2000)throw Error('Use up to 2,000 rows per CSV in this version.');
  return rows.map((r,i)=>{if(r.length!==headers.length)throw Error(`Row ${i+2} has ${r.length} cells; expected ${headers.length}.`);return Object.fromEntries(headers.map((k,j)=>[k,r[j]]));});
}
export function importOrders(text){
  const rows=parseCSV(text),seen=new Set();return rows.map((r,i)=>{
    for(const k of ['order_ref','customer_name','amount_due','account_id'])if(!r[k])throw Error(`Orders row ${i+2}: missing ${k}.`);
    if(seen.has(r.order_ref))throw Error(`Duplicate order: ${r.order_ref}.`);seen.add(r.order_ref);
    if((r.currency||'PKR').toUpperCase()!=='PKR')throw Error('This version supports PKR only.');
    return {id:r.order_ref,name:r.customer_name,due:paisa(r.amount_due),account:r.account_id,currency:'PKR'};
  });
}
export function importStatement(text){
  const rows=parseCSV(text),seen=new Set();return rows.map((r,i)=>{
    for(const k of ['posted_at','direction','amount','account_id','transaction_id'])if(!r[k])throw Error(`Statement row ${i+2}: missing ${k}.`);
    const time=timestamp(r.posted_at);if(!Number.isFinite(time))throw Error(`Statement row ${i+2}: use YYYY-MM-DDTHH:MM for time.`);
    const direction=r.direction.toUpperCase();if(!['CREDIT','DEBIT'].includes(direction))throw Error(`Statement row ${i+2}: direction must be CREDIT or DEBIT.`);
    if((r.currency||'PKR').toUpperCase()!=='PKR')throw Error('This version supports PKR statements only.');
    const key=[r.account_id,direction,normRef(r.transaction_id),time,paisa(r.amount)].join('|');
    if(seen.has(key))throw Error(`Statement row ${i+2} duplicates a previous line.`);seen.add(key);
    return {id:'s'+i,account:r.account_id,amount:paisa(r.amount),time,ref:r.transaction_id,name:r.counterparty||'Not supplied',direction,currency:'PKR'};
  });
}
export const successfulStatus = value => ['success','successful','completed','paid','payment successful','transaction successful'].includes(String(value??'').trim().toLowerCase());
export function reconcile({orders,claims,lines,coverage,referenceVerified=false}){
  const refs=new Map(),digests=new Map();
  for(const c of claims){if(fullRef(c.ref)){const k=c.account+'|'+normRef(c.ref);refs.set(k,(refs.get(k)||0)+1);}if(c.digest)digests.set(c.digest,(digests.get(c.digest)||0)+1);}
  let results=orders.map(order=>{
    const found=claims.filter(c=>c.order===order.id),claim=found[0];
    const base={id:order.id,order,claim,candidates:[],status:'review',machine:'review',reason:'',code:'',decision:null};
    const finish=(status,code,reason)=>({...base,status,machine:status,code,reason});
    if(!found.length)return finish('review','NO_PROOF','No payment proof is linked to this order.');
    if(found.length>1)return finish('review','MULTIPLE_PROOFS','More than one proof is linked. Review them together.');
    const amount=claim.amount,time=timestamp(claim.at);
    if(!Number.isSafeInteger(amount)||amount<=0||!Number.isFinite(time)||!claim.confirmed)return finish('review','CHECK_DETAILS','Check and confirm the screenshot amount and timestamp.');
    if(claim.account!==order.account)return finish('review','ACCOUNT_CONFLICT','The claim and order use different receiving accounts.');
    const credits=lines.filter(l=>l.direction==='CREDIT'&&l.currency==='PKR'&&l.account===order.account);
    const exact=fullRef(claim.ref)?credits.filter(l=>normRef(l.ref)===normRef(claim.ref)):[];
    const close=credits.filter(l=>l.amount===amount&&Math.abs(l.time-time)<=10*60*1000);
    base.candidates=[...new Map([...exact,...close].map(l=>[l.id,l])).values()];
    if((fullRef(claim.ref)&&refs.get(claim.account+'|'+normRef(claim.ref))>1)||(claim.digest&&digests.get(claim.digest)>1))return finish('review','REUSED_PROOF','This reference or screenshot is also claimed by another order.');
    if(!successfulStatus(claim.status_text))return finish('review','STATUS_CONFLICT','Payment status is missing, unrecognized, pending or unsuccessful. Check the receipt.');
    if(exact.length&&lines.some(l=>l.direction==='DEBIT'&&l.currency==='PKR'&&l.account===order.account&&normRef(l.ref)===normRef(claim.ref)))return finish('review','REVERSAL','A same-reference debit may be a refund or reversal. Resolve the source evidence before allocating.');
    if(amount!==order.due)return finish('review','AMOUNT_CONFLICT','The screenshot amount does not equal the order total.');
    const start=timestamp(coverage.start),end=timestamp(coverage.end);
    if(!coverage.complete||!Number.isFinite(start)||!Number.isFinite(end)||end<=start||time<start||time>end)return finish('review','COVERAGE','The statement does not establish coverage for this claim.');
    if(exact.length>1)return finish('review','DUPLICATE_CREDIT','Multiple statement lines share this reference. Resolve the source records.');
    if(exact.length===1){
      if(exact[0].amount!==amount)return finish('review','AMOUNT_CONFLICT','The reference matches, but the statement amount is different.');
      if(Math.abs(exact[0].time-time)>24*60*60*1000)return finish('review','DATE_CONFLICT','The same reference appears on a different day.');
      if(!referenceVerified)return finish('review','VERIFY_REFERENCE','Confirm that full sender and receiver references correspond for these accounts.');
      return {...finish('ship','EXACT_MATCH','One statement credit matches the full reference and exact amount.'),allocated:exact[0].id};
    }
    if(base.candidates.length)return finish('review','POSSIBLE_MATCH',base.candidates.length>1?'Several credits could be this payment. Choose the correct one.':'Amount and time are close. A person must confirm this match.');
    if(time<start+10*60000||time>end-30*60000)return finish('review','POSTING_WINDOW','Coverage is too close to the claim time. Import a wider or newer statement.');
    if(!fullRef(claim.ref))return finish('review','PARTIAL_REFERENCE','The reference is missing or incomplete; ask for clearer proof.');
    return finish('hold','NOT_FOUND','No matching credit was found in the supplied statement.');
  });
  const allocations=new Map();for(const r of results)if(r.allocated){const list=allocations.get(r.allocated)||[];list.push(r.id);allocations.set(r.allocated,list);}
  return results.map(r=>r.allocated&&allocations.get(r.allocated).length>1?{...r,allocated:null,status:'review',machine:'review',code:'CONTESTED_CREDIT',reason:'This credit is contested by multiple orders.'}:r);
}
export function decide(results,id,status,lineId,reason){
  if(!reason||reason.trim().length<5)throw Error('Please add a short reason (at least 5 characters).');
  const row=results.find(r=>r.id===id);if(!row)throw Error('Order no longer exists.');
  if(!['ship','hold','review'].includes(status))throw Error('Unsupported decision.');
  if(status==='ship'){
    const line=row.candidates.find(l=>l.id===lineId);if(!line)throw Error('Select a candidate statement credit.');
    if(line.amount!==row.order.due||line.account!==row.order.account||line.direction!=='CREDIT')throw Error('This credit cannot cover the order exactly.');
    if(results.some(r=>r.id!==id&&r.status==='ship'&&r.allocated===lineId))throw Error('This credit is already assigned to another order.');
    if(row.code==='REVERSAL')throw Error('Resolve refund or reversal evidence before shipping.');
    if(row.code==='DUPLICATE_CREDIT')throw Error('Resolve the duplicate statement records and reconcile again.');
  }
  return results.map(r=>r.id===id?{...r,status,allocated:status==='ship'?lineId:null,decision:{status,reason:reason.trim(),at:new Date().toISOString()}}:r);
}
export function csvCell(v){let s=String(v??'');if(/^[\s]*[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}
export function exportCSV(results,mode){return ['order_ref,customer,amount_pkr,final_status,machine_status,reason,reviewer_reason,statement_line,source',...results.map(r=>[r.id,r.order.name,(r.order.due/100).toFixed(2),r.status,r.machine,r.reason,r.decision?.reason||'',r.allocated||'',mode].map(csvCell).join(','))].join('\r\n');}
export function receiptHints(text){
  const amount=text.match(/(?:PKR|Rs\.?|amount)\s*[:\s]*([\d,]+(?:\.\d{1,2})?)/i);
  const ref=text.match(/(?:transaction\s*(?:id|number|no\.?)|reference(?:\s*(?:id|number|no\.?))?|trx\s*id|tid)\s*[:#\s]*([A-Za-z0-9-]{5,})/i);
  return {amount:amount?.[1]||'',ref:ref?.[1]||''};
}
export function demoData(){
  const specs=[['1042','Hira Khan',3500,'MLN778810', '14:22'],['1043','Sana Malik',4200,'','16:05'],['1044','Usman Tariq',2800,'MLN940031','16:40'],['1045','Ayesha Noor',1200,'MLN778811','11:14'],['1046','Hamza Ahmed',6000,'MLN778812','12:35'],['1047','Mariam Ali',2100,'MLN778813','13:09'],['1048','Ali Raza',1800,'MLN940039','15:45'],['1049','Ahmed Bilal',2500,'MLN778814','14:50'],['1050','Sara Khan',2500,'MLN778814','14:50'],['1051','Nida Saleem',3300,'MLN778815','17:11'],['1052','Zain Malik',900,'MLN778816',''],['1053','Hassan Shah',4000,'MLN778817','21:15']];
  const orders=specs.map(([id,name,a])=>({id,name,due:a*100,account:'shop-wallet',currency:'PKR'}));
  const claims=specs.map(([id,name,a,ref,t],i)=>({id:'c'+i,order:id,name,amount:a*100,ref,at:t?'2026-10-09T'+t:'',account:'shop-wallet',confirmed:!!t,filename:'receipt-'+id+'.png',status_text:'Successful',mode:'sample',digest:'demo-'+i}));
  const lines=claims.filter((_,i)=>[0,3,4,5,7,9].includes(i)).map((q,i)=>({id:'s'+i,name:q.name,amount:q.amount,ref:q.ref,time:timestamp(q.at),direction:'CREDIT',currency:'PKR',account:'shop-wallet'}));
  lines.push({id:'s6',name:'Shahid Ahmed',amount:420000,ref:'MLN771111',time:timestamp('2026-10-09T16:04'),direction:'CREDIT',currency:'PKR',account:'shop-wallet'},{id:'s7',name:'Sana Malik',amount:420000,ref:'MLN772222',time:timestamp('2026-10-09T16:09'),direction:'CREDIT',currency:'PKR',account:'shop-wallet'});
  return {orders,claims,lines,coverage:{start:'2026-10-09T08:00',end:'2026-10-09T20:00',complete:true},referenceVerified:true};
}
