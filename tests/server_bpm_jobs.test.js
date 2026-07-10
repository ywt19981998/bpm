const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');

test('backend exposes separate author and topic job endpoints', () => {
  assert.match(source, /\/api\/bpm-topic-jobs/);
  assert.match(source, /\/api\/bpm-author-jobs/);
});

test('backend invokes isolated Playwright modes', () => {
  assert.match(source, /"submit-topic"/);
  assert.match(source, /"submit-author"/);
});

test('worker dispatches jobs by explicit type', () => {
  assert.match(source, /job_type\s*==\s*"author"/);
  assert.match(source, /"type":\s*job_type/);
});
