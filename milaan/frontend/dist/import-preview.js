import {parseCSV,paisa,timestamp,normRef} from './engine.js';

export const fieldsFor=kind=>kind==='orders'?['order_ref','customer_name','amount_due','account_id','currency']:['posted_at','direction','amount','counterparty','transaction_id','account_id','currency'];
const quote=value=>'"'+String(value??'').replaceAll('"','""')+'"';
export const encodeCSV=(fields,rows)=>[fields,...rows.map(r=>fields.map(f=>r[f]??''))].map(row=>row.map(quote).join(',')).join('\r\n');

export function previewImport(text,kind,mapping,options={}) {
  const source=parseCSV(text),fields=fieldsFor(kind),errors=[],warnings=[],rows=[],seen=new Set(),refs=new Set();
  const mapped=Object.values(mapping).filter(Boolean);
  if(new Set(mapped).size!==mapped.length)throw Error('Map each source column to only one field.');
  for(const [index,input] of source.entries()) {
    const row=Object.fromEntries(fields.map(f=>[f,mapping[f]?input[mapping[f]]??'':'']));
    row.currency=row.currency||'PKR';
    if(kind==='statement'&&!mapping.account_id&&options.account)row.account_id=options.account;
    const record=index+2;
    try {
      const required=kind==='orders'?['order_ref','customer_name','amount_due','account_id']:['posted_at','direction','amount','account_id'];
      for(const f of required)if(!row[f])throw Error(`${f}: required value or mapping missing.`);
      if(!mapping.transaction_id&&kind==='statement')throw Error('transaction_id: map the reference column (blank source values remain blank).');
      if(row.currency!=='PKR')throw Error('currency: only PKR is supported.');
      if(row.account_id.length>100)throw Error('account_id: maximum 100 characters.');
      if(kind==='orders') {
        if(row.order_ref.length>100||row.customer_name.length>150)throw Error('order_ref / customer_name exceeds its supported length.');
        try{paisa(row.amount_due);}catch(error){throw Error('amount_due: '+error.message);}
        if(seen.has(row.order_ref))throw Error('order_ref: duplicate order.');
        seen.add(row.order_ref);
      } else {
        if(!/(?:Z|[+-]\d{2}:\d{2})$/.test(row.posted_at))row.posted_at+=options.timezone||'+05:00';
        const at=timestamp(row.posted_at);if(!Number.isFinite(at))throw Error('posted_at: use a full ISO date and time.');
        if(options.account&&row.account_id!==options.account)throw Error('account_id: differs from the declared receiving account.');
        if(options.coverage) {
          const start=timestamp(options.coverage.start),end=timestamp(options.coverage.end);
          if(!Number.isFinite(start)||!Number.isFinite(end)||end<=start)throw Error('coverage: set a valid start and end before importing.');
          if(at<start||at>end)throw Error('posted_at: outside the declared statement coverage.');
        }
        row.direction=row.direction.toUpperCase();
        if(!['CREDIT','DEBIT'].includes(row.direction))throw Error('direction: use CREDIT or DEBIT; normalize bank-specific labels explicitly.');
        let amount;try{amount=paisa(row.amount);}catch(error){throw Error('amount: '+error.message);}
        if(row.transaction_id.length>150||row.counterparty.length>200)throw Error('transaction_id / counterparty exceeds its supported length.');
        const key=JSON.stringify([row.account_id,at,row.direction,amount,normRef(row.transaction_id),row.counterparty]);
        if(seen.has(key))throw Error('duplicate transaction record; correct the source before saving.');
        seen.add(key);
        if(options.local&&!row.transaction_id)throw Error('transaction_id: browser-local mode requires a reference; use saved mode for incomplete evidence.');
        if(!row.transaction_id)warnings.push({record,message:'Blank reference: retained as incomplete evidence; no reference is invented.'});
        const ref=row.account_id+'|'+normRef(row.transaction_id);
        if(row.direction==='CREDIT'&&row.transaction_id&&refs.has(ref))warnings.push({record,message:'Repeated credit reference: matching will require review.'});
        if(row.direction==='CREDIT'&&row.transaction_id)refs.add(ref);
      }
      rows.push(row);
    } catch(error) {errors.push({record,message:error.message});}
  }
  const csv=encodeCSV(fields,rows);
  if(new TextEncoder().encode(csv).length>2_000_000)throw Error('Mapped CSV exceeds 2 MB; split the source before importing.');
  return {rows,errors,warnings,accepted:rows.length,rejected:errors.length,total:source.length,csv};
}

const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Originals are held only in memory until the dialog closes; no upload occurs on preview.
export async function reviewImport(file,kind,options={}) {
  if(file.size>2_000_000)throw Error('CSV exceeds 2 MB.');
  let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());}catch{throw Error('CSV must be valid UTF-8.');}
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer())),byte=>byte.toString(16).padStart(2,'0')).join('');
  const source=parseCSV(text),headers=Object.keys(source[0]),fields=fieldsFor(kind);
  const dialog=document.createElement('dialog');dialog.className='import-preview';dialog.setAttribute('aria-labelledby','preview-title');
  dialog.innerHTML=`<h2 id="preview-title">Review ${kind} import</h2><p>${esc(file.name)} · ${source.length} records. Map columns, inspect all errors, then confirm. Nothing has been saved.</p><p>Use normalized ISO timestamps and positive PKR amounts. No PDF or AI processing occurs here.</p><div class="preview-mapping">${fields.map(field=>`<label class="field">${field}<select data-map="${field}" aria-label="Map ${field}"><option value="">${field==='account_id'&&options.account?'Use declared account':'Not mapped'}</option>${headers.map(header=>`<option value="${esc(header)}" ${header===field?'selected':''}>${esc(header)}</option>`).join('')}</select></label>`).join('')}</div>${kind==='statement'?`<label class="field">Timezone for source timestamps without an offset<select id="preview-timezone"><option value="+05:00">Asia/Karachi (UTC+05:00)</option><option value="Z">UTC</option></select></label><p>Existing explicit offsets are preserved. Coverage remains the period you declared in Pakistan time.</p>`:''}<div id="preview-summary" role="status" aria-live="polite"></div><div id="preview-issues"></div><div class="preview-table" tabindex="0" aria-label="Normalized record preview"></div><p>Showing up to 20 records; every record is validated. Rejected rows block the entire import; no rows are silently discarded.</p><label class="checkbox-row"><input type="checkbox" id="preview-confirm"><span>I reviewed the mapped evidence${kind==='statement'?' and the declared statement coverage':''}. Save only these reviewed records.</span></label><div class="preview-actions"><button type="button" class="btn btn-outline" id="preview-cancel">Cancel import</button><button type="button" class="btn btn-forest" id="preview-save" disabled>Save reviewed import</button></div>`;
  document.body.append(dialog);
  const $=selector=>dialog.querySelector(selector);let preview,mapping;
  function update() {
    $('#preview-confirm').checked=false;$('#preview-save').disabled=true;
    try {
      mapping=Object.fromEntries([...dialog.querySelectorAll('[data-map]')].map(el=>[el.dataset.map,el.value]));
      preview=previewImport(text,kind,mapping,{...options,timezone:$('#preview-timezone')?.value});
      $('#preview-summary').textContent=`${preview.accepted} accepted · ${preview.rejected} rejected · ${preview.warnings.length} warnings (not saved)`;
      $('#preview-issues').innerHTML=[...preview.errors,...preview.warnings].slice(0,100).map(issue=>`<p>Record ${issue.record}: ${esc(issue.message)}</p>`).join('');
      $('.preview-table').innerHTML='<table><thead><tr>'+fields.map(f=>`<th>${esc(f)}</th>`).join('')+'</tr></thead><tbody>'+preview.rows.slice(0,20).map(row=>'<tr>'+fields.map(f=>`<td>${esc(row[f])}</td>`).join('')+'</tr>').join('')+'</tbody></table>';
    } catch(error) {preview=null;$('#preview-summary').textContent=error.message;$('#preview-issues').textContent='';$('.preview-table').textContent='';}
  }
  for(const el of dialog.querySelectorAll('select'))el.onchange=update;
  $('#preview-confirm').onchange=()=>{$('#preview-save').disabled=!$('#preview-confirm').checked||!preview||preview.rejected>0||preview.accepted===0;};
  update();dialog.showModal();
  return new Promise(resolve=>{
    let settled=false;
    const finish=result=>{if(settled)return;settled=true;dialog.close();dialog.remove();resolve(result);};
    $('#preview-cancel').onclick=()=>finish(null);
    dialog.addEventListener('cancel',event=>{event.preventDefault();finish(null);});
    $('#preview-save').onclick=()=>{if(!preview||preview.rejected||!$('#preview-confirm').checked)return;const result=new File([preview.csv],file.name,{type:'text/csv'});result.provenance={source_sha256:digest,mapping,timezone:$('#preview-timezone')?.value||'+05:00'};finish(result);};
    dialog.onclose=()=>finish(null);
  });
}
