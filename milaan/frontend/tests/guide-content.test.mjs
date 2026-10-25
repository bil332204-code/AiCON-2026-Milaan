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
    assert.match(block,/Transaction ID \/ Reference number/);
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
  assert.match(entry,/Milaan does not create this number/);
  assert.match(entry,/MLN is fictional demo data, not a Milaan ID format/);
  assert.match(entry,/partial Transaction ID \/ Reference number: REVIEW/);
});
