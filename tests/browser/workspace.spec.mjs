import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
const csv=(name,text)=>({name,mimeType:'text/csv',buffer:Buffer.from(text)});
async function confirmImport(page) {
  await page.locator('#preview-confirm').check();
  await page.getByRole('button',{name:'Save reviewed import',exact:true}).click();
  await expect(page.locator('.import-preview')).toHaveCount(0);
}
async function login(page) {
  await page.goto('/');
  await page.getByRole('button',{name:'Use your own files'}).click();
  await page.locator('#account-email').fill('browser@example.com');
  await page.locator('#account-password').fill('wrong-password');
  await page.locator('#account-submit').click();
  await expect(page.locator('#account-error')).toBeVisible();
  await page.locator('#account-password').fill('synthetic-browser-test-password');
  page.once('dialog',dialog=>dialog.accept('Synthetic browser batch '+Date.now()));
  await page.locator('#account-submit').click();
  await expect(page.locator('[data-upload="orders"]')).toBeVisible();
}

test('saved workspace: reviewed imports, receipt, reconciliation, human decisions, export and logout',async({page},testInfo)=>{
  const failures=[];page.on('pageerror',error=>failures.push(error.message));
  await login(page);
  const orders=csv('synthetic-orders.csv','order_ref,customer_name,amount_due,account_id\nBROWSER-1,Ali Synthetic,100,wallet');
  await page.locator('[data-upload="orders"]').setInputFiles(orders);
  await expect(page.locator('#preview-summary')).toContainText('1 accepted · 0 rejected');
  await expect(page.getByRole('button',{name:'Save reviewed import',exact:true})).toBeDisabled();
  await confirmImport(page);
  await expect(page.getByText('1 saved orders',{exact:true})).toBeVisible();
  await page.locator('#statement-account').fill('wallet');
  await page.locator('[data-coverage="start"]').fill('2026-10-09T08:00');
  await page.locator('[data-coverage="end"]').fill('2026-10-09T20:00');
  await page.locator('[data-coverage="complete"]').check();
  await page.locator('[data-coverage="references"]').check();
  const statement=csv('synthetic-bank.csv','Date,Type,Value,Reference,Person\n2026-10-09T14:00,CREDIT,100,REF-BROWSER,Ali Synthetic');
  await page.locator('[data-upload="statement"]').setInputFiles(statement);
  await expect(page.locator('#preview-summary')).toContainText('1 rejected');
  for(const [target,source] of Object.entries({posted_at:'date',direction:'type',amount:'value',transaction_id:'reference',counterparty:'person'}))await page.getByLabel('Map '+target,{exact:true}).selectOption(source);
  await expect(page.locator('#preview-summary')).toContainText('1 accepted · 0 rejected');
  await fs.mkdir('../../docs/screenshots',{recursive:true});
  await page.locator('#preview-summary').scrollIntoViewIfNeeded();
  await page.screenshot({path:`../../docs/screenshots/import-${testInfo.project.name}.png`});
  await confirmImport(page);
  await expect(page.getByText('synthetic-bank.csv · Complete period declared',{exact:true})).toBeVisible();
  await page.locator('#upload-order').selectOption({label:'BROWSER-1 · Ali Synthetic · PKR 100'});
  await page.locator('[data-upload="claims"]').setInputFiles('../../milaan/backend/samples/SYNTHETIC-receipt.jpg');
  const proof=page.locator('.proof-card');await expect(proof).toHaveCount(1);
  for(const [field,value] of Object.entries({amount:'100',ref:'REF-BROWSER',at:'2026-10-09T14:00',status_text:'Successful',name:'Ali Synthetic'}))await proof.locator(`[data-claim-field="${field}"]`).fill(value);
  await proof.locator('[data-claim-field="confirmed"]').check();
  await proof.locator('[data-save-claim]').click();
  await expect(proof.getByText(/ready/)).toBeVisible();
  await page.locator('[data-action="reconcile"]').click();
  await expect(page.locator('#results-body .pill.ship')).toHaveCount(1);
  await page.locator('#search-orders').fill('REF-BROWSER');
  await expect(page.locator('#results-body tr[data-order]')).toHaveCount(1);
  await page.locator('#discrepancy-filter').selectOption('EXACT_MATCH');
  await page.screenshot({path:`../../docs/screenshots/results-${testInfo.project.name}.png`,fullPage:true});
  await page.locator('#results-body [data-order]').last().click();
  await page.locator('#decision-reason').fill('Synthetic human requests additional evidence');
  await page.getByRole('button',{name:'Keep on hold',exact:true}).click();
  await expect(page.locator('#review-dialog')).not.toBeVisible();
  await page.locator('#results-body [data-order]').last().click();
  await page.locator('#decision-reason').fill('Synthetic human review remains necessary');
  await page.getByRole('button',{name:'Needs review',exact:true}).click();
  await expect(page.locator('#review-dialog')).not.toBeVisible();
  const downloadEvent=page.waitForEvent('download');
  await page.locator('[data-action="export"]').click();
  const download=await downloadEvent;const exported=await fs.readFile(await download.path(),'utf8');
  expect(exported).toContain('Synthetic human review remains necessary');
  await page.locator('[data-view="activity"]').click();
  await expect(page.getByRole('heading',{name:'review decision'}).first()).toBeVisible();
  if(testInfo.project.name==='mobile')expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.locator('[data-action="settings"]').click();
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await expect(page.locator('#account-dialog')).toBeVisible();
  expect(failures).toEqual([]);
});

test('preview errors, duplicate warning and cancellation never save records',async({page})=>{
  await login(page);
  const orders=csv('invalid-orders.csv','order_ref,customer_name,amount_due,account_id\nO1,Ali,100,wallet\nO2,Ali,invalid,wallet\nO1,Ali,100,wallet');
  await page.locator('[data-upload="orders"]').setInputFiles(orders);
  await expect(page.locator('#preview-summary')).toContainText('1 accepted · 2 rejected');
  await expect(page.locator('#preview-issues')).toContainText('Record 3');
  await expect(page.locator('#preview-issues')).toContainText('duplicate order');
  await page.locator('#preview-confirm').check();
  await expect(page.getByRole('button',{name:'Save reviewed import',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Cancel import',exact:true}).click();
  await expect(page.getByText('0 saved orders',{exact:true})).toBeVisible();
  await page.locator('#statement-account').fill('wallet');
  await page.locator('[data-coverage="start"]').fill('2026-10-09T08:00');
  await page.locator('[data-coverage="end"]').fill('2026-10-09T20:00');
  const repeated=csv('repeated-reference.csv','posted_at,direction,amount,transaction_id,counterparty\n2026-10-09T14:00,CREDIT,100,REF123,Ali\n2026-10-09T14:01,CREDIT,100,REF123,Ali');
  await page.locator('[data-upload="statement"]').setInputFiles(repeated);
  await expect(page.locator('#preview-summary')).toContainText('2 accepted · 0 rejected · 1 warnings');
  await expect(page.locator('#preview-issues')).toContainText('Repeated credit reference');
  await page.keyboard.press('Escape');
  await expect(page.locator('.saved-statement')).toHaveCount(0);
});

test('combined payment shares require explicit review and persist without double funding',async({page,request},testInfo)=>{
  const loginResponse=await request.post('/api/auth/login',{data:{email:'browser@example.com',password:'synthetic-browser-test-password'}});
  expect(loginResponse.ok()).toBeTruthy();
  const token=(await loginResponse.json()).access_token,headers={Authorization:'Bearer '+token},reference='COMBINED-'+testInfo.project.name.toUpperCase();
  async function post(path,data){const r=await request.post(path,{headers,data});expect(r.ok(),await r.text()).toBeTruthy();return r.json();}
  let batch=await post('/api/batches',{name:'Synthetic combined payment '+testInfo.project.name});
  const first=await post(`/api/batches/${batch.id}/orders/item`,{order_ref:'COMBINED-A',customer_name:'Synthetic Buyer A',amount_due:'100',account_id:'wallet'});batch=first.batch;
  const second=await post(`/api/batches/${batch.id}/orders/item`,{order_ref:'COMBINED-B',customer_name:'Synthetic Buyer B',amount_due:'50',account_id:'wallet'});batch=second.batch;
  const statement=await request.post(`/api/batches/${batch.id}/statement`,{headers,multipart:{
    expected_revision:String(batch.revision),account_id:'wallet',coverage_start:'2026-10-09T08:00',coverage_end:'2026-10-09T20:00',complete:'true',references_verified:'true',
    file:{name:'synthetic-combined.csv',mimeType:'text/csv',buffer:Buffer.from('posted_at,direction,amount,counterparty,transaction_id\n2026-10-09T14:00,CREDIT,150,Synthetic Payer,'+reference)}
  }});expect(statement.ok(),await statement.text()).toBeTruthy();batch=(await statement.json()).batch;
  const upload=await request.post(`/api/batches/${batch.id}/claims`,{headers,multipart:{expected_revision:String(batch.revision),order_id:first.order.id,
    file:{name:'synthetic-combined.jpg',mimeType:'image/jpeg',buffer:await fs.readFile('../../milaan/backend/samples/SYNTHETIC-receipt.jpg')}
  }});expect(upload.ok(),await upload.text()).toBeTruthy();const claim=(await upload.json()).claim;
  const checked=await request.patch(`/api/claims/${claim.id}`,{headers,data:{expected_version:claim.version,confirmed:true,fields:{is_payment_receipt:true,amount_pkr:'150',datetime_local:'2026-10-09T14:00',transaction_id:reference,status_text:'Successful'}}});expect(checked.ok(),await checked.text()).toBeTruthy();
  const jobResponse=await request.post(`/api/batches/${batch.id}/reconcile`,{headers:{...headers,'Idempotency-Key':'browser-combined-run'}});expect(jobResponse.ok()).toBeTruthy();const job=await jobResponse.json();
  await expect.poll(async()=>{const r=await request.get(`/api/jobs/${job.id}`,{headers});return (await r.json()).status;}).toBe('done');
  await page.goto('/');await page.getByRole('button',{name:'Open workspace',exact:true}).click();
  await page.locator('#account-email').fill('browser@example.com');await page.locator('#account-password').fill('synthetic-browser-test-password');await page.locator('#account-submit').click();
  await page.locator(`[data-batch-id="${batch.id}"]`).click();
  await expect(page.locator('#results-body .pill.review')).toHaveCount(2);
  await page.getByRole('button',{name:'Review payment allocations',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Review payment allocations',exact:true});
  const sections=dialog.locator('.allocation-order');await expect(sections).toHaveCount(2);
  for(const section of await sections.all()){
    const text=await section.locator('.checkbox-row').first().innerText();
    await section.locator('[data-include]').check();
    await section.locator('[data-part-line]').selectOption({index:1});
    await section.locator('[data-part-claim]').selectOption(claim.id);
    await section.locator('[data-part-amount]').fill(text.includes('COMBINED-A')?'100':'50');
  }
  await dialog.locator('#allocation-reason').fill('Synthetic payer explicitly confirmed both orders and their exact shares');
  await dialog.locator('#allocation-confirm').check();
  await dialog.locator('#allocation-save').scrollIntoViewIfNeeded();
  await page.screenshot({path:`../../docs/screenshots/allocation-${testInfo.project.name}.png`});
  await dialog.getByRole('button',{name:'Save allocation review',exact:true}).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('#results-body .pill.ship')).toHaveCount(2);
  const saved=await request.get(`/api/batches/${batch.id}/results`,{headers}),result=await saved.json();
  expect(result.items.reduce((sum,row)=>sum+row.allocated_paisa,0)).toBe(15000);
  expect(result.items.every(row=>row.machine_verdict==='review'&&row.final_status==='ship')).toBe(true);
  const downloadEvent=page.waitForEvent('download');await page.locator('[data-action="export"]').click();
  expect(await fs.readFile(await (await downloadEvent).path(),'utf8')).toContain('allocation_parts');
  if(testInfo.project.name==='mobile')expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const removed=await request.delete(`/api/batches/${batch.id}`,{headers});expect(removed.status()).toBe(204);
});
