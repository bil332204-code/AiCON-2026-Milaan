import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
import crypto from 'node:crypto';

async function mail(kind,email){
 let value;await expect.poll(async()=>{const text=await fs.readFile('/tmp/milaan-browser-test-outbox.jsonl','utf8').catch(()=> '');value=text.trim().split('\n').filter(Boolean).map(line=>JSON.parse(line)).filter(item=>item.kind===kind&&item.email===email).at(-1)?.value;return !!value;}).toBe(true);return value;
}
const password='synthetic-security-passphrase';
function totp(secret,offset=0){
 const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';let bits='';for(const c of secret.replace(/\s/g,''))bits+=alphabet.indexOf(c).toString(2).padStart(5,'0');
 const key=Buffer.from(bits.match(/.{8}/g).map(b=>parseInt(b,2)));const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(Math.floor(Date.now()/1000/30)+offset));
 const h=crypto.createHmac('sha1',key).update(counter).digest();const o=h[h.length-1]&15;return String((h.readUInt32BE(o)&0x7fffffff)%1000000).padStart(6,'0');
}
async function signup(page,email){
 await page.goto('/signup');await page.locator('#account-name').fill('Security Seller');await page.locator('#account-email').fill(email);
 await page.locator('#account-password').fill(password);await page.locator('#account-confirm').fill(password);await page.locator('#account-submit').click();
 await page.locator('#account-code').fill(await mail('verification',email));await page.locator('#account-submit').click();
 await expect(page.getByRole('heading',{name:"Check today's orders."})).toBeVisible();
}

test('pages run under a script CSP without violations',async({page})=>{
 const violations=[];page.on('console',m=>{if(/Content Security Policy/.test(m.text()))violations.push(m.text());});
 const response=await page.goto('/');expect(response.headers()['content-security-policy']).toContain("script-src 'self'");
 await page.goto('/guide');await page.goto('/login');
 expect(violations).toEqual([]);
});

test('two-step sign-in, data download and account deletion from Settings',async({page,browser},info)=>{
 const email=`security-${info.project.name}@example.com`;await signup(page,email);
 await page.locator('[data-action="settings"]').click();
 await page.getByRole('button',{name:'Turn on two-step sign-in'}).click();
 const secret=(await page.locator('.setup-key code').textContent()).replace(/\s/g,'');
 await page.locator('#totp-code').fill(totp(secret));await page.getByRole('button',{name:'Confirm and turn on'}).click();
 await expect(page.getByText('Two-step sign-in is on.',{exact:false}).first()).toBeVisible();
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download all my data'}).click();
 expect((await download).suggestedFilename()).toBe('milaan-my-data.json');
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await page.locator('#account-email').fill(email);await page.locator('#account-password').fill(password);await page.locator('#account-submit').click();
 await expect(page.locator('#account-heading')).toHaveText('One more step.');
 await page.locator('#account-code').fill(totp(secret,1));await page.locator('#account-submit').click();
 await expect(page.getByRole('heading',{name:"Check today's orders."})).toBeVisible();
 await page.locator('[data-action="settings"]').click();
 await page.locator('#delete-password').fill(password);await page.getByRole('button',{name:'Delete my account'}).click();
 await page.getByRole('button',{name:'Delete permanently'}).click();
 await expect(page.locator('#account-dialog')).toBeVisible();
 await page.locator('#account-email').fill(email);await page.locator('#account-password').fill(password);await page.locator('#account-submit').click();
 await expect(page.locator('#account-error')).toContainText('Incorrect email or password');
});
