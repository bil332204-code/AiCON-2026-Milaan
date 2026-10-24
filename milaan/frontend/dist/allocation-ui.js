import {money,paisa} from './engine.js';
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function fundingSummary(due,amounts){
  const paid=amounts.reduce((sum,value)=>sum+paisa(value),0);
  return {paid,outstanding:Math.max(0,due-paid),excess:Math.max(0,paid-due)};
}
export async function allocationDialog(state,save){
  const dialog=document.createElement('dialog');dialog.className='import-preview allocation-plan';dialog.setAttribute('aria-labelledby','allocation-title');
  dialog.innerHTML=`<h2 id="allocation-title">Review payment allocations</h2><p>Confirm which source credits fund each order. A checked, successful receipt must match the entire source credit. A shared receipt may support several orders only when you explicitly confirm their relationship.</p><p>Unchecked orders stay unchanged. Selected orders replace all their previous allocations; removing every part releases their reserved funds. Source “free” amounts are current balances before replacing selected allocations. Partial funding stays in Review. Overpayments are left unassigned; no automatic refund or settlement claim is made.</p><form id="allocation-form"><div class="allocation-orders">${state.results.map((r,index)=>`<section class="allocation-order" data-plan-order="${index}"><label class="checkbox-row"><input type="checkbox" data-include><span>Include ${esc(r.id)} · ${esc(r.order.name)} · PKR ${money(r.order.due)}</span></label><fieldset class="plain-fieldset" disabled><div class="allocation-parts"></div><button type="button" class="link-button" data-add-part>Add source credit</button></fieldset><p class="allocation-summary" role="status">Not selected; current funding: PKR ${money(r.paid||0)}.</p></section>`).join('')}</div><label class="field">Reason and payment relationship<textarea id="allocation-reason" required minlength="5" maxlength="1000" placeholder="Explain who paid, which orders it covers and why these shares are correct."></textarea></label><label class="checkbox-row"><input id="allocation-confirm" type="checkbox" required><span>I checked each selected receipt, full reference, successful status, source credit and receiving account, and confirmed the purpose of every shared or split payment.</span></label><p id="allocation-error" class="validation-error" role="alert" hidden></p><div class="preview-actions"><button type="button" id="allocation-cancel" class="btn btn-outline">Cancel</button><button type="submit" class="btn btn-forest" id="allocation-save">Save allocation review</button></div></form>`;
  document.body.append(dialog);let changed=false,saving=false,requestText='',requestKey='';
  const sections=[...dialog.querySelectorAll('[data-plan-order]')];
  function partRow(section,part={}){
    const result=state.results[Number(section.dataset.planOrder)],row=document.createElement('div');row.className='allocation-part';
    const credits=state.lines.filter(l=>l.direction==='CREDIT'&&l.currency==='PKR'&&l.account===result.order.account);
    const claims=state.claims.filter(c=>c.account===result.order.account);
    row.innerHTML=`<label class="field">Source credit<select data-part-line required><option value="">Choose source credit</option>${credits.map(l=>`<option value="${esc(l.id)}" ${l.id===part.statement_line_id?'selected':''}>${esc(l.ref||'Missing reference')} · PKR ${money(l.amount)} · free ${money(l.unallocated??l.amount)}</option>`).join('')}</select></label><label class="field">Receipt evidence<select data-part-claim required><option value="">Choose receipt evidence</option>${claims.map(c=>`<option value="${esc(c.id)}" ${c.id===part.claim_id?'selected':''}>${esc(c.order)} · ${esc(c.filename)} · ${esc(c.ref)} · PKR ${money(c.amount||0)} · ${esc(c.status_text||'Unknown status')}</option>`).join('')}</select></label><label class="field">Allocate to this order (PKR)<input data-part-amount inputmode="decimal" required value="${part.amount_paisa?(part.amount_paisa/100).toFixed(2):''}" placeholder="e.g. 60.00"></label><button type="button" class="link-button" data-remove-part>Remove part</button><p class="allocation-source-details" data-source-details></p>`;
    row.querySelector('[data-remove-part]').onclick=()=>{row.remove();dialog.querySelector('#allocation-confirm').checked=false;summary(section);};
    section.querySelector('.allocation-parts').append(row);
  }
  function summary(section){
    const included=section.querySelector('[data-include]').checked;
    if(!included)return;
    for(const part of section.querySelectorAll('.allocation-part')){
      const line=state.lines.find(l=>l.id===part.querySelector('[data-part-line]').value);
      const claim=state.claims.find(c=>c.id===part.querySelector('[data-part-claim]').value);
      part.querySelector('[data-source-details]').textContent=[line?`Credit: ${line.ref} · PKR ${money(line.amount)} · ${new Date(line.time).toLocaleString('en-GB',{timeZone:'Asia/Karachi'})} PKT`:null,
        claim?`Receipt: ${claim.ref} · PKR ${money(claim.amount||0)} · ${claim.at} PKT · ${claim.status_text||'unknown status'} · ${claim.confirmed?'fields confirmed':'fields unconfirmed'}`:null].filter(Boolean).join(' | ');
    }
    try{
      const values=[...section.querySelectorAll('[data-part-amount]')].map(input=>input.value);
      const result=state.results[Number(section.dataset.planOrder)],total=fundingSummary(result.order.due,values);
      section.querySelector('.allocation-summary').textContent=`Allocated PKR ${money(total.paid)} · outstanding ${money(total.outstanding)}${total.excess?' · overallocated '+money(total.excess)+' (cannot save)':''}. ${total.excess?'Reduce the overallocated share before saving.':total.outstanding?'Stays in Review.':'Fully funded; explicit confirmation still required.'}`;
    }catch(error){section.querySelector('.allocation-summary').textContent=error.message;}
  }
  for(const section of sections){
    const result=state.results[Number(section.dataset.planOrder)];
    for(const part of result.allocations||[])partRow(section,part);
    if(!result.allocations?.length)partRow(section);
    section.querySelector('[data-include]').onchange=event=>{section.querySelector('fieldset').disabled=!event.target.checked;dialog.querySelector('#allocation-confirm').checked=false;summary(section);};
    section.querySelector('[data-add-part]').onclick=()=>{if(section.querySelectorAll('.allocation-part').length>=20)return;partRow(section);dialog.querySelector('#allocation-confirm').checked=false;summary(section);};
  }
  dialog.querySelector('#allocation-cancel').onclick=()=>{if(!saving)dialog.close();};
  dialog.addEventListener('cancel',event=>{if(saving)event.preventDefault();});
  dialog.querySelector('#allocation-form').addEventListener('input',event=>{if(event.target.id!=='allocation-confirm')dialog.querySelector('#allocation-confirm').checked=false;const section=event.target.closest('[data-plan-order]');if(section)summary(section);});
  dialog.querySelector('#allocation-form').onsubmit=async event=>{
    event.preventDefault();const error=dialog.querySelector('#allocation-error'),button=dialog.querySelector('#allocation-save');error.hidden=true;let controls=[];
    try{
      const orders=sections.filter(section=>section.querySelector('[data-include]').checked).map(section=>{
        const result=state.results[Number(section.dataset.planOrder)];
        return {match_id:result.matchId,expected_version:result.version,parts:[...section.querySelectorAll('.allocation-part')].map(row=>({statement_line_id:row.querySelector('[data-part-line]').value,claim_id:row.querySelector('[data-part-claim]').value,amount_pkr:row.querySelector('[data-part-amount]').value}))};
      });
      if(!orders.length)throw Error('Select at least one order to review.');
      const body={expected_revision:state.remote.revision,orders,reason:dialog.querySelector('#allocation-reason').value,confirmed_relationships:dialog.querySelector('#allocation-confirm').checked};
      const serialized=JSON.stringify(body);if(serialized!==requestText){requestText=serialized;requestKey=crypto.randomUUID();}
      saving=true;controls=[...dialog.querySelectorAll('input,select,textarea,button,fieldset')].map(el=>[el,el.disabled]);for(const [el] of controls)el.disabled=true;button.textContent='Saving reviewed allocations…';
      // Retain the same key for an unchanged retry after a lost response.
      await save(body,requestKey);changed=true;dialog.close();
    }catch(failure){error.hidden=false;error.textContent=failure.message;}
    finally{saving=false;for(const [el,disabled] of controls)el.disabled=disabled;button.textContent='Save allocation review';}
  };
  dialog.showModal();
  return new Promise(resolve=>dialog.onclose=()=>{dialog.remove();resolve(changed);});
}
