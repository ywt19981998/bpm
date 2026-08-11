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

test('authenticated workspace opens with a project center navigation item', () => {
  assert.match(source, /id="menuProjects"/);
  assert.match(source, /id="projectCenterView"/);
  assert.match(functionBody('showWorkspace'), /switchMainView\("projects"\)/);
});

test('project center is a compact operational table with useful columns', () => {
  for (const label of ['选题名称', '作者', '报告状态', '作译者', 'BPM 状态', '更新时间', '操作']) {
    assert.match(source, new RegExp(`<th[^>]*>${label}<\\/th>`));
  }
  assert.match(source, /id="projectSearch"/);
  assert.match(source, /id="projectStatusFilter"/);
  assert.match(source, /id="includeArchivedProjects"/);
});

test('project rendering and navigation use authenticated project APIs', () => {
  for (const name of ['loadProjects', 'renderProjectTable', 'openProject', 'createProjectFromApplication', 'archiveCurrentProject']) {
    assert.doesNotThrow(() => functionBody(name));
  }
  assert.match(functionBody('loadProjects'), /apiFetch\(`?\/api\/projects/);
  assert.match(functionBody('openProject'), /apiFetch\(`\/api\/projects\/\$\{projectId\}`/);
  assert.match(functionBody('createProjectFromApplication'), /apiFetch\("\/api\/projects"/);
  assert.doesNotMatch(functionBody('createProjectFromApplication'), /userId/);
  assert.match(functionBody('renderProjectTable'), /textContent/);
});

test('workspace has no built-in medical sample project content', () => {
  assert.doesNotMatch(source, /医学物理学/);
  assert.doesNotMatch(source, /周丽丽/);
});

