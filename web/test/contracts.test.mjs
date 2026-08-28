import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const app = await readFile(new URL('../src/App.tsx', import.meta.url), 'utf8');
const api = await readFile(new URL('../src/api.ts', import.meta.url), 'utf8');
const map = await readFile(new URL('../src/JourneyMap.tsx', import.meta.url), 'utf8');

test('claim language preserves the autonomous influence contract', () => {
  assert.match(app, /Claim main character/);
  assert.match(app, /Influence claim/);
  assert.match(app, /Autonomous controller active/);
  assert.match(app, /not a command/);
});

test('Studio client never submits direct commands or controller claims', () => {
  assert.doesNotMatch(api, /\/commands/);
  assert.doesNotMatch(api, /controller.assign|queued-actions/);
  assert.match(api, /extensions\/bunnyland\.studio/);
});

test('map supports real Leaflet geography and fictional red-line playback', () => {
  assert.match(map, /L\.map/);
  assert.match(map, /fictional-map/);
  assert.match(map, /route-completed/);
  assert.match(map, /route-detour/);
});
