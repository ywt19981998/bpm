const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const skillPath = path.join(
  __dirname,
  '..',
  'skills',
  'phei-bpm-topic-declaration',
  'SKILL.md',
);
const source = fs.existsSync(skillPath) ? fs.readFileSync(skillPath, 'utf8') : '';

test('skill documents separate topic and author commands', () => {
  assert.match(source, /submit-topic/);
  assert.match(source, /submit-author/);
});

test('skill makes author creation an explicit user choice', () => {
  assert.match(source, /用户.*选择.*新增作译者/);
  assert.match(source, /填报选题.*不得.*新增作译者/);
});

test('skill gives each result its own validation rule', () => {
  assert.match(source, /选题任务.*title/);
  assert.match(source, /作译者任务.*authorName/);
});
