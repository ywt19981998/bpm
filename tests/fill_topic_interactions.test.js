const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const scriptPath = path.join(
  __dirname,
  '..',
  'skills',
  'phei-bpm-topic-declaration',
  'scripts',
  'fill_topic.js',
);
const source = fs.readFileSync(scriptPath, 'utf8');

function functionBody(name) {
  const start = source.indexOf(`async function ${name}(`);
  assert.notEqual(start, -1, `${name} must exist`);
  const next = source.indexOf('\nasync function ', start + 1);
  return source.slice(start, next === -1 ? source.length : next);
}

test('submitTopic never maintains authors', () => {
  const body = functionBody('submitTopic');
  assert.doesNotMatch(body, /saveAuthorMaintenance/);
  assert.match(body, /openTopicPopup/);
  assert.match(body, /fillScoreGrid/);
  assert.match(body, /fillCostEstimateForm/);
});

test('submitAuthor only maintains authors', () => {
  const body = functionBody('submitAuthor');
  assert.match(body, /saveAuthorMaintenance/);
  assert.doesNotMatch(body, /openTopicPopup|fillScoreGrid|fillCostEstimateForm/);
});

test('CLI exposes isolated topic and author modes', () => {
  assert.match(source, /mode === 'submit-author'/);
  assert.match(source, /mode === 'submit-topic'/);
});

test('BPM form changes use Playwright controls instead of direct DOM or Ext mutation', () => {
  assert.match(source, /\.fill\(/);
});

test('BPM selects use Playwright selection and blur so legacy listeners run', () => {
  assert.match(source, /\.selectOption\(/);
  assert.match(source, /if\s*\(await locator\.isVisible\(\)\)/);
  assert.match(source, /setHiddenSelectValue/);
  assert.match(source, /\.press\('Tab'\)/);
});

test('readonly BPM inputs use the fast targeted setter', () => {
  assert.match(source, /\.isEditable\(\)/);
  assert.match(source, /setReadonlyInputValue\(frame,\s*selector,\s*desired\)/);
  assert.match(source, /if\s*\(!visible\)/);
  assert.doesNotMatch(source, /Cannot change readonly BPM control/);
});

test('BPM choices click visible labels and directly set hidden required choices', () => {
  assert.match(source, /locator\('label',\s*\{\s*has:\s*target\s*\}\)/);
  assert.match(source, /if\s*\(!\(await label\.isVisible\(\)\)\)/);
  assert.match(source, /setHiddenChoiceValue/);
  assert.match(source, /label\.click\(\)/);
});

test('readonly editor metadata uses the fast targeted setter', () => {
  assert.match(source, /setReadonlyInputValue\(formFrame,\s*'input\[name="PRJEDITOR"\]'/);
  assert.match(source, /setReadonlyInputValue\(formFrame,\s*'input\[name="EDITOR"\]'/);
  assert.match(source, /setReadonlyInputValue\(formFrame,\s*'input\[name="PRJDEPT"\]'/);
});

test('score grid updates Ext records and clicks its own save button', () => {
  assert.match(source, /\brecord\.set\(/);
  assert.match(source, /grid\.getByRole\('button',\s*\{\s*name:\s*'保存'/);
  assert.match(source, /fillScoreGrid\(reopened\.formFrame,\s*topic\)/);
  assert.ok(
    source.indexOf("grid.getByRole('button', { name: '保存'")
      < source.indexOf("setReadonlyInputValue(frame, '#SCORE'"),
  );
});

test('book name is not redundantly retyped after the score grid masks the form', () => {
  assert.doesNotMatch(source, /typeTextLikeUser\(formFrame,\s*'input\[name="BOOKNAME"\]'/);
});

test('BPM draft save clicks the visible temporary-save button', () => {
  assert.doesNotMatch(source, /\bsaveFormData\(\)/);
  assert.match(source, /input\[name="SAVEB"\]/);
  assert.match(source, /\.click\(\)/);
  assert.match(source, /正在提交数据/);
  assert.match(source, /waitForMainFormFrame\(popup\)/);
});

test('cost estimate reopens the saved draft instead of reusing the post-save frame', () => {
  assert.match(source, /reopenSavedTopicPopup/);
  assert.match(source, /await popup\.close\(\)/);
});

test('cost estimate uses the fast BPM subform opener and clears temporary author data', () => {
  assert.match(source, /\bopenOtherBindReport\(/);
  assert.match(source, /clearMainAuthorFields/);
});
