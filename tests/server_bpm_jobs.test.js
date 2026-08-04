const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');

function functionBody(name) {
  const start = source.indexOf(`def ${name}(`);
  assert.notEqual(start, -1, `${name} must exist`);
  const next = source.indexOf('\ndef ', start + 1);
  return source.slice(start, next === -1 ? source.length : next);
}

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

test('BPM jobs use authenticated server-side credentials', () => {
  const createJobBody = functionBody('create_bpm_job');
  assert.match(source, /get_integration_credentials\(user\["id"\],\s*"phei_bpm"\)/);
  assert.match(createJobBody, /trusted_payload\s*=\s*deepcopy\(payload\)/);
  assert.doesNotMatch(createJobBody, /credentials\s*=\s*payload\.get\("bpm"\)/);
  assert.match(createJobBody, /JOB_QUEUE\.put\(\(job_id,\s*job_type,\s*trusted_payload\)\)/);
});
