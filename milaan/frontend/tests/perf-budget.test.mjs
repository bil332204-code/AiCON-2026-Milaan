import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const scene=readFileSync(new URL('../dist/scene.js',import.meta.url),'utf8');

test('4G/small-screen scene avoids full-density rendering while respecting motion choice',()=>{
  assert.match(scene,/const economical=matchMedia\('\(max-width: 760px\)'\)/);
  assert.match(scene,/economical\?75:135/);
  assert.match(scene,/localStorage\.setItem\('milaan-motion'/);
  assert.match(scene,/localStorage\.getItem\('milaan-motion'/);
  assert.doesNotMatch(scene,/sessionStorage\.setItem\('milaan-motion'/);
  assert.match(scene,/economical\?1\.5:2/);
  assert.match(scene,/economical\?32:25/);
  assert.match(scene,/prefers-reduced-motion/);
  assert.match(scene,/document\.hidden/);
});
