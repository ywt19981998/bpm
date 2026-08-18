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
const {
  applyLoggedInBpmEditor,
  ensureEditorIdentity,
  findUniqueBpmPersonLink,
  readLoggedInBpmProfile,
  selectBpmPerson,
  validateAuthorSaveEvidence,
  waitForSavedTopicLink,
} = require(scriptPath);

function fakeBpmProfilePage(name, department) {
  let triggerClicks = 0;
  const trigger = {
    async waitFor() {},
    async click() { triggerClicks += 1; },
  };
  const panel = {
    async waitFor() {},
  };
  const rows = {
    nth(index) {
      return {
        async innerText() {
          return index === 0 ? name : department;
        },
      };
    },
  };
  return {
    locator(selector) {
      if (selector === '#userInfo') return trigger;
      if (selector === '#editUserInfoPanel.show') return panel;
      if (selector === '#editUserInfoPanel .edit-user-info-operate-panel > div > div') return rows;
      throw new Error(`Unexpected selector: ${selector}`);
    },
    get triggerClicks() { return triggerClicks; },
  };
}

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

test('author maintenance opens the visible Dojo button instead of same-name hidden fields', () => {
  const body = functionBody('openAuthorMaintenancePopup');
  assert.match(body, /getByRole\('button',\s*\{\s*name:\s*'新增作译者',\s*exact:\s*true,?\s*\}\)/);
  assert.doesNotMatch(body, /input\[value="新增作译者"\]/);
  assert.match(body, /waitForEvent\('popup',\s*\{\s*timeout:\s*15000\s*\}\)/);
});

test('author maintenance requires BPM save evidence and a persisted list match', () => {
  assert.throws(
    () => validateAuthorSaveEvidence(["系统提示:【电子邮件】不允许为空，请输入内容!"], ""),
    /电子邮件/,
  );
  assert.throws(
    () => validateAuthorSaveEvidence([], ""),
    /作译者编码/,
  );
  assert.deepEqual(
    validateAuthorSaveEvidence(["作译者添加成功！"], "ZYZ20260001"),
    { authorCode: "ZYZ20260001" },
  );

  const body = functionBody('saveAuthorMaintenance');
  assert.match(body, /validateAuthorSaveEvidence/);
  assert.match(body, /verifySavedAuthorInList/);
});

test('CLI exposes isolated topic and author modes', () => {
  assert.match(source, /mode === 'submit-author'/);
  assert.match(source, /mode === 'submit-topic'/);
});

test('topic submission reports verified BPM milestones in order', () => {
  const body = functionBody('submitTopic');
  const milestones = [
    'login_verified',
    'topic_form_opened',
    'topic_draft_saved',
    'cost_estimate_saved',
    'worklist_verified',
  ];
  let previous = -1;
  for (const milestone of milestones) {
    const current = body.indexOf(`markMilestone('${milestone}')`);
    assert.ok(current > previous, `${milestone} must be recorded after the prior verified stage`);
    previous = current;
  }
  assert.match(body, /milestones:\s*\[\.\.\.milestones\]/);
  assert.match(body, /error\.bpmResult\s*=/);
  assert.match(source, /err\.bpmResult[\s\S]*JSON\.stringify\(err\.bpmResult/);
});

test('BPM profile name overrides the website display name before topic filling', async () => {
  const page = fakeBpmProfilePage('叶文涛', '高等信息科技事业部');
  const profile = await readLoggedInBpmProfile(page);
  const topic = { projectEditor: '网站注册姓名', editor: '网站注册姓名' };

  applyLoggedInBpmEditor(topic, profile);

  assert.deepEqual(profile, { name: '叶文涛', department: '高等信息科技事业部' });
  assert.equal(topic.projectEditor, '叶文涛');
  assert.equal(topic.editor, '叶文涛');
  assert.equal(page.triggerClicks, 2);

  const submitBody = functionBody('submitTopic');
  assert.ok(submitBody.indexOf('await login(page)') < submitBody.indexOf('readLoggedInBpmProfile(page)'));
  assert.ok(submitBody.indexOf('readLoggedInBpmProfile(page)') < submitBody.indexOf('openTopicPopup(page)'));
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

test('editor identity preserves BPM values or uses the person picker before save', () => {
  const identityBody = functionBody('ensureEditorIdentity');
  const ensurePersonBody = functionBody('ensureBpmPersonIdentity');
  const pickerBody = functionBody('selectBpmPerson');
  const fillBody = functionBody('fillForm');
  const saveBody = functionBody('submitTopic');
  for (const field of [
    'PRJEDITOR',
    'PRJEDITORNO',
    'PRJEDITORUID',
    'EDITOR',
    'EDITORNO',
    'EDITORUID',
  ]) {
    assert.match(identityBody, new RegExp(`input\\[name=["']${field}["']\\]`));
  }
  assert.match(identityBody, /ensureBpmPersonIdentity\([\s\S]*topic\.projectEditor[\s\S]*'策划编辑'/);
  assert.match(identityBody, /ensureBpmPersonIdentity\([\s\S]*topic\.editor[\s\S]*'拟责任编辑'/);
  assert.ok(ensurePersonBody.indexOf('readInputValue(formFrame, selector)') < ensurePersonBody.indexOf('selectPerson('));
  assert.match(ensurePersonBody, /hiddenIdSelectors[\s\S]*readInputValue/);
  assert.doesNotMatch(pickerBody, /field\.inputValue\(\).*personName/);
  assert.match(pickerBody, /verifyBpmPersonIdentity\([\s\S]*formFrame,[\s\S]*selector,[\s\S]*requiredIdSelectors/);
  assert.match(fillBody, /ensureEditorIdentity\(formFrame,\s*topic\)/);
  assert.ok(saveBody.indexOf('fillForm(formFrame, topic)') < saveBody.indexOf('clickWorkflowSaveAndWait'));
  assert.doesNotMatch(fillBody, /setReadonlyInputValue\(formFrame,\s*'input\[name="(?:PRJEDITORNO|PRJEDITORUID|EDITORNO|EDITORUID)"\]'/);
  assert.match(source, /setReadonlyInputValue\(formFrame,\s*'input\[name="PRJDEPT"\]'/);
});

test('editor identity selects only the invalid field', async () => {
  const cases = [
    {
      values: {
        'input[name="PRJEDITOR"]': '张编辑',
        'input[name="PRJEDITORNO"]': 'P1001',
        'input[name="PRJEDITORUID"]': 'zhang-editor',
        'input[name="EDITOR"]': '旧编辑',
        'input[name="EDITORNO"]': '',
        'input[name="EDITORUID"]': '',
      },
      expectedCalls: [[
        'input[name="EDITOR"]',
        ['input[name="EDITORNO"]', 'input[name="EDITORUID"]'],
        '张编辑',
        '拟责任编辑',
      ]],
    },
    {
      values: {
        'input[name="PRJEDITOR"]': '旧编辑',
        'input[name="PRJEDITORNO"]': '',
        'input[name="PRJEDITORUID"]': '',
        'input[name="EDITOR"]': '张编辑',
        'input[name="EDITORNO"]': 'E1001',
        'input[name="EDITORUID"]': 'zhang-editor',
      },
      expectedCalls: [[
        'input[name="PRJEDITOR"]',
        ['input[name="PRJEDITORNO"]', 'input[name="PRJEDITORUID"]'],
        '张编辑',
        '策划编辑',
      ]],
    },
    {
      values: {
        'input[name="PRJEDITOR"]': '张编辑',
        'input[name="PRJEDITORNO"]': 'P1001',
        'input[name="PRJEDITORUID"]': 'zhang-editor',
        'input[name="EDITOR"]': '张编辑',
        'input[name="EDITORNO"]': 'E1001',
        'input[name="EDITORUID"]': 'zhang-editor',
      },
      expectedCalls: [],
    },
    {
      values: {
        'input[name="PRJEDITOR"]': '张编辑',
        'input[name="PRJEDITORNO"]': 'P1001',
        'input[name="PRJEDITORUID"]': '',
        'input[name="EDITOR"]': '张编辑',
        'input[name="EDITORNO"]': 'E1001',
        'input[name="EDITORUID"]': 'zhang-editor',
      },
      expectedCalls: [[
        'input[name="PRJEDITOR"]',
        ['input[name="PRJEDITORNO"]', 'input[name="PRJEDITORUID"]'],
        '张编辑',
        '策划编辑',
      ]],
    },
  ];

  for (const { values, expectedCalls } of cases) {
    const calls = [];
    await ensureEditorIdentity(
      fakeInputFrame(values),
      { projectEditor: '张编辑', editor: '张编辑' },
      async (...args) => calls.push(args.slice(1)),
    );
    assert.deepEqual(calls, expectedCalls);
  }
});

test('person picker fails when BPM does not populate the hidden person ID', async () => {
  const nameSelector = 'input[name="EDITOR"]';
  const hiddenIdSelectors = ['input[name="EDITORNO"]', 'input[name="EDITORUID"]'];
  const formFrame = fakePickerFrame({
    [nameSelector]: '张编辑',
    [hiddenIdSelectors[0]]: 'E1001',
    [hiddenIdSelectors[1]]: '',
  });

  await assert.rejects(
    selectBpmPerson(formFrame, nameSelector, hiddenIdSelectors, '张编辑', '拟责任编辑'),
    /拟责任编辑.*隐藏人员 ID/,
  );
});

test('person picker fails closed for zero or multiple exact-name matches', async () => {
  await assert.rejects(
    findUniqueBpmPersonLink(fakePersonPicker(0), '张编辑', '拟责任编辑', { timeoutMs: 0 }),
    /找不到.*张编辑/,
  );
  await assert.rejects(
    findUniqueBpmPersonLink(fakePersonPicker(2), '张编辑', '拟责任编辑', { timeoutMs: 0 }),
    /多个同名结果.*人工确认/,
  );
});

test('person picker clicks the only exact-name match', async () => {
  const personLink = await findUniqueBpmPersonLink(
    fakePersonPicker(1), '张编辑', '拟责任编辑', { timeoutMs: 0 },
  );
  await personLink.click();
  assert.equal(personLink.clicked, true);
});

test('author maintenance never writes constructed contactor identifiers', () => {
  const body = functionBody('fillAuthorMaintenanceForm');
  assert.match(body, /ensureBpmPersonIdentity\(\s*formFrame,[\s\S]*CONTACTORUID/);
  assert.doesNotMatch(body, /setInputValueIfExists\(formFrame,\s*'input\[name="CONTACTORUID"\]'/);
  assert.doesNotMatch(body, /setInputValueIfExists\(formFrame,\s*'input\[name="CONTACTORDEPID"\]'/);
  assert.doesNotMatch(source, /["']yewt["']/);
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

test('cost estimate calculates and clicks only the top-level temporary-save button', () => {
  const body = functionBody('saveCostEstimateForm');
  assert.match(body, /input\[value="计算"\]/);
  assert.match(body, /input\[name="SAVEB"\]\[value="暂存"\]/);
  assert.doesNotMatch(body, /button\.x-btn-text\.save|input\[value="保存"\]/);
});

test('cost estimate success is recorded only after persisted values are verified', () => {
  const submitBody = functionBody('submitTopic');
  const saveCall = submitBody.indexOf('saveCostEstimateForm');
  const verifyCall = submitBody.indexOf('verifyCostEstimateValues');
  const milestone = submitBody.indexOf("markMilestone('cost_estimate_saved')");
  assert.ok(saveCall >= 0, 'cost estimate must use its dedicated save helper');
  assert.ok(verifyCall > saveCall, 'persisted cost values must be verified after save');
  assert.ok(milestone > verifyCall, 'success milestone must follow persisted-value verification');
});

test('saved draft lookup rescans all worklist frames until the new list appears', async () => {
  const staleFrame = createFakeWorklistFrame(['XT20260001 旧选题']);
  const freshFrame = createFakeWorklistFrame(['XT20262784 人工智能通识（应用驱动）']);
  let pollCount = 0;
  const page = {
    frames() {
      return pollCount === 0 ? [staleFrame] : [staleFrame, freshFrame];
    },
    async waitForTimeout() {
      pollCount += 1;
    },
  };

  const result = await waitForSavedTopicLink(page, {
    cno: 'XT20262784',
    bookName: '人工智能通识（应用驱动）',
    timeout: 1000,
    pollMs: 1,
  });

  assert.equal(result.frame, freshFrame);
  assert.equal(await result.link.innerText(), 'XT20262784 人工智能通识（应用驱动）');
  assert.ok(pollCount >= 1);
});

test('final BPM verification uses the resilient saved-draft lookup', () => {
  const body = functionBody('verifyCreatedTitle');
  assert.match(body, /waitForSavedTopicLink/);
});

test('cost estimate uses the fast BPM subform opener and clears temporary author data', () => {
  assert.match(source, /\bopenOtherBindReport\(/);
  assert.match(source, /clearMainAuthorFields/);
});

function createFakeWorklistFrame(titles) {
  const links = titles.map((title) => ({
    async innerText() {
      return title;
    },
    async isVisible() {
      return true;
    },
  }));

  return {
    url() {
      return 'http://bpm.example/WorkFlow_Execute_Worklist';
    },
    locator(selector) {
      assert.equal(selector, 'a');
      return {
        filter({ hasText }) {
          const matches = links.filter((link) => titles[links.indexOf(link)].includes(hasText));
          return {
            async count() {
              return matches.length;
            },
            nth(index) {
              return matches[index];
            },
          };
        },
      };
    },
  };
}

function fakeInputFrame(values) {
  return {
    locator(selector) {
      return {
        first() {
          return this;
        },
        async inputValue() {
          return values[selector] || '';
        },
      };
    },
  };
}

function fakePickerFrame(values) {
  const pickerButton = {
    first() {
      return this;
    },
    async click() {},
  };
  const row = {
    locator() {
      return pickerButton;
    },
  };
  const candidate = {
    async count() {
      return 1;
    },
    nth() {
      return this;
    },
    async click() {},
  };
  const picker = {
    async waitForLoadState() {},
    frames() {
      return [{ getByText() { return candidate; } }];
    },
    async waitForTimeout() {},
    async close() {},
  };
  const context = {
    async waitForEvent() {
      return picker;
    },
  };

  return {
    locator(selector) {
      return {
        first() {
          return this;
        },
        async inputValue() {
          return values[selector] || '';
        },
        locator() {
          return row;
        },
      };
    },
    page() {
      return { context() { return context; } };
    },
    async waitForFunction() {},
  };
}

function fakePersonPicker(matchCount) {
  const links = Array.from({ length: matchCount }, () => ({
    clicked: false,
    async click() {
      this.clicked = true;
    },
  }));
  return {
    frames() {
      return [{
        getByText() {
          return {
            async count() {
              return links.length;
            },
            nth(index) {
              return links[index];
            },
          };
        },
      }];
    },
    async waitForTimeout() {},
  };
}
