import {allocationDialog} from './allocation-ui.js';
import {reviewImport} from './import-preview.js';
import {MilaanAPI} from './milaan-api.js';
import {mapRemote} from './remote-state.js';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $=s=>document.querySelector(s);
export function validateBackendURL(value, pageProtocol=location.protocol) {
  const url=new URL(value);
  if(url.username||url.password||url.search||url.hash)throw Error('Use the backend origin only, without credentials, query or fragment.');
  if(!['http:','https:'].includes(url.protocol))throw Error('Use an HTTP or HTTPS backend address.');
  if(url.pathname!=='/')throw Error('Use the backend origin, without an API path.');
  if(pageProtocol==='https:'&&url.protocol!=='https:')throw Error('This online page needs an HTTPS backend. For your laptop, use the downloaded website at http://localhost:8080.');
  return url.origin;
}
export function createBackend(hooks) {
  const {getState,setState,render,showWorkspace,dispose,toast,ask}=hooks;
  let base='';try{base=localStorage.getItem('milaan-backend-origin')||'';if(base)base=validateBackendURL(base);}catch{base='';}
  if(!base)base=location.port==='8080'?location.protocol+'//'+location.hostname+':8000':location.origin;
  const api=new MilaanAPI(base);api.sessionMode=new URL(base).hostname===location.hostname&&new URL(base).protocol===location.protocol?'cookie':'bearer';let profile=null,contentValues=null,integrationStatus=null,working=false,pending='batches';
  const cache=new Map();let authEpoch=0;const channel=typeof BroadcastChannel!=='undefined'?new BroadcastChannel('milaan-auth'):null;
  const announceSessionChange=()=>channel?.postMessage('session-changed');
  if(channel)channel.onmessage=event=>{if(event.data==='session-changed'){api.clearSession();clearPrivate();render();authenticate();toast('Your session changed in another tab. Sign in to continue.');}};
  window.addEventListener('pagehide',event=>{if(!event.persisted)channel?.close();});
  const authDialog=document.createElement('dialog');authDialog.id='account-dialog';authDialog.className='help-dialog account-dialog';authDialog.setAttribute('aria-labelledby','account-heading');
  authDialog.innerHTML=`<button class="dialog-close icon-button" type="button" data-account-close aria-label="Close authentication">×</button><a href="/" class="brand auth-brand">milaan<span class="brand-dot">.</span></a><div class="eyebrow dark-label">YOUR PRIVATE WORKSPACE</div><h2 id="account-heading">Welcome back.</h2><p class="account-intro">A clearer view of every payment. Sign in to your Milaan account.</p><form id="account-form"><details class="auth-connection"><summary>Connection settings</summary><label class="field">Backend address<input id="backend-origin" type="url" required value="${esc(base)}"></label><p class="auth-guidance">Same-host sign-in supports secure remembered sessions. A separate backend hostname uses a temporary API session that ends on refresh.</p></details><label class="field" id="name-field" hidden>Your name<input id="account-name" autocomplete="name" maxlength="100"></label><label class="field" id="email-field">Email address<input id="account-email" type="email" autocomplete="username" required></label><div id="password-fields"><label class="field">Password<div class="password-input"><input id="account-password" type="password" autocomplete="current-password" required minlength="1" maxlength="256"><button type="button" id="password-toggle" aria-label="Show password" aria-pressed="false">Show</button></div></label><label class="field" id="confirm-field" hidden>Confirm password<input id="account-confirm" type="password" autocomplete="new-password" maxlength="256"></label><p id="password-guidance" class="auth-guidance" hidden>Use 10–256 characters. A long, unique passphrase is best.</p></div><label class="checkbox-row" id="remember-field"><input type="checkbox" id="account-remember"><span>Remember me for up to 30 days on this device</span></label><button class="link-button" id="forgot-password" type="button">Forgot password?</button><div id="verification-fields" hidden><p id="verification-message" role="status"></p><label class="field">6-digit email code<input id="account-code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" maxlength="6"></label><button class="link-button" id="resend-code" type="button">Resend code</button></div><div id="account-error" class="validation-error" role="alert" hidden></div><p id="account-success" class="auth-success" role="status" hidden></p><button class="btn btn-forest" id="account-submit" type="submit">Sign in</button><button class="link-button" id="account-switch" type="button">Create a new account</button></form><p class="account-note">Private records. Explainable decisions. Your judgment stays in control. <a href="https://milaan-studio.bil332204.chatgpt.site/workspace" rel="noreferrer">Existing hosted records stay in the current workspace.</a></p>`;
  document.body.append(authDialog);let authMode='login',challenge=null,resendAt=0,resetToken='',ready=Promise.resolve();
  if(location.pathname==='/reset-password'){resetToken=new URLSearchParams(location.hash.slice(1)).get('token')||'';history.replaceState(null,'',location.pathname);}
  window.addEventListener('hashchange',()=>{if(location.pathname==='/reset-password'){const incoming=new URLSearchParams(location.hash.slice(1)).get('token');if(incoming){resetToken=incoming;history.replaceState(null,'',location.pathname);authenticate('batches','reset');}}});
  function clearPrivate(){authEpoch++;document.title='Milaan · Payment clarity';for(const dialog of document.querySelectorAll('dialog[open]')){if(dialog===authDialog)continue;if(dialog.id==='confirm-dialog')dialog.dispatchEvent(new Event('cancel',{cancelable:true}));else dialog.close();if(dialog.classList.contains('import-preview')){dialog.replaceChildren();dialog.remove();}}dispose();cache.clear();profile=null;contentValues=null;integrationStatus=null;$('#review-dialog').close();$('#review-content').replaceChildren();$('#workspace-faq')?.replaceChildren();setState({...getState(),remote:null,orders:[],claims:[],lines:[],results:[],activity:[],view:'batches'});}
  api.onUnauthorized=()=>{if(profile){clearPrivate();render();authenticate();}};
  $('[data-account-close]').onclick=()=>authDialog.close();
  authDialog.addEventListener('close',()=>document.body.classList.remove('auth-open'));
  function showAuthMode(){
    const verifying=!!challenge,signup=authMode==='signup',reset=authMode==='reset',forgot=authMode==='forgot';
    $('#account-heading').textContent=verifying?'Check your inbox.':signup?'Make room for clarity.':reset?'A fresh start.':forgot?'Let’s get you back in.':'Welcome back.';
    $('.account-intro').textContent=verifying?(challenge.account_verification?'Confirm the email on your existing account to enable secure recovery.':'Verify your email to create your private workspace.'):signup?'Create your independent Milaan account.':reset?'Choose a new password. Previous sessions will be signed out.':forgot?'Enter your email to request a secure recovery link.':'A clearer view of every payment. Sign in to your Milaan account.';
    $('#name-field').hidden=!signup||verifying;$('#email-field').hidden=reset||verifying;$('#password-fields').hidden=forgot||verifying;
    $('#confirm-field').hidden=!(signup||reset);$('#password-guidance').hidden=!(signup||reset);
    $('#remember-field').hidden=authMode!=='login'||verifying||api.sessionMode!=='cookie';$('#forgot-password').hidden=authMode!=='login'||verifying;
    $('#verification-fields').hidden=!verifying;$('.auth-connection').hidden=verifying;
    $('#account-name').required=signup&&!verifying;$('#account-name').disabled=!signup||verifying;
    $('#account-email').required=!reset&&!verifying;$('#account-email').disabled=reset||verifying;
    $('#account-password').required=!forgot&&!verifying;$('#account-password').disabled=forgot||verifying;
    $('#account-password').minLength=signup||reset?10:1;$('#account-password').autocomplete=signup||reset?'new-password':'current-password';
    $('#account-confirm').required=(signup||reset)&&!verifying;$('#account-confirm').disabled=!(signup||reset)||verifying;
    $('#account-code').required=verifying;$('#account-code').disabled=!verifying;
    $('#account-submit').textContent=verifying?'Verify email & continue':signup?'Create account':reset?'Update password':forgot?'Send recovery link':'Sign in';
    $('#account-switch').textContent=signup||reset||forgot||verifying?'Back to sign in':'Create a new account';
    if(verifying){$('#verification-message').textContent=`We sent a code to ${challenge.email}. It expires in 10 minutes.`;$('#account-code').focus();}
  }
  function authError(error){$('#account-error').hidden=false;$('#account-error').textContent=Array.isArray(error.detail)?error.detail.map(e=>e.msg).join(' '):error.message==='Failed to fetch'?'Could not connect. Try again, or check your connection.':error.message;}
  function success(text){$('#account-success').hidden=false;$('#account-success').textContent=text;}
  function mode(value){authMode=value;challenge=null;for(const id of ['account-password','account-confirm'])$('#'+id).type='password';$('#password-toggle').textContent='Show';$('#password-toggle').setAttribute('aria-label','Show password');$('#password-toggle').setAttribute('aria-pressed','false');$('#account-error').hidden=true;$('#account-success').hidden=true;$('#account-password').value='';$('#account-confirm').value='';showAuthMode();}
  $('#account-switch').onclick=()=>{if(challenge?.account_verification){challenge=null;authDialog.close();return;}mode(authMode==='login'&&!challenge?'signup':'login');};
  $('#forgot-password').onclick=()=>mode('forgot');
  $('#backend-origin').addEventListener('change',()=>{try{api.baseUrl=validateBackendURL($('#backend-origin').value.trim());api.sessionMode=new URL(api.baseUrl).hostname===location.hostname&&new URL(api.baseUrl).protocol===location.protocol?'cookie':'bearer';if(api.sessionMode==='bearer')$('#account-remember').checked=false;showAuthMode();}catch(error){authError(error);}});
  $('#password-toggle').onclick=()=>{const show=$('#account-password').type==='password';for(const id of ['account-password','account-confirm'])$('#'+id).type=show?'text':'password';$('#password-toggle').textContent=show?'Hide':'Show';$('#password-toggle').setAttribute('aria-label',show?'Hide password':'Show password');$('#password-toggle').setAttribute('aria-pressed',String(show));};
  $('#resend-code').onclick=async()=>{const button=$('#resend-code');button.disabled=true;try{if(Date.now()<resendAt)throw Error('Wait before requesting another code.');challenge=challenge.account_verification?{...await api.startAccountEmailVerification(),account_verification:true}:await api.resendCode(challenge.challenge_id);resendAt=Date.now()+60000;showAuthMode();}catch(error){authError(error);}finally{button.disabled=false;}};
  $('#account-form').onsubmit=async event=>{
    event.preventDefault();const button=$('#account-submit');button.disabled=true;const label=button.textContent;button.textContent='Please wait…';$('#account-error').hidden=true;$('#account-success').hidden=true;$('#account-switch').disabled=true;
    try{
      api.baseUrl=validateBackendURL($('#backend-origin').value.trim());api.sessionMode=new URL(api.baseUrl).hostname===location.hostname&&new URL(api.baseUrl).protocol===location.protocol?'cookie':'bearer';
      if(!challenge&&(authMode==='signup'||authMode==='reset')&&$('#account-password').value!==$('#account-confirm').value)throw Error('Passwords do not match.');
      if(challenge?.account_verification){profile=await api.confirmAccountEmail(challenge.challenge_id,$('#account-code').value.trim());challenge=null;authDialog.close();showWorkspace('settings');toast('Email confirmed. Secure password recovery is enabled.');return;}
      if(authMode==='forgot'){const result=await api.requestReset($('#account-email').value);success(result.message);return;}
      if(authMode==='reset'){const result=await api.resetPassword(resetToken,$('#account-password').value);resetToken='';api.clearSession();announceSessionChange();clearPrivate();mode('login');success(result.message);return;}
      const info=challenge?await api.verifyEmail(challenge.challenge_id,$('#account-code').value.trim()):authMode==='signup'?await api.register($('#account-email').value,$('#account-password').value,$('#account-name').value):await api.login($('#account-email').value,$('#account-password').value,$('#account-remember').checked);
      if(info.verification_required){challenge=info;resendAt=Date.now()+60000;$('#account-password').value='';$('#account-confirm').value='';showAuthMode();return;}
      if(profile&&profile.id!==info.user.id)clearPrivate();profile=info.user;challenge=null;$('#account-code').value='';$('#account-password').value='';$('#account-confirm').value='';
      [contentValues,integrationStatus]=await Promise.all([api.content(),api.integrations()]);
      try{localStorage.setItem('milaan-backend-origin',api.baseUrl);}catch{}
      authDialog.close();announceSessionChange();applyContent();toast('Signed in. Your private workspace is ready.');
      if(api.baseUrl===location.origin)history.replaceState(null,'','/workspace');
      if(pending==='new')await newBatch();else if(pending==='sample')await serverDemo();else showWorkspace('batches');
    }catch(error){authError(error);}
    finally{button.disabled=false;$('#account-switch').disabled=false;showAuthMode();}
  };
  async function authenticate(action='batches',requestedMode='login'){
    await ready;pending=action;
    if(api.authenticated&&requestedMode==='login'){if(action==='new')return newBatch();if(action==='sample')return serverDemo();return showWorkspace('batches');}
    mode(requestedMode);document.body.classList.add('auth-open');if(!authDialog.open)authDialog.showModal();requestAnimationFrame(()=>{const target=challenge?$('#account-code'):requestedMode==='signup'?$('#account-name'):requestedMode==='reset'?$('#account-password'):$('#account-email');target.focus();});
  }
  function restore(){
    ready=(async()=>{
      const epoch=authEpoch;
      try{
        const info=await api.restoreSession();if(epoch!==authEpoch){api.clearSession();return;}profile=info.user;
        const [restoredContent,restoredIntegrations]=await Promise.all([api.content(),api.integrations()]);if(epoch!==authEpoch)return;contentValues=restoredContent;integrationStatus=restoredIntegrations;applyContent();
        if(location.pathname==='/workspace'||location.hash==='#workspace'){
          const id=new URLSearchParams(location.search).get('batch');
          if(id){try{const b=await api.batch(id);await load(id,b.latest_run_id?'results':'imports');showWorkspace();}catch{showWorkspace('batches');toast('That saved batch is unavailable.');}}
          else showWorkspace('batches');
        }
      }catch(error){if(error.status!==401)toast('Session could not be restored. You can sign in again.');}
    })();
    ready.then(()=>{if(location.pathname==='/reset-password')authenticate('batches',resetToken?'reset':'forgot');else if(location.pathname==='/signup')authenticate('batches','signup');else if(location.pathname==='/login'&&!api.authenticated)authenticate();else if(location.pathname==='/guide')$('#help-dialog').showModal();});
    return ready;
  }
  function applyContent(){
    const name=contentValues?.branding?.value?.product_name;
    if(name){document.title=String(name)+' · Payment clarity';const el=$('.workspace-tag');if(el)el.textContent=String(name)+' · SELLER WORKSPACE';}
    let faqs=$('#workspace-faq');if(!faqs){faqs=document.createElement('section');faqs.id='workspace-faq';$('#help-dialog').append(faqs);}
    const items=contentValues?.faq?.value?.items;faqs.innerHTML=Array.isArray(items)?items.map(item=>`<details class="saved-faq"><summary>${esc(item.question)}</summary><p>${esc(item.answer)}</p></details>`).join(''):'';
  }
  async function guarded(fn){if(working)throw Error('Wait for the current server operation.');working=true;try{return await fn();}finally{working=false;}}
  async function load(id,view=getState().view){
    const epoch=authEpoch;
    const [batch,orders,claims,statements,results,events]=await Promise.all([api.batch(id),api.orders(id),api.claims(id),api.statements(id),api.results(id),api.audit(id)]);
    const allLines=[];
    for(const statement of statements.items){for(let offset=0;;offset+=500){const page=await api.statementLines(statement.id,offset);allLines.push(...page.items);if(page.items.length<500)break;}}
    if(epoch!==authEpoch||!api.authenticated)throw Error('Session changed; reload your workspace.');
    if(getState().remote?.id!==id){dispose();cache.clear();}
    const mapped=mapRemote(batch,orders.items,claims.items,statements.items,allLines,results.items,events.items);
    mapped.claims.forEach(c=>c.url=cache.get(c.id)||null);
    setState({...getState(),...mapped,view,filter:'all',reasonFilter:'',query:'',error:''});if(api.baseUrl===location.origin)history.replaceState(null,'','/workspace?batch='+encodeURIComponent(id)+'#workspace');render();return batch;
  }
  async function newBatch(){
    if(!api.authenticated)return authenticate('new');
    return guarded(async()=>{const name=prompt('Name this batch','My dispatch batch');if(!name?.trim())return;const b=await api.createBatch(name.trim());await load(b.id,'imports');showWorkspace('imports');});
  }
  async function serverDemo(){
    if(!api.authenticated)return authenticate('sample');
    return guarded(async()=>{const b=await api.demo();const j=await api.reconcile(b.id);toast('Creating your saved sample batch…');await api.waitForJob(j.id);await load(b.id,'results');showWorkspace('results');});
  }
  async function batches(){
    if(!api.authenticated){$('#app-content').innerHTML='<div class="results-panel empty-state"><h2>Sign in to open saved records.</h2><button class="btn btn-forest" data-action="account">Sign in</button></div>';return authenticate();}
    $('#app-content').innerHTML='<div class="page-intro"><h1>Your saved batches.</h1></div><p role="status">Loading your records…</p>';
    try{const data=await api.batches();if(getState().view!=='batches'||!api.authenticated)return;
      $('#app-content').innerHTML=`<div class="page-intro"><div><div class="eyebrow">YOUR CONNECTED BACKEND</div><h1>Your work, saved.</h1><p>Open a batch to continue. Inputs and review decisions stay on the server until expiry.</p></div><div class="intro-actions"><button class="btn btn-outline" data-action="server-sample">Saved sample</button><button class="btn btn-forest" data-action="new">New batch</button></div></div><div class="saved-batches">${data.items.length?data.items.map(b=>`<button class="saved-batch" data-batch-id="${esc(b.id)}"><span class="eyebrow">${b.is_demo?'SYNTHETIC SAMPLE':'YOUR RECORDS'}</span><h2>${esc(b.name)}</h2><p>Created ${new Date(b.created_at).toLocaleString()}<br>Expires ${new Date(b.expires_at).toLocaleString()}</p><strong>${b.latest_run_id?'Open results':'Continue imports'} →</strong></button>`).join(''):'<section class="import-card"><h2>A fresh start.</h2><p>Create a batch to upload your orders and statement, or try a saved sample.</p></section>'}</div>`;
    }catch(error){$('#app-content').textContent=error.message;}
  }
  async function settings(){
    if(!api.authenticated)return authenticate();
    try{[contentValues,integrationStatus]=await Promise.all([api.content(),api.integrations()]);if(getState().view!=='settings'||!api.authenticated)return;
      const fields={branding:{product_name:'Product name',tagline:'Tagline',hero_title:'Workspace welcome'},workspace:{shop_name:'Shop name'},messages:{matched:'Message after a match',review:'Message when more proof is needed'}};
      const panels=Object.entries(fields).map(([key,names])=>`<section class="import-card settings-card"><h2>${esc(key)}</h2>${Object.entries(names).map(([field,label])=>`<label class="field">${esc(label)}<textarea data-content-group="${key}" data-content-field="${field}" rows="${key==='messages'?4:2}">${esc(contentValues[key].value[field]||'')}</textarea></label>`).join('')}<button class="btn btn-forest" data-content-save="${key}">Save ${key}</button></section>`).join('');
      const faqItems=Array.isArray(contentValues.faq.value.items)?contentValues.faq.value.items:[];
      const faqPanel=`<section class="import-card settings-card"><h2>Frequently asked questions</h2>${[...faqItems, {question:'',answer:''}].map((item,i)=>`<div class="faq-edit"><label class="field">Question ${i+1}<input data-faq-question="${i}" value="${esc(item.question)}"></label><label class="field">Answer<textarea data-faq-answer="${i}" rows="3">${esc(item.answer)}</textarea></label></div>`).join('')}<p>Fill the empty pair to add a question. Clear both fields to remove one.</p><button class="btn btn-forest" data-content-save="faq">Save questions</button></section>`;
      $('#app-content').innerHTML=`<div class="page-intro"><div><div class="eyebrow">WORKSPACE SETTINGS</div><h1>Make it yours.</h1><p>Saved content is private to your seller account.</p></div></div><section class="import-card connection-info"><h2>${esc(profile.display_name)}</h2><p>${esc(api.baseUrl)}<br>Image reader: ${integrationStatus.gemini_configured&&integrationStatus.extraction_provider==='gemini'?'Gemini configured':'Manual entry · configure Gemini in the backend .env for AI reading'}<br>New batch retention: ${integrationStatus.retention_hours} hours. No live bank connection.</p>${profile.email_verified?'<p>Email confirmed · password recovery enabled.</p>':'<p>Confirm your email to enable password recovery. Existing password access is preserved.</p><button class="btn btn-outline" data-action="verify-account-email">Confirm account email</button>'}<button class="btn btn-outline" data-action="logout">Sign out</button><button class="link-button" data-action="logout-all">Sign out all devices</button></section><div class="import-grid">${panels}${faqPanel}</div>`;
    }catch(error){toast(error.message);}
  }
  async function ensureEditable(){
    const state=getState();if(!state.remote)throw Error('Open a saved batch first.');
    if(state.remote.latest_run_id){if(!await ask('Edit this batch?','This releases its current credit allocations and clears current results. Previous decisions remain in the batch audit history.','Reset and edit'))return false;
      const reason=prompt('Why are you changing the source records?','Updating source records');if(!reason||reason.trim().length<5)return false;
      await api.reset(state.remote.id,state.remote.revision,reason);await load(state.remote.id,state.view);
    }return true;
  }
  async function upload(kind,files){return guarded(async()=>{
    if(getState().claims.some(c=>c.dirty))throw Error('Save edited receipt fields before uploading more records.');
    let reviewedFile;
    const draft={coverage:{...getState().coverage},references:getState().referenceVerified,account:$('#statement-account')?.value?.trim(),orderId:$('#upload-order')?.value};
    if(kind!=='claims'){reviewedFile=await reviewImport(files[0],kind,kind==='statement'?{account:draft.account,coverage:draft.coverage}:{});if(!reviewedFile)return;}
    if(!await ensureEditable())return;
    let state=getState(),batch=state.remote;
    if(kind==='orders'){if(state.orders.length)throw Error('Orders already exist. Create another batch to replace the order CSV.');await api.uploadOrders(batch.id,reviewedFile,batch.revision);}
    else if(kind==='statement'){
      const account=draft.account;
      if(!account||!draft.coverage.start||!draft.coverage.end)throw Error('Set receiving account and actual statement period before uploading.');
      if(state.statements.some(s=>s.account_id===account))throw Error('A statement for this account already exists. Remove it before importing a replacement.');
      await api.uploadStatement(batch.id,reviewedFile,batch.revision,{account_id:account,coverage_start:draft.coverage.start,coverage_end:draft.coverage.end,complete:draft.coverage.complete,references_verified:draft.references,provider_pair:'seller-declared-profile'});
    }else{
      const order=state.orders.find(o=>o.serverId===draft.orderId);if(!order)throw Error('Choose the order these screenshots belong to first.');
      if(state.claims.length+files.length>100)throw Error('Use at most 100 screenshots per batch.');
      for(const file of files){const uploaded=await api.uploadClaim(batch.id,order.serverId,file,batch.revision);batch=uploaded.batch;toast(`Uploaded ${file.name}`);}
    }
    await load(batch.id,'imports');toast(kind==='claims'?'Saved to your backend.':'Reviewed import saved: '+(kind==='orders'?getState().orders.length:getState().lines.filter(l=>l.account===draft.account).length)+' accepted · 0 rejected.');
  });}
  async function run(){return guarded(async()=>{
    if(getState().claims.some(c=>c.dirty))throw Error('Save your edited receipt fields before reconciling.');
    if(!await ensureEditable())return;const state=getState();
    if(state.claims.some(c=>c.dirty))throw Error('Save your edited receipt fields before reconciling.');
    const job=await api.reconcile(state.remote.id);toast('Reconciliation queued…');
    await api.waitForJob(job.id,{onProgress:j=>toast(`Reconciliation: ${j.status} · ${j.progress}/${j.total}`)});
    await load(state.remote.id,'results');showWorkspace('results');
  });}
  async function read(ids){return guarded(async()=>{
    if(getState().claims.some(c=>c.dirty))throw Error('Save edited receipt fields before requesting another AI read.');
    const state=getState();if(state.mode==='demo')throw Error('Saved synthetic samples have no uploaded images.');
    if(!integrationStatus?.gemini_configured||integrationStatus.extraction_provider!=='gemini')throw Error('Configure EXTRACTION_PROVIDER, GEMINI_API_KEY and GEMINI_MODEL in the backend .env, then restart and reopen Settings. Manual entry works now.');
    if(!await ask('Read receipts with Gemini?','Pending receipt images will be sent to Google for two AI reads. Review the extracted fields before relying on them.','Send pending images'))return;
    if(!await ensureEditable())return;
    for(const id of ids){const c=getState().claims.find(c=>c.id===id);if(c&&c.extractionStatus!=='pending')await api.retryExtraction(c.id,c.version);}
    const job=await api.extract(state.remote.id,true);await api.waitForJob(job.id,{onProgress:j=>toast(`Reading: ${j.status} · ${j.progress}/${j.total}`)});
    await load(state.remote.id,'imports');toast('Reads saved. Check each receipt, including any disagreements.');
  });}
  async function saveClaim(id){return guarded(async()=>{
    const draft={...getState().claims.find(c=>c.id===id)};if(!draft.id)throw Error('Receipt missing.');
    if(!await ensureEditable())return;
    const current=getState().claims.find(c=>c.id===id);
    await api.updateClaim(id,current.version,{...draft.fields,status_text:draft.status_text||null,is_payment_receipt:draft.fields.is_payment_receipt!==false,amount_pkr:draft.amount?(draft.amount/100).toFixed(2):null,datetime_local:draft.at||null,transaction_id:draft.ref||null,sender_name:draft.name||null,unreadable_fields:draft.confirmed?[]:draft.fields.unreadable_fields||[]},draft.confirmed);
    await load(getState().remote.id,'imports');toast('Receipt fields saved.');
  });}
  async function decision(row,status,line,reason){return guarded(async()=>{await api.decide(row.matchId,row.version,status,reason,line||null);await load(getState().remote.id,'results');toast('Review decision saved.');});}
  async function image(claim){if(!claim?.hasImage)return null;if(cache.has(claim.id))return cache.get(claim.id);const url=URL.createObjectURL(await api.receiptBlob(claim.id));cache.set(claim.id,url);claim.url=url;return url;}
  function hydrate(){
    const bid=getState().remote?.id;
    document.querySelectorAll('.proof-thumbnail[data-server-image]').forEach(el=>{const claim=getState().claims.find(c=>c.id===el.dataset.serverImage);image(claim).then(url=>{if(url&&el.isConnected&&getState().remote?.id===bid)el.src=url;}).catch(()=>{el.alt='Preview unavailable; reload after signing in.';});});
  }
  async function exportResults(){const blob=await api.exportCSV(getState().remote.id);const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='milaan-reconciliation.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function edit(el){const c=getState().claims.find(c=>c.id===el.dataset.claim);if(!c)return;const field=el.dataset.claimField;
    if(['order','account'].includes(field))throw Error('Order/account links are fixed after upload. Remove and upload again against the correct order.');
    if(field==='amount'){const text=el.value.trim();if(text&&!/^\d+(?:\.\d{1,2})?$/.test(text))throw Error('Use a positive decimal PKR amount.');c.amount=text?Math.round(Number(text)*100):null;}
    else if(field==='confirmed'){if(el.checked&&(!c.amount||!c.at))throw Error('Enter a positive amount and full timestamp before confirming.');c.confirmed=el.checked;}
    else c[field]=el.value;
    if(field!=='confirmed')c.confirmed=false;c.dirty=true;
    const check=document.querySelector(`[data-claim="${c.id}"][data-claim-field="confirmed"]`);if(check)check.checked=c.confirmed;
    toast('Edited locally. Press Save receipt fields to persist.');
  }
  document.addEventListener('click',async event=>{
    const button=event.target.closest('button');if(!button)return;
    if(!button.dataset.batchId&&!button.dataset.contentSave&&!button.dataset.saveClaim&&!button.dataset.removeStatement&&!['verify-account-email','logout-all','allocation-plan','account','logout','server-sample','saved-batches','settings','refresh-batch','edit-inputs'].includes(button.dataset.action))return;
    event.preventDefault();event.stopImmediatePropagation();
    try{
      if(button.dataset.batchId)await guarded(async()=>{const b=await load(button.dataset.batchId,'results');showWorkspace(b.latest_run_id?'results':'imports');});
      else if(button.dataset.contentSave){const key=button.dataset.contentSave;const value={...contentValues[key].value};
        if(key==='faq'){value.items=[...document.querySelectorAll('[data-faq-question]')].map(el=>({question:el.value.trim(),answer:document.querySelector(`[data-faq-answer="${el.dataset.faqQuestion}"]`).value.trim()})).filter(item=>item.question||item.answer);if(value.items.some(item=>!item.question||!item.answer))throw Error('Each question needs an answer.');}
        else document.querySelectorAll(`[data-content-group="${key}"]`).forEach(el=>value[el.dataset.contentField]=el.value.trim());
        const updated=await api.saveContent(key,value,contentValues[key].version);contentValues[key]=updated;applyContent();toast('Content saved.');}
      else if(button.dataset.saveClaim)await saveClaim(button.dataset.saveClaim);
      else if(button.dataset.removeStatement)await guarded(async()=>{if(!await ensureEditable())return;const b=getState().remote;await api.deleteStatement(button.dataset.removeStatement,b.revision);await load(b.id,'imports');});
      else if(button.dataset.action==='allocation-plan'){await guarded(async()=>{const state=getState();if(!state.remote||!state.results.length)throw Error('Load saved results first.');if(await allocationDialog(state,(body,key)=>api.reviewAllocations(state.remote.id,body,key))){await load(state.remote.id,'results');toast('Reviewed allocations saved. Partial funding stays in Review.');}});}
      else if(button.dataset.action==='verify-account-email'){const info=await api.startAccountEmailVerification();if(info.email_verified){profile.email_verified=true;showWorkspace('settings');return;}challenge={...info,account_verification:true};resendAt=Date.now()+60000;showAuthMode();document.body.classList.add('auth-open');authDialog.showModal();}
      else if(button.dataset.action==='logout-all'){if(await ask('Sign out all devices?','All your current Milaan sessions will end.','Sign out all devices')){await api.logoutAll();announceSessionChange();clearPrivate();authenticate();render();}}
      else if(button.dataset.action==='logout'){if(working)throw Error('Wait for the current operation.');await api.logout();announceSessionChange();clearPrivate();authenticate();render();}
      else if(button.dataset.action==='account')authenticate();
      else if(button.dataset.action==='server-sample')await serverDemo();
      else if(button.dataset.action==='saved-batches'){if(api.authenticated)showWorkspace('batches');else authenticate();}
      else if(button.dataset.action==='settings'){if(api.authenticated)showWorkspace('settings');else authenticate();}
      else if(button.dataset.action==='refresh-batch')await guarded(()=>load(getState().remote.id));
      else if(button.dataset.action==='edit-inputs')await guarded(ensureEditable);
    }catch(error){toast(error.message);if(error.status===401)authenticate();}
  },true);
  return {api,restore,newBatch,run,read,upload,saveClaim,decision,image,hydrate,exportResults,edit,batches,settings,load,
    open(){if(api.authenticated)showWorkspace('batches');else authenticate();},
    profile:()=>profile,content:()=>contentValues,busy:()=>working,
    async remove(id){return guarded(async()=>{if(!await ensureEditable())return;const c=getState().claims.find(c=>c.id===id);await api.deleteClaim(id,c.version);const url=cache.get(id);if(url)URL.revokeObjectURL(url);cache.delete(id);await load(getState().remote.id,'imports');});},
    async clear(){return guarded(async()=>{if(!await ask('Delete this saved batch?','This permanently removes its receipts, records, results and allocations. Export first if needed.','Delete batch'))return;await api.deleteBatch(getState().remote.id);dispose();cache.clear();setState({...getState(),remote:null,orders:[],claims:[],lines:[],results:[],activity:[],view:'batches'});showWorkspace('batches');});}
  };
}
