import test from 'node:test';
import assert from 'node:assert/strict';
import {csvCell} from '../dist/engine.js';

test('synthetic dangerous spreadsheet cells always remain text',()=>{
  for(const example of ['=1+1','+1','-1','@SUM(1)','\t+7','\r-4','  =1']){
    const exported=csvCell(example);
    assert.ok(exported.startsWith('"\''),example);
    assert.ok(exported.includes(example.replaceAll('"','""')));
  }
  assert.equal(csvCell('ordinary'),'"ordinary"');
});
