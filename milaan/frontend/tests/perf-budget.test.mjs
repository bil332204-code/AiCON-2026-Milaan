import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const landing=readFileSync(new URL('../dist/landing.js',import.meta.url),'utf8');
const css=readFileSync(new URL('../dist/formal.css',import.meta.url),'utf8');

test('landing motion is light, respects reduced motion and stops when the page is hidden',()=>{
  assert.match(landing,/prefers-reduced-motion: reduce/);
  assert.match(landing,/function finalState\(\)/);
  assert.match(landing,/hover: hover\) and \(pointer: fine\)/);
  assert.match(landing,/pagehide/);
  assert.doesNotMatch(landing,/requestAnimationFrame\(draw\)/,'no endless animation loop');
  assert.doesNotMatch(landing,/<canvas|getContext\(/,'no canvas rendering');
  assert.match(css,/@media \(prefers-reduced-motion: reduce\)/);
});
