const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

function functionBody(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} should exist`);
  const bodyStart = source.indexOf('{', start);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === '{') depth += 1;
    if (source[index] === '}') depth -= 1;
    if (depth === 0) return source.slice(bodyStart + 1, index);
  }
  assert.fail(`${name} should have a complete body`);
}

test('BPM view has separate topic and author buttons', () => {
  assert.match(source, /id="queueAuthor"/);
  assert.match(source, /id="queueBpm"[^>]*>.*填报选题/s);
});

test('buttons use separate backend endpoints', () => {
  assert.match(source, /apiFetch\("\/api\/bpm-author-jobs"/);
  assert.match(source, /apiFetch\("\/api\/bpm-topic-jobs"/);
});

test('author copy no longer promises automatic creation', () => {
  assert.doesNotMatch(source, /BPM 填报时会先新增作译者/);
  assert.doesNotMatch(source, /将自动准备 BPM 新增作译者数据/);
  assert.match(source, /可单独新增至 BPM 作译者库/);
});

test('job cards display the task type', () => {
  assert.match(source, /job\.type === "author"/);
  assert.match(source, /作译者维护/);
  assert.match(source, /选题填报/);
});

test('BPM queue payloads use the authenticated display name without client credentials', () => {
  const editorNameBody = functionBody('bpmEditorName');
  const currentPayloadBody = functionBody('currentBpmPayload');

  assert.match(editorNameBody, /currentUser\?\.displayName/);
  assert.doesNotMatch(currentPayloadBody, /editorName\s*:/);
  assert.doesNotMatch(currentPayloadBody, /\bbpm\s*:/);
  assert.doesNotMatch(currentPayloadBody, /password\s*:/);
  assert.doesNotMatch(source, /function currentBpmCredentials\(/);
  assert.doesNotMatch(source, /function hasBpmCredentials\(/);
});

test('queue actions require persisted BPM configuration and retain it after queueing', () => {
  assert.match(source, /let bpmCredentialConfigured = false;/);
  assert.match(source, /if \(!bpmCredentialConfigured\)/);
  assert.match(source, /请先在 BPM 配置中保存账号和密码/);
  assert.doesNotMatch(source, /document\.getElementById\("bpmPassword"\)\.value = ""/);
});

test('persistent BPM jobs use succeeded as their terminal success status', () => {
  const statusLabelBody = functionBody('jobStatusLabel');
  const statusClassBody = functionBody('jobStatusClass');

  assert.match(statusLabelBody, /succeeded:\s*"已完成"/);
  assert.doesNotMatch(statusLabelBody, /completed:/);
  assert.match(statusClassBody, /status === "succeeded"/);
  assert.doesNotMatch(statusClassBody, /status === "completed"/);
});
