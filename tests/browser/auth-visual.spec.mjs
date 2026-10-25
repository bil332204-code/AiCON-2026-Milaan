import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
async function mail(kind,email){
 let value;await expect.poll(async()=>{const text=await fs.readFile('/tmp/milaan-browser-test-outbox.jsonl','utf8').catch(()=> '');value=text.trim().split('\n').filter(Boolean).map(line=>JSON.parse(line)).filter(item=>item.kind===kind&&item.email===email).at(-1)?.value;return !!value;}).toBe(true);return value;
}
const password='synthetic-v3-long-passphrase';
async function signup(page,email){
 await page.goto('/signup');await expect(page.locator('#account-dialog')).toBeVisible();
 await page.locator('#account-name').fill('Synthetic V3 Seller');await page.locator('#account-email').fill(email);
 await page.locator('#account-password').fill(password);await page.locator('#account-confirm').fill(password);
 await page.locator('#account-submit').click();await expect(page.locator('#verification-fields')).toBeVisible();
 await page.locator('#account-code').fill(await mail('verification',email));await page.locator('#account-submit').click();
 await expect(page.getByRole('heading',{name:'Your work, saved.'})).toBeVisible();
}

test('independent signup, verification, refresh, recovery and private user isolation',async({page,browser},info)=>{
 const email=`v3-${info.project.name}@example.com`;
 await page.goto('/workspace');await expect(page).toHaveURL(/\/login/);
 await expect(page.locator('#account-dialog')).toBeVisible();
 expect(await page.locator('#account-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);
 await page.screenshot({path:`../../docs/screenshots/v3-auth-${info.project.name}.png`});
 await page.locator('#account-switch').click();await page.locator('#account-name').fill('Synthetic V3 Seller');
 await page.locator('#account-email').fill(email);await page.locator('#account-password').fill(password);
 await page.locator('#account-confirm').fill('different-synthetic-password');await page.locator('#account-submit').click();
 await expect(page.locator('#account-error')).toContainText('Passwords do not match');
 await page.locator('#password-toggle').click();await expect(page.locator('#account-password')).toHaveAttribute('type','text');
 await page.locator('#password-toggle').click();await page.locator('#account-confirm').fill(password);await page.locator('#account-submit').click();
 await expect(page.locator('#verification-fields')).toBeVisible();
 await page.locator('#account-code').fill(await mail('verification',email));await page.locator('#account-submit').click();
 await expect(page.getByRole('heading',{name:'Your work, saved.'})).toBeVisible();
 const cookies=await page.context().cookies();expect(cookies.find(c=>c.name==='milaan_session')?.httpOnly).toBe(true);
 expect(await page.evaluate(()=>document.cookie.includes('milaan_session'))).toBe(false);
 expect(await page.evaluate(()=>Object.keys(localStorage).some(key=>/token|password|session/i.test(key)))).toBe(false);
 const batchName=`Synthetic V3 private ${info.project.name}`;page.once('dialog',dialog=>dialog.accept(batchName));
 await page.getByRole('button',{name:'New batch',exact:true}).first().click();
 await expect(page.locator('[data-upload="orders"]')).toBeVisible();
 const batchId=new URL(page.url()).searchParams.get('batch');expect(batchId).toBeTruthy();
 await page.reload();await expect(page.locator('[data-upload="orders"]')).toBeVisible();
 const sibling=await page.context().newPage();await sibling.goto('/workspace');await expect(sibling.locator(`[data-batch-id="${batchId}"]`)).toBeVisible();
 await page.locator('[data-action="settings"]').click();await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(sibling.locator('#account-dialog')).toBeVisible();await expect(sibling.locator(`[data-batch-id="${batchId}"]`)).toHaveCount(0);await sibling.close();
 await expect(page.locator('#account-dialog')).toBeVisible();await page.locator('#forgot-password').click();
 await page.locator('#account-email').fill(email);await page.locator('#account-submit').click();await expect(page.locator('#account-success')).toContainText('check your inbox');
 const token=await mail('reset',email);
 await page.goto('/reset-password#token='+'x'.repeat(64));await page.locator('#account-password').fill('new-synthetic-v3-passphrase');await page.locator('#account-confirm').fill('new-synthetic-v3-passphrase');await page.locator('#account-submit').click();
 await expect(page.locator('#account-error')).toContainText('invalid or expired');
 await page.goto('/reset-password#token='+token);await expect(page.locator('#account-heading')).toHaveText('A fresh start.');
 await expect(page).not.toHaveURL(/#token=/);
 await page.locator('#account-password').fill('new-synthetic-v3-passphrase');await page.locator('#account-confirm').fill('new-synthetic-v3-passphrase');await page.locator('#account-submit').click();
 await expect(page.locator('#account-success')).toContainText('Password updated');
 await page.locator('#account-email').fill(email);await page.locator('#account-password').fill(password);await page.locator('#account-submit').click();await expect(page.locator('#account-error')).toBeVisible();
 await page.locator('#account-password').fill('new-synthetic-v3-passphrase');await page.locator('#account-remember').check();await page.locator('#account-submit').click();
 await expect(page.locator(`[data-batch-id="${batchId}"]`)).toBeVisible();
 const remembered=(await page.context().cookies()).find(c=>c.name==='milaan_session');expect(remembered.expires).toBeGreaterThan(Date.now()/1000+20*86400);
 const secondContext=await browser.newContext({baseURL:'http://127.0.0.1:8765',viewport:info.project.use.viewport});const second=await secondContext.newPage();
 await signup(second,`other-v3-${info.project.name}@example.com`);
 await second.goto('/workspace?batch='+batchId);await expect(second.getByRole('heading',{name:'Your work, saved.'})).toBeVisible();
 await expect(second.locator(`[data-batch-id="${batchId}"]`)).toHaveCount(0);
 await secondContext.close();
 await page.locator('[data-action="settings"]').click();await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await page.locator('#account-switch').click();await page.locator('#account-name').fill('Duplicate');await page.locator('#account-email').fill(email);await page.locator('#account-password').fill(password);await page.locator('#account-confirm').fill(password);await page.locator('#account-submit').click();
 await expect(page.locator('#account-error')).toContainText('Account cannot be created');
});

test('cinematic landing is accessible, reduced-motion safe and fits small and tablet screens',async({page},info)=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto('/');await expect(page.getByRole('heading',{level:1})).toHaveAccessibleName('Every payment. In its right place.');
 await expect(page.locator('.headline-word').last()).toHaveCSS('opacity','1');
 await page.screenshot({path:`../../docs/screenshots/v3-home-${info.project.name}.png`});
 await page.locator('#observatory-title').scrollIntoViewIfNeeded();await expect(page.locator('[data-demo-count="12"]')).toHaveText('12');
 await page.getByRole('tab',{name:/missing credit/}).click();await expect(page.locator('#scenario-stage')).toContainText('Hold');await page.keyboard.press('ArrowRight');await expect(page.getByRole('tab',{name:/reused proof/})).toHaveAttribute('aria-selected','true');await page.keyboard.press('ArrowLeft');await expect(page.locator('#scenario-stage')).toContainText('Hold');
 await page.getByRole('button',{name:'Understand the limits'}).click();await expect(page.locator('#help-dialog')).toBeVisible();await page.getByRole('button',{name:/Got it/}).click();
 await page.emulateMedia({reducedMotion:'reduce'});await page.goto('/');
 await expect(page.locator('.ambient-mesh')).toHaveCount(1);
 expect(await page.locator('.ambient-orb').first().evaluate(el=>getComputedStyle(el).animationName)).toBe('none');
 expect(await page.locator('.headline-word').first().evaluate(el=>getComputedStyle(el).opacity)).toBe('1');
 for(const width of [320,768]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.getByRole('button',{name:'Use your own files'}).click();await expect(page.locator('#account-dialog')).toBeVisible();expect(await page.locator('#account-dialog').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true);await page.locator('[data-account-close]').click();}
 const metrics=await page.evaluate(()=>({navigationMs:Math.round(performance.getEntriesByType('navigation')[0].duration),domNodes:document.querySelectorAll('*').length,resourceBytes:performance.getEntriesByType('resource').reduce((sum,r)=>sum+(r.transferSize||0),0)}));
 await fs.writeFile(`../../docs/screenshots/v3-performance-${info.project.name}.json`,JSON.stringify(metrics,null,2)+'\n');
 await test.info().attach('local-performance-observation',{body:JSON.stringify(metrics,null,2),contentType:'application/json'});
 expect(errors).toEqual([]);
});

test('legacy account confirms its email from an authenticated session before enabling recovery',async({page},info)=>{
 const email=`legacy-${info.project.name}@example.com`;
 await page.goto('/login');await page.locator('#account-email').fill(email);await page.locator('#account-password').fill('synthetic-browser-test-password');await page.locator('#account-submit').click();
 await expect(page.getByRole('heading',{name:'Your work, saved.'})).toBeVisible();
 await page.locator('[data-action="settings"]').click();await page.getByRole('button',{name:'Confirm account email',exact:true}).click();
 await expect(page.locator('#verification-fields')).toBeVisible();await page.locator('#account-code').fill(await mail('verification',email));await page.locator('#account-submit').click();
 await expect(page.locator('#account-dialog')).not.toBeVisible();await expect(page.getByText('Email confirmed · password recovery enabled.',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Sign out all devices',exact:true}).click();await page.locator('#confirm-yes').click();await expect(page.locator('#account-dialog')).toBeVisible();
});
