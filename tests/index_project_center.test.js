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

test('project editing serializes and autosaves versioned server state', () => {
  for (const name of ['serializeWorkspaceState', 'saveCurrentProject', 'scheduleProjectAutosave']) {
    assert.doesNotThrow(() => functionBody(name));
  }
  const saveBody = functionBody('saveCurrentProject');
  assert.match(saveBody, /method:\s*"PUT"/);
  assert.match(saveBody, /version:\s*expectedVersion/);
  assert.match(saveBody, /currentProjectVersion\s*=\s*data\.project\.version/);
  assert.match(saveBody, /response\.status === 409/);
  assert.match(saveBody, /setProjectSaveState\("conflict"\)/);
  assert.match(functionBody('scheduleProjectAutosave'), /setTimeout\([^,]+,\s*700\)/s);
  assert.match(source, /id="projectSaveStatus"/);
});

test('legacy browser drafts migrate only after project creation succeeds', () => {
  const body = functionBody('migrateLegacyDraft');
  assert.match(body, /localStorage\.getItem\(draftStorageKey\(user\)\)/);
  assert.match(body, /apiFetch\("\/api\/projects"/);
  assert.match(body, /if \(!response\.ok\)/);
  assert.ok(
    body.indexOf('localStorage.removeItem(draftStorageKey(user))') > body.indexOf('await response.json()'),
    'legacy draft removal must happen after a successful JSON response'
  );
  assert.match(body, /sourceFiles:\s*\{\s*application:\s*\{\s*missing:\s*true/s);
});

test('BPM view renders project preflight and gates topic queueing', () => {
  assert.match(source, /id="projectPreflightBody"/);
  for (const label of ['字段', '内容', '来源', '状态']) {
    assert.match(source, new RegExp(`<th[^>]*>${label}<\\/th>`));
  }
  assert.match(functionBody('loadProjectPreflight'), /`\/api\/projects\/\$\{projectId\}\/preflight`/);
  assert.match(functionBody('renderProjectPreflight'), /textContent/);
  assert.match(functionBody('renderProjectPreflight'), /queueBpm\.disabled\s*=\s*!currentProjectPreflight\.ready/);
});
