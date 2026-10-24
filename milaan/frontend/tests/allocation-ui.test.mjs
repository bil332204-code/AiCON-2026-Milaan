import test from 'node:test';
import assert from 'node:assert/strict';
import {fundingSummary} from '../dist/allocation-ui.js';
test('funding sums integer paisa and exposes partial or excess shares',()=>{
  assert.deepEqual(fundingSummary(10000,['60.00','40.00']),{paid:10000,outstanding:0,excess:0});
  assert.deepEqual(fundingSummary(10000,['60.00']),{paid:6000,outstanding:4000,excess:0});
  assert.deepEqual(fundingSummary(10000,['150.00']),{paid:15000,outstanding:0,excess:5000});
  assert.deepEqual(fundingSummary(10000,[]),{paid:0,outstanding:10000,excess:0});
  assert.throws(()=>fundingSummary(10000,['-1']));
});
