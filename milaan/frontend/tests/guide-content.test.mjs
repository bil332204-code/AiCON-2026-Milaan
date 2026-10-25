import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const entry=readFileSync(new URL('../dist/index.html',import.meta.url),'utf8');
const guide=readFileSync(new URL('../dist/guide.js',import.meta.url),'utf8');

test('seller guide exposes four steps in English and Roman Urdu, with a real language toggle',()=>{
  assert.match(entry,/data-guide-language="en" aria-pressed="true"/);
  assert.match(entry,/data-guide-language="ur" aria-pressed="false"/);
  assert.match(entry,/id="guide-ur"[^>]*lang="ur-Latn" hidden/);
  for(const id of ['guide-en','guide-ur']){
    const block=entry.split('id="'+id+'"')[1].split('</section>')[0];
    assert.equal((block.match(/<li>/g)||[]).length,4);
    assert.match(block,/Transaction ID/);
    assert.match(block,/Order number/);
  }
  assert.match(guide,/button\.addEventListener\('click'/);
});

test('all local CTAs use consistent names and do not use external-link arrows',()=>{
  assert.ok((entry.match(/Try the demo/g)||[]).length>=3);
  assert.ok((entry.match(/Use your own files/g)||[]).length>=2);
  assert.doesNotMatch(entry,/Understand the limits <span>↗<\/span>/);
  assert.doesNotMatch(entry,/Use your own files <span>↗<\/span>/);
  assert.doesNotMatch(entry,/Open the demo workspace|See Milaan in action|Explore the demo/);
});

test('landing explains transaction reference source without inventing Milaan ID format',()=>{
  assert.match(entry,/Milaan does not generate it/);
  assert.match(entry,/MLN is fictional demo data, not a Milaan ID format/);
  assert.match(entry,/partial Transaction ID: REVIEW/);
  assert.match(entry,/24 hours/);
  assert.match(entry,/24 ghantay/);
  assert.doesNotMatch(entry,/Transaction ID \/ Reference number/);
});

test('private beta stays honest without removing the anonymous demo or weakening SHIP terms',()=>{
  const code=readFileSync(new URL('../dist/app.js',import.meta.url),'utf8');
  assert.match(code,/Private beta · Existing accounts only/);
  assert.match(code,/if\(action==='new'\)\{if\(privateBeta\(\)&&!backend\.api\.authenticated\)/);
  assert.match(code,/if\(await existingAccountGate\(\)\)return backend\.open\(\)/);
  assert.match(code,/new signup is closed/);
  assert.match(entry,/data-action="demo"/);
  assert.match(entry,/Statement CSV help/);
  assert.match(entry,/Statement CSV ka tareeqa/);
  assert.match(entry,/Stop shipping on screenshots alone/);
  assert.doesNotMatch(entry,/<span>09 Oct 2026<\/span>/);
  const english=entry.match(/<div class="help-limit"><b>When will Milaan automatically suggest SHIP\?<\/b>([\s\S]*?)<\/div>/)?.[1];
  const urdu=entry.match(/<div class="help-limit"><b>Automatic SHIP kab suggest hota hai\?<\/b>([\s\S]*?)<\/div>/)?.[1];
  assert.ok(english && urdu);
  for(const rule of [1,2,3,4,5,6,7,8]){assert.ok(english.includes('('+rule+')'));assert.ok(urdu.includes('('+rule+')'));}
  assert.match(english,/24 hours/);assert.match(urdu,/24 ghantay/);
  assert.match(english,/reversal\/refund/);assert.match(urdu,/refund\/reversal/);
  const recognizedStatuses = ['success','successful','completed','paid','payment successful','transaction successful'];
  for(const status of recognizedStatuses){
    assert.ok(english.includes(status), 'English status: '+status);
    assert.ok(urdu.includes(status), 'Roman Urdu status: '+status);
  }
  assert.match(english,/Milaan does not verify settlement with the bank or ship orders/);
  assert.match(urdu,/Milaan bank se payment confirm nahi karta aur order khud ship nahi karta/);
  assert.match(english,/seller confirms the sender's and receiver's Transaction IDs correspond/);
  assert.match(urdu,/seller ne sender aur receiver ke Transaction IDs ki correspondence confirm ki ho/);
});
