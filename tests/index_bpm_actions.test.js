const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

test('BPM view has separate topic and author buttons', () => {
  assert.match(source, /id="queueAuthor"/);
  assert.match(source, /id="queueBpm"[^>]*>.*填报选题/s);
});

test('buttons use separate backend endpoints', () => {
  assert.match(source, /fetch\("\/api\/bpm-author-jobs"/);
  assert.match(source, /fetch\("\/api\/bpm-topic-jobs"/);
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
