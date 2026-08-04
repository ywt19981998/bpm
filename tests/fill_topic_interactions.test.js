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
  ensureEditorIdentity,
  findUniqueBpmPersonLink,
  selectBpmPerson,
  waitForSavedTopicLink,
} = require(scriptPath);

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
