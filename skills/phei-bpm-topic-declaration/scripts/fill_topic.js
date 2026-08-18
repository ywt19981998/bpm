const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const DEFAULT_URL = process.env.BPM_URL || 'http://bpm.phei.com.cn:8088/portal/index.jsp';

function loadInput(jsonPath) {
  const absPath = path.resolve(jsonPath);
  const raw = fs.readFileSync(absPath, 'utf8');
  const parsed = JSON.parse(raw);
  return { absPath, data: parsed };
}

function deepMerge(base, override) {
  const merged = { ...base };
  Object.entries(override || {}).forEach(([key, value]) => {
    if (
      value
      && typeof value === 'object'
      && !Array.isArray(value)
      && base[key]
      && typeof base[key] === 'object'
      && !Array.isArray(base[key])
    ) {
      merged[key] = deepMerge(base[key], value);
    } else {
      merged[key] = value;
    }
  });
  return merged;
}

function withDefaults(data) {
  const defaults = {
    type: '本版',
    class1: '02',
    class2: '0201',
    class3: '020101',
    class4: '02010103',
    gbClass: 'G',
    readLevel: '高等理工',
    haveReplaceBsn: '无',
    replaceBsn: '0000',
    authorCode: '',
    authorName: '',
    authorId: '',
    authorMaintenance: {
      enabled: false,
      type: '个人',
      name: '',
      contactor: '叶文涛',
      gender: '',
      certificateType: '其他',
      certificateNo: '　',
      title: '　',
      education: '　',
      major: '　',
      graduateSchool: '　',
      workUnit: '　',
      unitAddress: '　',
      unitZip: '　',
      unitContactor: '　',
      unitFax: '　',
      phone1: '　',
      phone2: '　',
      fax: '　',
      email: '　',
      postalCode: '　',
      address: '　',
      workResume: '　',
      academicOrganizations: '　',
      researchProjects: '　',
      awards: '　',
      writingDirection: '　',
      publications: '　',
      bio: '　',
      bioStatus: '待补全失败',
    },
    readerNum: '100',
    language: '中文',
    scriptSource: '作者独立投稿',
    scriptStyle: '电子文件',
    awards: '无',
    colorPrint: '单色',
    haveCd: '',
    words: '350.00',
    price: '59.8',
    remCharNum: '0',
    remPayMode: '销数版税',
    remStandard: '8',
    remUnit: '2',
    publishMode: '常规出版',
    haveZz: '否',
    imburseFee: '0',
    imburseNum: '0',
    haveBx: '否',
    bsaleNum: '0',
    bsaleDiscount: '0',
    coMode: '',
    coBuyDiscount: '0',
    bsaleMode: '',
    digital: '授权',
    eRemPayMode: '是',
    eRemStandard: '8',
    totalNum: '3000',
    firstNum: '1200',
    project: '无',
    scriptClassify: '普通选题',
    projectEditor: '叶文涛',
    projectEditorNo: '',
    projectEditorUid: '',
    editor: '叶文涛',
    editorNo: '',
    editorUid: '',
    projectDept: '高等教育出版分社/高等信息科技事业部',
    editorDept: '高等教育出版分社/高等信息科技事业部',
    isCost: '1',
    impScript: '否',
    isUrgent: '普通',
    isMeeting: '否',
    bwClass: '计算机',
    bwCipClass: 'TP',
    costDefaults: {
      category: '教育',
      edition: '本版',
      copyrightWords: '350.00',
      paidWords: '0.00',
      remunerationMode: '销数版税',
      remunerationRate: '8%',
      editUnitPrice: '6.50',
      proofUnitPrice: '1.00',
      thirdProofUnitPrice: '1.50',
      finalReviewUnitPrice: '0.00',
      typesettingUnitPrice: '11.50',
      coverUnitPrice: '800.00',
      containsDisc: '无',
      electronicFileFee: '0.00',
      otherPrepressFee: '0.00',
      imageFee: '0.00',
      discDevelopmentFee: '0.00',
      printing: {
        sheets: '14.000',
        printRun: '1200',
        floatingPrintRun: '200',
        pageCount: '224',
        totalImpressions: '1',
        accumulatedPrintRun: '3000',
        unitPrice: '59.80',
        binding: '平装覆膜',
        formatSize: '16(185*260)',
        textPaperSpec: '787*1092',
        textPaperName: '胶版',
        textPaperWeight: '70克',
        textPaperClass: 'J70787',
        textPrintColors: '1',
        textPlateMaking: 'CTP制版',
        textPrintingMode: '对开',
        ctpProofPages: '0',
        coverPaperName: '铜版',
        coverPaperWeight: '200克',
        coverPaperClass: 'T200889',
        coverPrintColors: '4',
        coverFinish: '亚膜',
        coverPlateMaking: 'CTP制版',
        coverPrintingMode: '对开',
        colorInsertSheets: '0.000',
        blackInsertSheets: '0.000',
        coverFlap: '无',
        addEndpaper: '无',
        endpaperClass: 'J140787',
        addDustJacket: '无',
        addBellyBand: '无',
      },
      sales: {
        deliveryCopies: '1020.0',
        saleCopies: '816.00',
        totalDeliveryCopies: '2550.0',
        totalSaleCopies: '2040.00',
        productionDeliveryRate: '85.00',
        subsidy: '否',
        subsidyAmount: '0',
        complimentaryCopies: '0',
        guaranteedSale: '否',
        guaranteedSaleCopies: '0',
        guaranteedSaleDiscount: '0.00',
        returnRate: '20.00',
        deliveryDiscount: '65.00',
        storageTransportRate: '6.00',
        managementFee: '7500.00',
        salesCycleYears: '3',
      },
    },
  };
  const merged = {
    ...deepMerge(defaults, data),
    class1: '02',
    class2: '0201',
    gbClass: 'G',
    readLevel: '高等理工',
  };
  if (merged.editorName && !data.projectEditor) merged.projectEditor = merged.editorName;
  if (merged.editorName && !data.editor) merged.editor = merged.editorName;
  if (merged.authorMaintenance) {
    if (!merged.authorMaintenance.name) merged.authorMaintenance.name = merged.authorName;
    if (!merged.authorMaintenance.contactor) merged.authorMaintenance.contactor = merged.projectEditor;
    if (!data.authorMaintenance || data.authorMaintenance.enabled === undefined) {
      merged.authorMaintenance.enabled = Boolean(merged.authorMaintenance.name);
    }
  }
  return merged;
}

function isValidPersonName(value) {
  const text = String(value || '').trim();
  return /^[\u4e00-\u9fff·]{2,8}$/.test(text);
}

async function setInputValue(frame, selector, value) {
  const locator = frame.locator(selector).first();
  await locator.waitFor({ state: 'attached', timeout: 10000 });
  const desired = String(value ?? '');
  if (!(await locator.isEditable())) {
    await setReadonlyInputValue(frame, selector, desired);
    return;
  }
  const visible = await locator.isVisible().catch(() => false);
  if (!visible) {
    await setReadonlyInputValue(frame, selector, desired);
    return;
  }
  await locator.click();
  await locator.fill(desired);
  await locator.press('Tab');
}

async function setReadonlyInputValue(frame, selector, value) {
  const locator = frame.locator(selector).first();
  if (!(await locator.count()) || value === undefined || value === null) return;
  await locator.evaluate((el, nextValue) => {
    el.value = nextValue;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, String(value));
}

async function setInputValueIfExists(frame, selector, value) {
  if (value === undefined || value === null) return;
  const locator = frame.locator(selector);
  if (await locator.count()) {
    await setInputValue(frame, selector, value);
  }
}

async function typeTextLikeUser(frame, selector, value) {
  if (value === undefined || value === null) return;
  const locator = frame.locator(selector).first();
  await locator.waitFor({ state: 'visible', timeout: 10000 });
  await locator.click();
  await locator.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A');
  await locator.pressSequentially(String(value), { delay: 20 });
  await locator.press('Tab');
}

async function selectOptionIfExists(frame, selector, value) {
  if (value === undefined || value === null) return;
  const locator = frame.locator(selector);
  if (await locator.count()) {
    await selectOptionWhenReady(frame, selector, value, { required: false, timeout: 2000 });
  }
}

async function getSelectOptions(locator) {
  return await locator.evaluate((el) => Array.from(el.options || []).map((option) => ({
    value: option.value,
    text: option.textContent.trim(),
  })));
}

async function setHiddenSelectValue(locator, value) {
  await locator.evaluate((el, nextValue) => {
    el.value = nextValue;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, value);
}

async function selectOptionWhenReady(frame, selector, value, options = {}) {
  const {
    required = true,
    fallback = false,
    timeout = 15000,
    settleMs = 500,
  } = options;

  if (value === undefined || value === null || value === '') return null;

  const locator = frame.locator(selector).first();
  if (!(await locator.count())) {
    if (required) throw new Error(`Select not found: ${selector}`);
    return null;
  }

  await locator.waitFor({ state: 'attached', timeout: 30000 });
  const expected = String(value).trim();
  const deadline = Date.now() + timeout;
  let choices = [];
  let match = null;

  while (Date.now() <= deadline) {
    choices = await getSelectOptions(locator);
    match = choices.find((choice) => choice.value === expected)
      || choices.find((choice) => choice.text === expected);
    if (match) break;
    await frame.waitForTimeout(500);
  }

  if (!match && fallback) {
    match = choices.find((choice) => choice.value && !/请选择|请\s*选择/.test(choice.text))
      || choices.find((choice) => choice.value);
    if (match) {
      console.warn(`Select fallback ${selector}: wanted "${expected}", using "${match.value || match.text}" (${match.text})`);
    }
  }

  if (!match) {
    const available = choices.map((choice) => `${choice.value}:${choice.text}`).join(' | ');
    if (required) {
      throw new Error(`Option not found for ${selector}: "${expected}". Available options: ${available || '(none)'}`);
    }
    return null;
  }

  if (await locator.isVisible()) {
    await locator.selectOption({ value: match.value });
    await locator.press('Tab');
  } else {
    await setHiddenSelectValue(locator, match.value);
  }
  if (settleMs) await frame.waitForTimeout(settleMs);
  return match;
}

async function setHiddenChoiceValue(target) {
  await target.evaluate((el) => {
    el.checked = true;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

async function setRadioValue(frame, name, value) {
  if (value === undefined || value === null || value === '') return;
  const candidates = frame.locator(`input[name="${name}"]`);
  const values = await candidates.evaluateAll((elements) => elements.map((el) => el.getAttribute('value') || ''));
  const target = frame.locator(`input[name="${name}"][value=${JSON.stringify(String(value))}]`);
  if (!(await target.count())) {
    throw new Error(`Choice not found for ${name}: "${value}". Available options: ${values.join(', ')}`);
  }
  if (await target.first().isChecked()) return;
  const label = frame.locator('label', { has: target }).first();
  if (!(await label.isVisible())) {
    await setHiddenChoiceValue(target.first());
    return;
  }
  await label.click();
  if (!(await target.first().isChecked())) {
    throw new Error(`Visible label did not select ${name}: "${value}"`);
  }
}

async function verifyBpmPersonIdentity(
  formFrame,
  selector,
  hiddenIdSelectors,
  personName,
  fieldLabel,
) {
  const requiredIdSelectors = Array.isArray(hiddenIdSelectors) ? hiddenIdSelectors : [hiddenIdSelectors];
  const selectedName = await readInputValue(formFrame, selector);
  const selectedIds = await Promise.all(
    requiredIdSelectors.map((idSelector) => readInputValue(formFrame, idSelector)),
  );
  if (selectedName !== personName) {
    throw new Error(`${fieldLabel}选择后姓名不匹配：期望“${personName}”，实际“${selectedName || '空'}”。`);
  }
  const missingSelectors = requiredIdSelectors.filter((_, index) => (
    !String(selectedIds[index] || '').trim()
  ));
  if (missingSelectors.length) {
    throw new Error(`${fieldLabel}选择后缺少隐藏人员 ID：${missingSelectors.join(', ')}。`);
  }
}

async function findUniqueBpmPersonLink(picker, personName, fieldLabel, options = {}) {
  const deadline = Date.now() + (options.timeoutMs ?? 30000);
  do {
    const matches = [];
    for (const pickerFrame of picker.frames()) {
      const candidate = pickerFrame.getByText(personName, { exact: true });
      const count = await candidate.count();
      for (let index = 0; index < count; index += 1) {
        matches.push(candidate.nth(index));
      }
    }
    if (matches.length === 1) return matches[0];
    if (matches.length > 1) {
      throw new Error(`${fieldLabel}人员选择器找到多个同名结果“${personName}”，需要人工确认或提供更精确识别。`);
    }
    if (Date.now() >= deadline) break;
    await picker.waitForTimeout(options.pollMs ?? 500);
  } while (Date.now() < deadline);
  throw new Error(`${fieldLabel}人员选择器找不到“${personName}”，需要人工确认或提供更精确识别。`);
}

async function selectBpmPerson(formFrame, selector, hiddenIdSelectors, personName, fieldLabel) {
  if (!personName) return;
  const requiredIdSelectors = Array.isArray(hiddenIdSelectors) ? hiddenIdSelectors : [hiddenIdSelectors];
  const field = formFrame.locator(selector).first();

  const row = field.locator('xpath=ancestor::tr[1]');
  const pickerButton = row.locator('input[type="button"][title="弹出选择窗口"]').first();
  const context = formFrame.page().context();
  const pickerPromise = context.waitForEvent('page', { timeout: 15000 });
  await pickerButton.click();
  const picker = await pickerPromise;
  await picker.waitForLoadState('domcontentloaded');

  let personLink = null;
  try {
    personLink = await findUniqueBpmPersonLink(picker, personName, fieldLabel);
  } catch (error) {
    await picker.close().catch(() => {});
    throw error;
  }

  try {
    await personLink.click();
    await formFrame.waitForFunction(
      ({ fieldSelector, requiredSelectors, expected }) => (
        document.querySelector(fieldSelector)?.value === expected
        && requiredSelectors.every((idSelector) => (
          String(document.querySelector(idSelector)?.value || '').trim()
        ))
      ),
      { fieldSelector: selector, requiredSelectors: requiredIdSelectors, expected: personName },
      { timeout: 15000 },
    ).catch(() => {});
    await verifyBpmPersonIdentity(
      formFrame,
      selector,
      requiredIdSelectors,
      personName,
      fieldLabel,
    );
  } finally {
    await picker.close().catch(() => {});
  }
}

async function ensureBpmPersonIdentity(
  formFrame,
  selector,
  hiddenIdSelectors,
  personName,
  fieldLabel,
  selectPerson = selectBpmPerson,
) {
  const requiredIdSelectors = Array.isArray(hiddenIdSelectors) ? hiddenIdSelectors : [hiddenIdSelectors];
  const currentName = await readInputValue(formFrame, selector);
  const currentIds = await Promise.all(
    requiredIdSelectors.map((idSelector) => readInputValue(formFrame, idSelector)),
  );
  if (
    currentName === personName
    && currentIds.every((currentId) => String(currentId || '').trim())
  ) return;
  await selectPerson(formFrame, selector, requiredIdSelectors, personName, fieldLabel);
}

async function ensureEditorIdentity(formFrame, topic, selectPerson = selectBpmPerson) {
  await ensureBpmPersonIdentity(
    formFrame,
    'input[name="PRJEDITOR"]',
    ['input[name="PRJEDITORNO"]', 'input[name="PRJEDITORUID"]'],
    topic.projectEditor,
    '策划编辑',
    selectPerson,
  );
  await ensureBpmPersonIdentity(
    formFrame,
    'input[name="EDITOR"]',
    ['input[name="EDITORNO"]', 'input[name="EDITORUID"]'],
    topic.editor,
    '拟责任编辑',
    selectPerson,
  );
}

async function expandDepartmentNode(departmentFrame, nodeText) {
  const node = departmentFrame.getByText(nodeText, { exact: true });
  await node.waitFor({ state: 'visible', timeout: 15000 });
  const nodeRow = node.locator('xpath=ancestor::div[contains(@class,"x-tree-node-el")][1]');
  const expandButton = nodeRow.locator('.x-tree-ec-icon[class*="-plus"]');
  if (await expandButton.count()) {
    await expandButton.click();
    await departmentFrame.waitForTimeout(1000);
  }
}

async function selectDepartmentWithPicker(formFrame, departmentPath) {
  if (!departmentPath) return;
  const departmentName = departmentPath.split('/').pop();
  const field = formFrame.locator('input[name="PRJDEPT"]').first();
  if ((await field.inputValue()).includes(departmentName)) return;

  const row = field.locator('xpath=ancestor::tr[1]');
  const pickerButton = row.locator('input[type="button"][title="弹出选择窗口"]').first();
  await pickerButton.click();
  const popup = formFrame.page();
  let departmentFrame = null;
  const deadline = Date.now() + 30000;
  while (!departmentFrame && Date.now() < deadline) {
    departmentFrame = popup.frames().find((frame) => frame.url().includes('Dictionary_Department_Tree'));
    if (!departmentFrame) await popup.waitForTimeout(500);
  }
  if (!departmentFrame) {
    throw new Error('BPM department picker frame did not load');
  }

  await expandDepartmentNode(departmentFrame, '电子工业出版社');
  await expandDepartmentNode(departmentFrame, '社领导');
  const pathParts = departmentPath.split('/');
  for (const pathPart of pathParts.slice(0, -1)) {
    await expandDepartmentNode(departmentFrame, pathPart);
  }
  const departmentNode = departmentFrame.getByText(departmentName, { exact: true });
  await departmentNode.waitFor({ state: 'visible', timeout: 15000 });
  await departmentNode.click();
  await formFrame.waitForFunction(
    ({ expected }) => document.querySelector('input[name="PRJDEPT"]')?.value.includes(expected),
    { expected: departmentName },
    { timeout: 15000 },
  );
}

function scoreMap(topic) {
  return {
    '选题内容': Number(topic.scoreContent || 0),
    '作者情况': Number(topic.scoreAuthor || 0),
    '策划过程与可行性': Number(topic.scoreFeasibility || 0),
    '获奖潜质': Number(topic.scoreAward || 0),
    '成本与盈利估算': Number(topic.scoreProfit || 0),
    '市场定位与营销': Number(topic.scoreMarketing || 0),
  };
}

async function fillScoreGrid(frame, topic) {
  const scores = scoreMap(topic);
  const total = Number(topic.scoreTotal || Object.values(scores).reduce((sum, value) => sum + Number(value || 0), 0));

  const grid = frame.locator('#ext-comp-1022');
  await grid.locator('.ext-el-mask-msg').waitFor({ state: 'hidden', timeout: 30000 }).catch(() => {});
  const rows = grid.locator('.x-grid3-body .x-grid3-row');
  const deadline = Date.now() + 30000;
  while ((await rows.count()) < 7 && Date.now() < deadline) {
    await frame.waitForTimeout(500);
  }
  if ((await rows.count()) < 7) {
    throw new Error(`Score grid did not finish loading; found ${await rows.count()} rows`);
  }

  await frame.evaluate(({ scoreValues, totalScore }) => {
    const scoreGrid = window.Ext && Ext.getCmp ? Ext.getCmp('ext-comp-1022') : null;
    if (!scoreGrid || !scoreGrid.getStore) throw new Error('Score grid store is unavailable');
    scoreGrid.getStore().each((record) => {
      const item = String(record.get('ITEM') || '');
      if (item.includes('总分')) {
        record.set('SELFSCORE', totalScore);
        return;
      }
      const scoreName = Object.keys(scoreValues).find((name) => item.includes(name));
      if (scoreName) record.set('SELFSCORE', Number(scoreValues[scoreName] || 0));
    });
    if (scoreGrid.getView) scoreGrid.getView().refresh();
  }, { scoreValues: scores, totalScore: total });

  await grid.getByRole('button', { name: '保存', exact: true }).click();
  await grid.locator('.ext-el-mask-msg').waitFor({ state: 'hidden', timeout: 5000 }).catch(() => {});
  await setReadonlyInputValue(frame, '#SCORE', String(total));
  await frame.waitForTimeout(1000);
}

async function clickWorkflowSaveAndWait(popup, formFrame, { timeout = 30000, settleMs = 1000 } = {}) {
  const saveButton = popup.locator('input[name="SAVEB"][value="暂存"]').first();
  await saveButton.waitFor({ state: 'visible', timeout: 10000 });
  await saveButton.click();
  const submitMask = formFrame.getByText(/正在提交数据/).first();
  const maskAppeared = await submitMask.waitFor({ state: 'visible', timeout: 5000 })
    .then(() => true)
    .catch(() => false);
  if (maskAppeared) {
    await submitMask.waitFor({ state: 'hidden', timeout: 60000 });
  }
  await formFrame.locator('#BOOKNAME').waitFor({ state: 'attached', timeout }).catch(() => {});
  await popup.waitForTimeout(settleMs);
}

async function waitForMainFormFrame(popup, timeout = 15000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    for (const frame of popup.frames()) {
      if (await frame.locator('#BOOKNAME').count().catch(() => 0)) return frame;
    }
    await popup.waitForTimeout(300);
  }
  throw new Error('Main BPM form frame did not reload after temporary save');
}

async function waitForCostFrame(popup, maxAttempts = 40) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    await popup.waitForTimeout(500);
    for (const frame of popup.frames()) {
      if (await frame.locator('input[name="UNITNUM"]').count().catch(() => 0)) {
        await frame.locator('input[name="UNITNUM"]').waitFor({ state: 'attached', timeout: 5000 });
        return frame;
      }
    }
  }
  return null;
}

async function triggerCostEstimateForm(formFrame) {
  await formFrame.evaluate(() => {
    if (typeof openOtherBindReport !== 'function') {
      throw new Error('openOtherBindReport is not available');
    }
    openOtherBindReport(frmMain, 'WorkFlow_Execute_Worklist_SubBindReport_Open', 1829);
  });
}

async function clearMainAuthorFields(formFrame) {
  await setReadonlyInputValue(formFrame, 'input[name="AUTHORCODE"]', '');
  await setReadonlyInputValue(formFrame, 'input[name="AUTHORID"]', '');
  await setReadonlyInputValue(formFrame, 'input[name="AUTHORNAME"]', '');
}

async function openCostEstimateForm(popup, formFrame, topic = {}) {
  if (topic.authorName) {
    await setReadonlyInputValue(formFrame, 'input[name="AUTHORNAME"]', topic.authorName);
  }
  const costTab = formFrame.locator('a', { hasText: '成本估算' }).first();
  if (await costTab.count()) {
    await costTab.click({ force: true });
    await formFrame.waitForTimeout(500);
  }
  await triggerCostEstimateForm(formFrame);
  const costFrame = await waitForCostFrame(popup, 40);
  await clearMainAuthorFields(formFrame);
  if (costFrame) return costFrame;

  const frameUrls = popup.frames().map((frame) => frame.url()).join(' | ');
  throw new Error(`Cost estimate form did not load. Frames: ${frameUrls}`);
}

async function fillCostEstimateForm(costFrame, topic) {
  const cost = topic.costDefaults || {};
  const printing = cost.printing || {};
  const sales = cost.sales || {};
  const choose = async (selector, value, settleMs = 500) => {
    await selectOptionWhenReady(costFrame, selector, value, {
      required: false,
      fallback: false,
      timeout: 12000,
      settleMs,
    });
  };

  await setInputValueIfExists(costFrame, 'input[name="REMCHARNUM"]', cost.paidWords);
  await setInputValueIfExists(costFrame, 'input[name="REMPAYMODE"]', '销数版税');
  await choose('select[name="CRPAYMODE"]', '销数版税');
  await setInputValueIfExists(costFrame, 'input[name="REMSTANDARD"]', '8');
  await choose('select[name="REMUNIT"]', '2');
  await setInputValueIfExists(costFrame, 'input[name="BJSTANDARD"]', cost.editUnitPrice);
  await setInputValueIfExists(costFrame, 'input[name="JDSTANDARD"]', cost.proofUnitPrice);
  await setInputValueIfExists(costFrame, 'input[name="SJSTANDARD"]', cost.thirdProofUnitPrice);
  await setInputValueIfExists(costFrame, 'input[name="FSTANDARD"]', cost.finalReviewUnitPrice || '0.00');
  await setInputValueIfExists(costFrame, 'input[name="SCRIPTSTANDARD"]', cost.typesettingUnitPrice);
  await setInputValueIfExists(costFrame, 'input[name="COVERSTANDARD"]', cost.coverUnitPrice);
  await choose('select[name="HAVEDISK"]', cost.containsDisc);
  await setInputValueIfExists(costFrame, 'input[name="DISKNUM"]', '0');
  await setInputValueIfExists(costFrame, 'input[name="DOCFEE"]', cost.electronicFileFee);
  await setInputValueIfExists(costFrame, 'input[name="OTHERFEE1"]', cost.otherPrepressFee);
  await setInputValueIfExists(costFrame, 'input[name="IMAGEFEE"]', cost.imageFee);
  await setInputValueIfExists(costFrame, 'input[name="DISKRDFEE"]', cost.discDevelopmentFee);

  await setInputValueIfExists(costFrame, 'input[name="UNITNUM"]', printing.sheets);
  await choose('select[name="FLOATNUM"]', printing.floatingPrintRun);
  await setInputValueIfExists(costFrame, 'input[name="SUMVERNUM"]', printing.totalImpressions);
  await choose('select[name="BINDMODE"]', '胶订');
  await choose('select[name="FITMENT"]', printing.binding, 1000);
  await choose('select[name="BOOKSIZE"]', printing.formatSize, 1200);
  await choose('select[name="SCRIPTPAPERSPEC"]', printing.textPaperSpec, 1200);
  await choose('select[name="SCRIPTPAPERNAME"]', printing.textPaperName, 1200);
  await choose('select[name="SCRIPTPAPERWEIGHT"]', printing.textPaperWeight, 1200);
  await setInputValueIfExists(costFrame, 'input[name="SCRIPTPAPERTYPE"]', printing.textPaperClass);
  await choose('select[name="SCRIPTPAPERCOLOR"]', printing.textPrintColors);
  await choose('select[name="PLATEMODE"]', printing.textPlateMaking);
  await choose('select[name="PRINTMODE"]', printing.textPrintingMode);
  await setInputValueIfExists(costFrame, 'input[name="CTPPAGENUM"]', printing.ctpProofPages);
  await choose('select[name="COVERPAPERNAME"]', printing.coverPaperName, 1000);
  await choose('select[name="COVERPAPERWEIGHT"]', printing.coverPaperWeight, 1000);
  await setInputValueIfExists(costFrame, 'input[name="COVERPAPERTYPE"]', printing.coverPaperClass);
  await choose('select[name="COVERPAPERCOLOR"]', printing.coverPrintColors);
  await choose('select[name="COVERCLADTYPE"]', printing.coverFinish);
  await choose('select[name="HAVELEKOU"]', printing.coverFlap);
  await choose('select[name="COVERPLATEMODE"]', printing.coverPlateMaking);
  await choose('select[name="COVERPRINTMODE"]', printing.coverPrintingMode);
  await setInputValueIfExists(costFrame, 'input[name="COLORINSERTPAGENUM"]', printing.colorInsertSheets);
  await setInputValueIfExists(costFrame, 'input[name="GRAYINSETNUM"]', printing.blackInsertSheets);
  await choose('select[name="HAVERINGLINER"]', printing.addEndpaper);
  await choose('select[name="RINGLINERTYPE"]', printing.endpaperClass);
  await choose('select[name="HAVEJACKET"]', printing.addDustJacket);
  await choose('select[name="HAVEPTAPE"]', printing.addBellyBand);

  await setInputValueIfExists(costFrame, 'input[name="SALENUM"]', sales.deliveryCopies);
  await setInputValueIfExists(costFrame, 'input[name="NETSALENUM"]', sales.saleCopies);
  await choose('select[name="HAVEZZ"]', sales.subsidy);
  await setInputValueIfExists(costFrame, 'input[name="IMBURSEFEE"]', sales.subsidyAmount);
  await setInputValueIfExists(costFrame, 'input[name="IMBURSENUM"]', sales.complimentaryCopies || '0');
  await choose('select[name="HAVEBX"]', sales.guaranteedSale);
  await setInputValueIfExists(costFrame, 'input[name="BSALENUM"]', sales.guaranteedSaleCopies || '0');
  await setInputValueIfExists(costFrame, 'input[name="BSALEDISCOUNT"]', sales.guaranteedSaleDiscount);
  await setInputValueIfExists(costFrame, 'input[name="CFRATE"]', sales.productionDeliveryRate);
  await setInputValueIfExists(costFrame, 'input[name="RETURNRATE"]', sales.returnRate);
  await setInputValueIfExists(costFrame, 'input[name="SALEDISCOUNT"]', sales.deliveryDiscount);
  await setInputValueIfExists(costFrame, 'input[name="SALELIFECYCLE"]', sales.salesCycleYears);
  await setInputValueIfExists(costFrame, 'input[name="SUMSALENUM"]', sales.totalDeliveryCopies);
  await setInputValueIfExists(costFrame, 'input[name="SUMNETSALENUM"]', sales.totalSaleCopies);
  await setInputValueIfExists(costFrame, 'input[name="CYPERCENT"]', sales.storageTransportRate);
  await setInputValueIfExists(costFrame, 'input[name="GAEXPENSE"]', sales.managementFee);
}

function numericFieldMatches(actual, expected) {
  const actualNumber = Number(String(actual ?? '').replace(/,/g, '').trim());
  const expectedNumber = Number(String(expected ?? '').replace(/,/g, '').trim());
  if (!Number.isFinite(actualNumber) || !Number.isFinite(expectedNumber)) return false;
  return Math.abs(actualNumber - expectedNumber) < 0.001;
}

async function verifyCostEstimateValues(costFrame, topic) {
  const cost = topic.costDefaults || {};
  const printing = cost.printing || {};
  const sales = cost.sales || {};
  const fields = [
    ['input[name="BJSTANDARD"]', cost.editUnitPrice, '编加单价'],
    ['input[name="JDSTANDARD"]', cost.proofUnitPrice, '校对单价'],
    ['input[name="UNITNUM"]', printing.sheets, '印张'],
    ['input[name="CYPERCENT"]', sales.storageTransportRate, '储运费扣点'],
    ['input[name="GAEXPENSE"]', sales.managementFee, '管理费'],
    ['input[name="SALENUM"]', sales.deliveryCopies, '发货册数'],
    ['input[name="NETSALENUM"]', sales.saleCopies, '销售册数'],
    ['input[name="SUMSALENUM"]', sales.totalDeliveryCopies, '总发货册数'],
    ['input[name="SUMNETSALENUM"]', sales.totalSaleCopies, '总销售册数'],
  ];
  const mismatches = [];
  const values = {};

  for (const [selector, expected, label] of fields) {
    if (expected === undefined || expected === null || expected === '') continue;
    const locator = costFrame.locator(selector).first();
    if (!(await locator.count())) {
      mismatches.push(`${label}字段不存在`);
      continue;
    }
    const actual = await locator.inputValue().catch(() => '');
    values[label] = actual;
    if (!numericFieldMatches(actual, expected)) {
      mismatches.push(`${label}期望“${expected}”，实际“${actual || '空'}”`);
    }
  }

  if (mismatches.length) {
    throw new Error(`成本估算关键字段校验失败：${mismatches.join('；')}`);
  }
  return values;
}

async function saveCostEstimateForm(costFrame, topic, { timeout = 30000 } = {}) {
  const calculateButton = costFrame.locator('input[value="计算"]').first();
  await calculateButton.waitFor({ state: 'visible', timeout: 10000 });
  await calculateButton.click();
  await costFrame.waitForTimeout(2000);
  await verifyCostEstimateValues(costFrame, topic);

  const saveButton = costFrame.locator('input[name="SAVEB"][value="暂存"]').first();
  await saveButton.waitFor({ state: 'visible', timeout: 10000 });
  await saveButton.click();
  await costFrame.waitForLoadState('domcontentloaded', { timeout }).catch(() => {});
  await costFrame.waitForTimeout(2000);
}

async function login(page) {
  const user = process.env.BPM_USER;
  const password = process.env.BPM_PASSWORD;
  if (!user || !password) {
    throw new Error('BPM_USER and BPM_PASSWORD are required');
  }

  await page.goto(DEFAULT_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.fill('#userid', user);
  await page.fill('#pwd', password);
  await page.click('#loginBtn');
  await page.waitForTimeout(6000);
}

async function readLoggedInBpmProfile(page) {
  const trigger = page.locator('#userInfo');
  await trigger.waitFor({ state: 'visible', timeout: 15000 });
  await trigger.click();

  const panel = page.locator('#editUserInfoPanel.show');
  await panel.waitFor({ state: 'visible', timeout: 10000 });
  const profileRows = page.locator(
    '#editUserInfoPanel .edit-user-info-operate-panel > div > div',
  );
  const name = String(await profileRows.nth(0).innerText()).trim();
  const department = String(await profileRows.nth(1).innerText()).trim();
  await trigger.click().catch(() => {});

  if (!isValidPersonName(name)) {
    throw new Error(`Could not identify the logged-in BPM user from the profile panel: "${name.slice(0, 40)}"`);
  }
  return { name, department };
}

function applyLoggedInBpmEditor(topic, profile) {
  topic.projectEditor = profile.name;
  topic.editor = profile.name;
  return topic;
}

async function openAuthorMaintenancePopup(page) {
  await page.locator('li.top-navitem-panel').filter({ hasText: '编辑' }).first().click();
  await page.waitForTimeout(1000);
  await page.locator('div.nav-item-func.metro-nav-goto').filter({ hasText: '作译者信息维护' }).first().click();
  await page.waitForTimeout(8000);

  const listFrame = page.frames().find((frame) => (
    frame.url().includes('Sys_UWV_portal')
    && frame.url().includes('%E6%96%B0%E5%A2%9E%E4%BD%9C%E8%AF%91%E8%80%85')
  ));
  if (!listFrame) throw new Error('Author maintenance frame not found');

  const addAuthorButton = listFrame.getByRole('button', {
    name: '新增作译者',
    exact: true,
  }).first();
  await addAuthorButton.waitFor({ state: 'visible', timeout: 15000 });
  const popupPromise = page.waitForEvent('popup', { timeout: 15000 });
  await addAuthorButton.click();
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded');
  await popup.waitForTimeout(3000);

  const formFrame = popup.frames().find((frame) => frame.url().includes('BindReport_S_Open')) || popup.mainFrame();
  await formFrame.locator('#AUTHORNAME').waitFor({ state: 'attached', timeout: 30000 });
  return { popup, formFrame };
}

async function fillAuthorMaintenanceForm(formFrame, topic) {
  const author = topic.authorMaintenance || {};
  await selectOptionWhenReady(formFrame, 'select[name="AUTHORTYPE"]', author.type || '个人', { fallback: true });
  await ensureBpmPersonIdentity(
    formFrame,
    'input[name="CONTACTOR"]',
    'input[name="CONTACTORUID"]',
    author.contactor || topic.projectEditor,
    '联系人',
  );
  await setInputValueIfExists(formFrame, 'input[name="AUTHORNAME"]', author.name || topic.authorName);
  await selectOptionIfExists(formFrame, 'select[name="SEX"]', author.gender);
  await selectOptionIfExists(formFrame, 'select[name="IDTYPE"]', author.certificateType || '其他');
  await setInputValueIfExists(formFrame, 'input[name="IDCODE"]', author.certificateNo || '　');
  await setInputValueIfExists(formFrame, 'input[name="TECHTITLE"]', author.title || '　');
  await setInputValueIfExists(formFrame, 'input[name="KNOWLEDGE"]', author.education || '　');
  await setInputValueIfExists(formFrame, 'input[name="MAJOR"]', author.major || '　');
  await setInputValueIfExists(formFrame, 'input[name="UNIV"]', author.graduateSchool || '　');
  await setInputValueIfExists(formFrame, 'input[name="UNIT"]', author.workUnit || '　');
  await setInputValueIfExists(formFrame, 'input[name="UNITADDRESS"]', author.unitAddress || '　');
  await setInputValueIfExists(formFrame, 'input[name="UNITZIP"]', author.unitZip || author.postalCode || '　');
  await setInputValueIfExists(formFrame, 'input[name="UNITCONTACTOR"]', author.unitContactor || '　');
  await setInputValueIfExists(formFrame, 'input[name="UNITFAX"]', author.unitFax || '　');
  await setInputValueIfExists(formFrame, 'input[name="PHONE1"]', author.phone1 || '　');
  await setInputValueIfExists(formFrame, 'input[name="PHONE2"]', author.phone2 || '　');
  await setInputValueIfExists(formFrame, 'input[name="FAX"]', author.fax || '　');
  await setInputValueIfExists(formFrame, 'input[name="EMAIL"]', author.email || '　');
  await setInputValueIfExists(formFrame, 'input[name="ZIP"]', author.postalCode || author.unitZip || '　');
  await setInputValueIfExists(formFrame, 'input[name="ADDRESS"]', author.address || '　');
  await setInputValueIfExists(formFrame, 'textarea[name="RESUME"]', author.workResume || '　');
  await setInputValueIfExists(formFrame, 'textarea[name="EXPERIENCE"]', author.academicOrganizations || '　');
  await setInputValueIfExists(formFrame, 'textarea[name="RESEARCHDETAIL"]', author.researchProjects || '　');
  await setInputValueIfExists(formFrame, 'textarea[name="PRIZEDETAIL"]', author.awards || '　');
  await setInputValueIfExists(formFrame, 'textarea[name="SPECIALITY"]', author.writingDirection || '　');
  await setInputValueIfExists(formFrame, 'textarea[name="WORKSDETAIL"]', author.publications || '　');
  await setInputValueIfExists(formFrame, 'textarea[name="AUTHORBRIEF"]', author.bio || '　');
}

function validateAuthorSaveEvidence(dialogs, authorCode) {
  const messages = (dialogs || []).map((message) => String(message || '').trim()).filter(Boolean);
  const blockingMessage = messages.find((message) => (
    /不允许为空|不是一个合法|已添加|失败|错误/.test(message)
    && !/作译者添加成功/.test(message)
  ));
  if (blockingMessage) {
    throw new Error(`BPM 作译者保存被校验拦截：${blockingMessage}`);
  }
  const code = String(authorCode || '').trim();
  if (!code || code === 'error') {
    throw new Error('BPM 作译者保存后没有生成作译者编码');
  }
  if (!messages.some((message) => /作译者添加成功/.test(message))) {
    throw new Error(`BPM 未返回“作译者添加成功”确认${messages.length ? `：${messages.join('；')}` : ''}`);
  }
  return { authorCode: code };
}

async function verifySavedAuthorInList(page, authorName, authorCode, { timeout = 30000 } = {}) {
  let listFrame = null;
  for (const frame of page.frames()) {
    if (await frame.locator('input[name^="AUTHORNAME"]:visible').count().catch(() => 0)) {
      listFrame = frame;
      break;
    }
  }
  if (!listFrame) throw new Error('BPM 作译者列表页未找到，无法验证保存结果');

  const nameInput = listFrame.locator('input[name^="AUTHORNAME"]:visible').first();
  const codeInput = listFrame.locator('input[name^="AUTHORCODE"]:visible').first();
  await nameInput.fill(authorName);
  if (await codeInput.count()) await codeInput.fill(authorCode);
  const queryButton = listFrame.getByRole('button', { name: '查询', exact: true }).first();
  await queryButton.waitFor({ state: 'visible', timeout: 10000 });
  await queryButton.click();

  const deadline = Date.now() + timeout;
  let lastText = '';
  while (Date.now() <= deadline) {
    for (const frame of page.frames()) {
      const bodyText = await frame.locator('body').innerText().catch(() => '');
      if (!bodyText) continue;
      if (bodyText.includes(authorName) && bodyText.includes(authorCode)) {
        return { ok: true, authorName, authorCode };
      }
      if (bodyText.includes('作者姓名或单位名称')) lastText = bodyText.slice(0, 3000);
    }
    await page.waitForTimeout(500);
  }
  throw new Error(
    `BPM 作译者保存未通过列表验证：未找到“${authorName} / ${authorCode}”${lastText ? `；列表内容：${lastText}` : ''}`,
  );
}

async function saveAuthorMaintenance(page, topic, outputDir, { dryRun = false } = {}) {
  const author = topic.authorMaintenance || {};
  if (!author.enabled || !(author.name || topic.authorName)) {
    return { skipped: true, reason: 'no author maintenance data' };
  }
  const { popup, formFrame } = await openAuthorMaintenancePopup(page);
  await fillAuthorMaintenanceForm(formFrame, topic);
  const screenshot = path.join(outputDir, dryRun ? 'bpm-author-dry-run-filled.png' : 'bpm-author-before-save.png');
  await popup.screenshot({ path: screenshot, fullPage: true });
  if (dryRun) {
    await popup.close().catch(() => {});
    return { skipped: false, dryRun: true, authorName: author.name || topic.authorName, screenshot };
  }
  const dialogs = [];
  popup.on('dialog', async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.accept().catch(() => {});
  });
  const authorCodeResponsePromise = popup.waitForResponse(
    (response) => response.url().includes('PHEI_GXR_AUTHOR_FORMBEFORESAVE'),
    { timeout: 15000 },
  ).catch(() => null);
  await popup.locator('input[name="SAVEB"]').click();
  const authorCodeResponse = await authorCodeResponsePromise;
  const responseAuthorCode = authorCodeResponse
    ? String(await authorCodeResponse.text().catch(() => '')).trim()
    : '';
  await page.waitForTimeout(500);
  const formAuthorCode = popup.isClosed()
    ? ''
    : await formFrame.locator('input[name="AUTHORCODE"]').inputValue().catch(() => '');
  const evidence = validateAuthorSaveEvidence(dialogs, responseAuthorCode || formAuthorCode);
  await page.waitForTimeout(2000);
  const verification = await verifySavedAuthorInList(
    page,
    author.name || topic.authorName,
    evidence.authorCode,
  );
  const after = path.join(outputDir, 'bpm-author-after-save.png');
  await page.screenshot({ path: after, fullPage: true });
  await popup.close().catch(() => {});
  return {
    skipped: false,
    authorName: author.name || topic.authorName,
    authorCode: evidence.authorCode,
    verified: verification.ok,
    dialogs,
    screenshots: [screenshot, after],
  };
}

async function openTopicPopup(page) {
  await page.locator('li.top-navitem-panel').filter({ hasText: '编辑' }).first().click();
  await page.waitForTimeout(1000);
  await page.locator('div.nav-item-func.metro-nav-goto').filter({ hasText: '选题申报' }).first().click();
  await page.waitForTimeout(8000);

  const listFrame = page.frames().find((f) => f.url().includes('WorkFlow_Execute_Worklist'));
  if (!listFrame) throw new Error('Worklist frame not found');

  const popupPromise = page.waitForEvent('popup', { timeout: 15000 });
  await listFrame.locator('input[name="newInstance"]').first().click();
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded');
  await popup.waitForTimeout(3000);

  let formFrame = popup.frames().find((f) => f.url().includes('BindReport_Open'));
  for (let attempt = 0; !formFrame && attempt < 40; attempt += 1) {
    await popup.waitForTimeout(1000);
    formFrame = popup.frames().find((f) => f.url().includes('BindReport_Open'));
  }
  if (!formFrame) throw new Error('BindReport_Open frame not found');

  return { popup, formFrame };
}

async function waitForSavedTopicLink(
  page,
  {
    cno,
    bookName,
    timeout = 45000,
    pollMs = 500,
  } = {},
) {
  const target = String(cno || bookName || '').trim();
  if (!target) throw new Error('Cannot locate saved BPM draft without a CNO or book name');

  const deadline = Date.now() + timeout;
  let lastTitles = [];
  let worklistFrameCount = 0;

  while (Date.now() <= deadline) {
    const frames = page.frames().filter((frame) => frame.url().includes('WorkFlow_Execute_Worklist'));
    worklistFrameCount = frames.length;
    lastTitles = [];

    for (const frame of frames) {
      const matchingLinks = frame.locator('a').filter({ hasText: target });
      const count = await matchingLinks.count().catch(() => 0);
      for (let index = 0; index < count; index += 1) {
        const link = matchingLinks.nth(index);
        const title = String(await link.innerText().catch(() => '')).replace(/\s+/g, ' ').trim();
        if (title) lastTitles.push(title);
        if (await link.isVisible().catch(() => false)) {
          return { link, frame, title };
        }
      }
    }

    if (Date.now() < deadline) await page.waitForTimeout(pollMs);
  }

  throw new Error(
    `Saved BPM draft "${target}" was not found after refreshing the worklist for ${timeout}ms. `
    + `Checked ${worklistFrameCount} worklist frame(s). `
    + `Matching titles seen: ${lastTitles.slice(0, 10).join(' | ') || '(none)'}`,
  );
}

async function reopenSavedTopicPopup(page, cno, bookName) {
  await page.locator('li.top-navitem-panel').filter({ hasText: '编辑' }).first().click();
  await page.waitForTimeout(500);
  await page.locator('div.nav-item-func.metro-nav-goto').filter({ hasText: '选题申报' }).first().click();
  const { link: savedLink } = await waitForSavedTopicLink(page, { cno, bookName });
  const popupPromise = page.waitForEvent('popup', { timeout: 15000 });
  await savedLink.click();
  const popup = await popupPromise;
  await popup.waitForLoadState('domcontentloaded');

  let formFrame = null;
  const formDeadline = Date.now() + 30000;
  while (!formFrame && Date.now() < formDeadline) {
    const urlMatch = popup.frames().find((frame) => frame.url().includes('BindReport_Open'));
    if (urlMatch && await urlMatch.locator('#BOOKNAME').count().catch(() => 0)) formFrame = urlMatch;
    if (!formFrame) {
      for (const frame of popup.frames()) {
        if (await frame.locator('#BOOKNAME').count().catch(() => 0)) {
          formFrame = frame;
          break;
        }
      }
    }
    if (!formFrame) await popup.waitForTimeout(500);
  }
  if (!formFrame) throw new Error('Saved BPM form frame did not load');
  return { popup, formFrame };
}

async function fillForm(formFrame, topic) {
  await setInputValue(formFrame, '#BOOKNAME', topic.bookName);

  await selectOptionWhenReady(formFrame, '#TYPE', topic.type, { fallback: true });
  await selectOptionWhenReady(formFrame, '#CLASS1', topic.class1, { fallback: true, settleMs: 1200 });
  await selectOptionWhenReady(formFrame, '#CLASS2', topic.class2, { fallback: true, timeout: 30000, settleMs: 1200 });
  await selectOptionWhenReady(formFrame, '#CLASS3', topic.class3, { fallback: true, timeout: 30000, settleMs: 1200 });
  await selectOptionWhenReady(formFrame, '#CLASS4', topic.class4, { required: false, fallback: true, timeout: 15000 });
  await selectOptionWhenReady(formFrame, '#GBCLASS', topic.gbClass, { fallback: true });
  await selectOptionWhenReady(formFrame, '#READLEVER', topic.readLevel, { fallback: true });
  await selectOptionWhenReady(formFrame, '#HAVEREPLACEBSN', topic.haveReplaceBsn, { fallback: true });
  await setInputValue(formFrame, 'input[name="REPLACEBSN"]', topic.replaceBsn);

  // The main declaration form's author fields should be selected from BPM's
  // author library manually. Leave them blank to avoid saving a name without
  // the corresponding author code.
  await clearMainAuthorFields(formFrame);

  await setInputValue(formFrame, '#BRIEF', topic.brief);
  await setInputValue(formFrame, '#READER', topic.reader);
  await setInputValue(formFrame, '#FEATURE', topic.feature);
  await setInputValue(formFrame, '#COMPARE', topic.compare);

  await setInputValue(formFrame, 'input[name="READERNUM"]', topic.readerNum);
  await selectOptionWhenReady(formFrame, '#LANGUAGE', topic.language, { fallback: true });
  await selectOptionWhenReady(formFrame, '#SCRIPTSOURCE', topic.scriptSource, { fallback: true });
  await selectOptionWhenReady(formFrame, '#SCRIPTSTYLE', topic.scriptStyle, { fallback: true });
  await setInputValue(formFrame, 'input[name="SCRIPTDATE"]', topic.scriptDate);
  await setInputValue(formFrame, 'input[name="MAKINGDATE"]', topic.makingDate);
  await setInputValue(formFrame, 'input[name="PUBLISHDATE"]', topic.publishDate);
  await selectOptionWhenReady(formFrame, '#AWARDS', topic.awards, { fallback: true });
  await selectOptionWhenReady(formFrame, '#COLORPRINT', topic.colorPrint, { fallback: true });
  await selectOptionWhenReady(formFrame, '#HAVECD', topic.haveCd, { required: false, fallback: true });
  await setInputValue(formFrame, 'input[name="WORDS"]', topic.words);
  await setInputValue(formFrame, 'input[name="PRICE"]', topic.price);
  await setInputValue(formFrame, 'input[name="REMCHARNUM"]', topic.remCharNum);
  await selectOptionWhenReady(formFrame, '#REMPAYMODE', topic.remPayMode, { fallback: true });
  await setInputValue(formFrame, 'input[name="REMSTANDARD"]', topic.remStandard);
  await selectOptionIfExists(formFrame, '#REMUNIT', topic.remUnit);
  await selectOptionWhenReady(formFrame, '#PUBLISHMODE', topic.publishMode, { fallback: true });
  await selectOptionWhenReady(formFrame, 'select[name="HAVEZZ"]', topic.haveZz, { fallback: true });
  await setInputValue(formFrame, 'input[name="IMBURSEFEE"]', topic.imburseFee);
  await setInputValue(formFrame, 'input[name="IMBURSENUM"]', topic.imburseNum);
  await selectOptionWhenReady(formFrame, 'select[name="HAVEBX"]', topic.haveBx, { fallback: true });
  await setInputValue(formFrame, 'input[name="BSALENUM"]', topic.bsaleNum);
  await setInputValue(formFrame, 'input[name="BSALEDISCOUNT"]', topic.bsaleDiscount);
  await selectOptionIfExists(formFrame, '#COMODE', topic.coMode);
  await setInputValueIfExists(formFrame, 'input[name="COBUYDISCOUNT"]', topic.coBuyDiscount);
  await selectOptionIfExists(formFrame, '#BSALEMODE', topic.bsaleMode);
  await selectOptionIfExists(formFrame, '#DIGITAL', topic.digital);
  await selectOptionIfExists(formFrame, '#EREMPAYMODE', topic.eRemPayMode);
  await setInputValueIfExists(formFrame, 'input[name="EREMSTANDARD"]', topic.eRemStandard);
  await setInputValue(formFrame, 'input[name="TOTALNUM"]', topic.totalNum);
  await setInputValue(formFrame, 'input[name="FIRSTNUM"]', topic.firstNum);
  await setRadioValue(formFrame, 'PROJECT', topic.project);
  await setRadioValue(formFrame, 'SCRIPTCLASSIFY', topic.scriptClassify);

  await ensureEditorIdentity(formFrame, topic);
  await setReadonlyInputValue(formFrame, 'input[name="PRJDEPT"]', topic.projectDept);
  await setReadonlyInputValue(formFrame, 'input[name="EDITORDEPT"]', topic.editorDept);
  await selectOptionWhenReady(formFrame, '#ISCOST', topic.isCost, { fallback: true });
  await selectOptionWhenReady(formFrame, '#IMPSCRIPT', topic.impScript, { fallback: true });
  await selectOptionWhenReady(formFrame, '#ISURGENT', topic.isUrgent, { fallback: true });
  await selectOptionWhenReady(formFrame, '#ISMEETING', topic.isMeeting, { fallback: true });
  await selectOptionIfExists(formFrame, '#BWCLASS', topic.bwClass);
  await setInputValueIfExists(formFrame, 'input[name="BWCIPCLASS"]', topic.bwCipClass);

}

async function inspectForm(formFrame) {
  return await formFrame.evaluate(() => {
    const labelTextFor = (el) => {
      const id = el.getAttribute('id');
      if (id) {
        const label = document.querySelector(`label[for="${CSS.escape(id)}"]`);
        if (label) return label.textContent.trim();
      }
      const row = el.closest('tr');
      if (row) {
        const cells = Array.from(row.cells || []);
        const index = cells.findIndex((cell) => cell.contains(el));
        const before = cells.slice(Math.max(0, index - 2), index).map((cell) => cell.textContent.trim()).filter(Boolean);
        if (before.length) return before.join(' / ');
      }
      const parentText = el.parentElement ? el.parentElement.textContent.trim() : '';
      return parentText.slice(0, 80);
    };

    return Array.from(document.querySelectorAll('input, textarea, select'))
      .filter((el) => {
        const type = (el.getAttribute('type') || '').toLowerCase();
        return type !== 'hidden' && type !== 'button' && type !== 'submit' && type !== 'image';
      })
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        type: el.getAttribute('type') || '',
        id: el.getAttribute('id') || '',
        name: el.getAttribute('name') || '',
        label: labelTextFor(el),
        value: el.value || '',
        onchange: el.getAttribute('onchange') || '',
        options: el.tagName.toLowerCase() === 'select'
          ? Array.from(el.options).map((option) => ({ value: option.value, text: option.textContent.trim() }))
          : [],
      }));
  });
}

async function inspectClickableControls(frame) {
  return await frame.evaluate(() => Array.from(document.querySelectorAll(
    'button, input[type="button"], input[type="submit"], input[type="image"], a, [onclick]',
  )).map((el) => ({
    tag: el.tagName.toLowerCase(),
    id: el.id || '',
    name: el.getAttribute('name') || '',
    type: el.getAttribute('type') || '',
    value: el.getAttribute('value') || '',
    text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120),
    onclick: (el.getAttribute('onclick') || '').slice(0, 300),
    visible: Boolean(el.getBoundingClientRect().width && el.getBoundingClientRect().height),
  })).filter((item) => (
    item.visible
    || /暂存|保存|成本|估算|办理|新增/.test(`${item.value} ${item.text} ${item.onclick}`)
  )));
}

async function inspectScoreGrid(formFrame) {
  return await formFrame.evaluate(() => {
    const marker = Array.from(document.querySelectorAll('*')).find((el) => (
      el.children.length === 0 && (el.textContent || '').trim() === '选题分级评分表'
    ));
    const container = marker && (marker.closest('.x-panel') || marker.parentElement?.parentElement?.parentElement);
    return {
      marker: marker ? {
        tag: marker.tagName.toLowerCase(),
        id: marker.id || '',
        className: marker.className || '',
      } : null,
      html: container ? container.outerHTML.slice(0, 30000) : '',
    };
  });
}

async function inspectChoiceControls(formFrame) {
  return await formFrame.locator('input[name="PROJECT"], input[name="SCRIPTCLASSIFY"]').evaluateAll(
    (elements) => elements.map((el) => ({
      name: el.getAttribute('name') || '',
      value: el.getAttribute('value') || '',
      html: (el.closest('label') || el.parentElement || el).outerHTML.slice(0, 2000),
    })),
  );
}

async function inspectEditorControls(formFrame) {
  return await formFrame.locator(
    'input[name="PRJEDITOR"], input[name="EDITOR"], input[name="PRJDEPT"]',
  ).evaluateAll((elements) => elements.map((el) => ({
    name: el.getAttribute('name') || '',
    html: (el.closest('tr') || el.parentElement || el).outerHTML.slice(0, 10000),
  })));
}

async function collectFilledFormDiagnostics(formFrame) {
  return await formFrame.evaluate(() => {
    const read = (selector) => {
      const el = document.querySelector(selector);
      return el ? el.value || '' : null;
    };
    const bindValue = typeof getBindValue === 'function' ? getBindValue(document.frmMain) : '';
    const visibleEmptyRequired = [];
    Array.from(document.querySelectorAll('input, textarea, select')).forEach((el) => {
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (type === 'hidden' || type === 'button' || type === 'submit' || type === 'image') return;
      const rect = el.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const row = el.closest('tr');
      const rowText = row ? row.textContent.replace(/\s+/g, ' ').trim() : '';
      if (!rowText.includes('*')) return;
      if (String(el.value || '').trim()) return;
      visibleEmptyRequired.push({
        id: el.id || '',
        name: el.getAttribute('name') || '',
        rowText: rowText.slice(0, 180),
      });
    });
    return {
      bookName: read('#BOOKNAME'),
      booksName: read('input[name="BOOKSNAME"]'),
      projectEditor: read('input[name="PRJEDITOR"]'),
      projectEditorNo: read('input[name="PRJEDITORNO"]'),
      projectEditorUid: read('input[name="PRJEDITORUID"]'),
      editor: read('input[name="EDITOR"]'),
      editorNo: read('input[name="EDITORNO"]'),
      editorUid: read('input[name="EDITORUID"]'),
      authorCode: read('input[name="AUTHORCODE"]'),
      authorName: read('input[name="AUTHORNAME"]'),
      authorId: read('input[name="AUTHORID"]'),
      score: read('#SCORE'),
      bindHasBookName: bindValue.includes(read('#BOOKNAME') || '__NO_BOOK__'),
      bindHasBooksName: bindValue.includes(`_BOOKSNAME{${read('input[name="BOOKSNAME"]') || ''}}BOOKSNAME_`),
      bindHead: bindValue.slice(0, 1000),
      visibleEmptyRequired,
      bodyTextHead: document.body.innerText.slice(0, 1000),
    };
  });
}

async function readInputValue(frame, selector) {
  return await frame.locator(selector).first().inputValue().catch(() => '');
}

async function verifyCreatedTitle(page, expectedBookName, expectedCno) {
  await page.locator('li.top-navitem-panel').filter({ hasText: '编辑' }).first().click();
  await page.waitForTimeout(1000);
  await page.locator('div.nav-item-func.metro-nav-goto').filter({ hasText: '选题申报' }).first().click();
  const expectedCnoText = String(expectedCno || '').trim();
  const expectedBookNameText = String(expectedBookName || '').trim();
  const { title } = await waitForSavedTopicLink(page, {
    cno: expectedCnoText,
    bookName: expectedBookNameText,
  });
  const cnoMatches = !expectedCnoText || title.includes(expectedCnoText);
  const bookNameMatches = !expectedBookNameText || title.includes(expectedBookNameText);
  const exactCurrent = cnoMatches && bookNameMatches ? title : null;

  return {
    ok: !!exactCurrent,
    title: exactCurrent || null,
    cnoOnly: cnoMatches ? title : null,
    bookNameOnly: bookNameMatches ? title : null,
    recentTitles: [title],
  };
}

async function inspect(outputDirArg) {
  const outputDir = path.resolve(outputDirArg || process.cwd());
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });

  try {
    await login(page);
    const { popup, formFrame } = await openTopicPopup(page);
    const screenshot = path.join(outputDir, 'bpm-inspect-form.png');
    await popup.screenshot({ path: screenshot, fullPage: true });
    const fields = await inspectForm(formFrame);
    const result = {
      ok: true,
      mode: 'inspect',
      fieldCount: fields.length,
      fields,
      popupControls: await inspectClickableControls(popup.mainFrame()),
      formControls: await inspectClickableControls(formFrame),
      scoreGridRows: await inspectScoreGrid(formFrame),
      choiceControls: await inspectChoiceControls(formFrame),
      editorControls: await inspectEditorControls(formFrame),
      screenshot,
      popupUrl: popup.url(),
      frameUrl: formFrame.url(),
    };
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
}

async function inspectEditorPicker(outputDirArg) {
  const outputDir = path.resolve(outputDirArg || process.cwd());
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });

  try {
    await login(page);
    const { popup, formFrame } = await openTopicPopup(page);
    const editorRow = formFrame.locator('input[name="PRJEDITOR"]').locator('xpath=ancestor::tr[1]');
    await editorRow.locator('input[type="button"]').click();
    await popup.waitForTimeout(3000);
    const pages = popup.context().pages();
    const pageDiagnostics = [];
    for (let index = 0; index < pages.length; index += 1) {
      const currentPage = pages[index];
      const screenshot = path.join(outputDir, `bpm-editor-picker-page-${index}.png`);
      await currentPage.screenshot({ path: screenshot, fullPage: true }).catch(() => {});
      pageDiagnostics.push({
        url: currentPage.url(),
        screenshot,
        frames: await Promise.all(currentPage.frames().map(async (frame) => ({
          url: frame.url(),
          text: (await frame.locator('body').innerText().catch(() => '')).slice(0, 3000),
          controls: await inspectClickableControls(frame).catch(() => []),
        }))),
      });
    }
    console.log(JSON.stringify({
      ok: true,
      mode: 'inspect-picker',
      pages: pageDiagnostics,
    }, null, 2));
  } finally {
    await browser.close();
  }
}

async function inspectDepartmentPicker(outputDirArg) {
  const outputDir = path.resolve(outputDirArg || process.cwd());
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });

  try {
    await login(page);
    const { popup, formFrame } = await openTopicPopup(page);
    const departmentRow = formFrame.locator('input[name="PRJDEPT"]').locator('xpath=ancestor::tr[1]');
    await departmentRow.locator('input[type="button"]').click();
    await popup.waitForTimeout(3000);
    const departmentFrame = popup.frames().find((frame) => frame.url().includes('Dictionary_Department_Tree'));
    if (departmentFrame) {
      await departmentFrame.locator('.x-tree-elbow-end-plus').first().click();
      await popup.waitForTimeout(3000);
      if (await departmentFrame.locator('.x-tree-elbow-end-plus').count()) {
        await departmentFrame.locator('.x-tree-elbow-end-plus').first().click();
        await popup.waitForTimeout(3000);
      }
    }
    const screenshot = path.join(outputDir, 'bpm-department-picker.png');
    await popup.screenshot({ path: screenshot, fullPage: true });
    console.log(JSON.stringify({
      ok: true,
      mode: 'inspect-department-picker',
      screenshot,
      frames: await Promise.all(popup.frames().map(async (frame) => ({
        url: frame.url(),
        text: (await frame.locator('body').innerText().catch(() => '')).slice(0, 5000),
        html: (await frame.locator('body').innerHTML().catch(() => '')).slice(0, 30000),
        controls: await inspectClickableControls(frame).catch(() => []),
      }))),
    }, null, 2));
  } finally {
    await browser.close();
  }
}

async function submitTopic(jsonPath) {
  const { absPath, data } = loadInput(jsonPath);
  const topic = withDefaults(data);
  const outputDir = path.dirname(absPath);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });
  const dialogs = [];
  const milestones = [];
  const markMilestone = (name) => {
    if (!milestones.includes(name)) milestones.push(name);
  };
  let cno = '';
  let verification = null;

  try {
    page.on('dialog', async (dialog) => {
      dialogs.push(dialog.message());
      await dialog.accept().catch(() => {});
    });

    await login(page);
    const bpmProfile = await readLoggedInBpmProfile(page);
    markMilestone('login_verified');
    applyLoggedInBpmEditor(topic, bpmProfile);
    const { popup, formFrame } = await openTopicPopup(page);
    markMilestone('topic_form_opened');
    await fillForm(formFrame, topic);

    const mainBefore = path.join(outputDir, 'bpm-main-before-save.png');
    const mainAfter = path.join(outputDir, 'bpm-main-after-save.png');
    await popup.screenshot({ path: mainBefore, fullPage: true });
    await clickWorkflowSaveAndWait(popup, formFrame, { timeout: 30000, settleMs: 3000 });
    await popup.screenshot({ path: mainAfter, fullPage: true });
    const savedFormFrame = await waitForMainFormFrame(popup);
    cno = await readInputValue(savedFormFrame, '#CNO');
    const savedBookName = await readInputValue(savedFormFrame, '#BOOKNAME');
    if (!cno && savedBookName !== topic.bookName) {
      throw new Error(`BPM draft save did not retain the expected book name: "${topic.bookName}"`);
    }
    markMilestone('topic_draft_saved');

    await popup.close();
    const reopened = await reopenSavedTopicPopup(page, cno, topic.bookName);
    await fillScoreGrid(reopened.formFrame, topic);
    const costFrame = await openCostEstimateForm(reopened.popup, reopened.formFrame, topic);
    await fillCostEstimateForm(costFrame, topic);
    const costBefore = path.join(outputDir, 'bpm-before-save.png');
    const costAfter = path.join(outputDir, 'bpm-after-save.png');
    await reopened.popup.screenshot({ path: costBefore, fullPage: true });
    await saveCostEstimateForm(costFrame, topic, { timeout: 30000 });
    await reopened.popup.screenshot({ path: costAfter, fullPage: true });
    await reopened.popup.close().catch(() => {});

    const costVerification = await reopenSavedTopicPopup(page, cno, topic.bookName);
    const persistedCostFrame = await openCostEstimateForm(
      costVerification.popup,
      costVerification.formFrame,
      topic,
    );
    const persistedCostValues = await verifyCostEstimateValues(persistedCostFrame, topic);
    const costVerified = path.join(outputDir, 'bpm-cost-verified.png');
    await costVerification.popup.screenshot({ path: costVerified, fullPage: true });
    await costVerification.popup.close().catch(() => {});
    markMilestone('cost_estimate_saved');

    verification = await verifyCreatedTitle(page, topic.bookName, cno);
    if (!verification.ok) {
      const cnoMessage = cno ? ` with CNO "${cno}"` : '';
      const cnoOnlyMessage = verification.cnoOnly ? ` Found current CNO title: "${verification.cnoOnly}".` : '';
      const oldTitleMessage = verification.bookNameOnly ? ` Found another matching book title: "${verification.bookNameOnly}".` : '';
      throw new Error(`BPM save was not verified: "${topic.bookName}"${cnoMessage} was not found in the worklist after save.${cnoOnlyMessage}${oldTitleMessage}`);
    }
    markMilestone('worklist_verified');
    const result = {
      ok: true,
      title: verification.title,
      cno,
      verification,
      milestones: [...milestones],
      dialogs,
      costEstimate: persistedCostValues,
      expectedBookName: topic.bookName,
      inputPath: absPath,
      screenshots: [
        mainBefore,
        mainAfter,
        costBefore,
        costAfter,
        costVerified,
      ],
    };
    console.log(JSON.stringify(result, null, 2));
    return result;
  } catch (error) {
    error.bpmResult = {
      ok: false,
      mode: 'submit-topic',
      title: verification?.title || null,
      cno: cno || null,
      verification,
      milestones: [...milestones],
      expectedBookName: topic.bookName,
      inputPath: absPath,
      error: String(error?.message || error || 'BPM topic submission failed'),
    };
    throw error;
  } finally {
    await browser.close();
  }
}

async function submitAuthor(jsonPath) {
  const { absPath, data } = loadInput(jsonPath);
  const topic = withDefaults(data);
  const authorName = topic.authorMaintenance?.name || topic.authorName;
  const authorBio = String(topic.authorMaintenance?.bio || '').trim();
  if (!isValidPersonName(authorName)) {
    throw new Error(`Invalid authorName: "${String(authorName || '').slice(0, 80)}". Please provide a 2-8 character Chinese author name.`);
  }
  if (!authorBio) throw new Error('Author bio is required');
  topic.authorMaintenance.enabled = true;

  const outputDir = path.dirname(absPath);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });

  try {
    await login(page);
    const authorResult = await saveAuthorMaintenance(page, topic, outputDir);
    if (authorResult.skipped) {
      throw new Error(authorResult.reason || 'Author maintenance was skipped');
    }
    console.log(JSON.stringify({
      ok: true,
      mode: 'submit-author',
      authorName,
      authorCode: authorResult.authorCode,
      verified: authorResult.verified === true,
      authorResult,
      inputPath: absPath,
    }, null, 2));
  } finally {
    await browser.close();
  }
}

async function dryRun(jsonPath) {
  const { absPath, data } = loadInput(jsonPath);
  const topic = withDefaults(data);
  const outputDir = path.dirname(absPath);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });

  try {
    await login(page);
    const authorResult = await saveAuthorMaintenance(page, topic, outputDir, { dryRun: true });
    const { popup, formFrame } = await openTopicPopup(page);
    await fillForm(formFrame, topic);
    const costFrame = await openCostEstimateForm(popup, formFrame);
    await fillCostEstimateForm(costFrame, topic);
    const screenshot = path.join(outputDir, 'bpm-dry-run-filled.png');
    await popup.screenshot({ path: screenshot, fullPage: true });
    console.log(JSON.stringify({
      ok: true,
      mode: 'dry-run',
      expectedBookName: topic.bookName,
      authorResult,
      inputPath: absPath,
      screenshot,
    }, null, 2));
  } finally {
    await browser.close();
  }
}

async function debugMain(jsonPath) {
  const { absPath, data } = loadInput(jsonPath);
  const topic = withDefaults(data);
  const outputDir = path.dirname(absPath);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });

  try {
    await login(page);
    const { popup, formFrame } = await openTopicPopup(page);
    await fillForm(formFrame, topic);
    const before = await collectFilledFormDiagnostics(formFrame);
    const beforeScreenshot = path.join(outputDir, 'bpm-main-debug-before-save.png');
    await popup.screenshot({ path: beforeScreenshot, fullPage: true });
    await clickWorkflowSaveAndWait(popup, formFrame, { timeout: 30000, settleMs: 3000 });
    const savedFormFrame = await waitForMainFormFrame(popup);
    const after = await collectFilledFormDiagnostics(savedFormFrame);
    const afterScreenshot = path.join(outputDir, 'bpm-main-debug-after-save.png');
    await popup.screenshot({ path: afterScreenshot, fullPage: true });
    console.log(JSON.stringify({
      ok: true,
      mode: 'debug-main',
      inputPath: absPath,
      before,
      after,
      screenshots: [beforeScreenshot, afterScreenshot],
    }, null, 2));
  } finally {
    await browser.close();
  }
}

async function main() {
  const mode = process.argv[2];
  const jsonPath = process.argv[3];
  if (mode === 'inspect') {
    await inspect(jsonPath);
    return;
  }
  if (mode === 'inspect-picker') {
    await inspectEditorPicker(jsonPath);
    return;
  }
  if (mode === 'inspect-department-picker') {
    await inspectDepartmentPicker(jsonPath);
    return;
  }
  if (mode === 'dry-run' && jsonPath) {
    await dryRun(jsonPath);
    return;
  }
  if (mode === 'debug-main' && jsonPath) {
    await debugMain(jsonPath);
    return;
  }
  if (mode === 'submit-author' && jsonPath) {
    await submitAuthor(jsonPath);
    return;
  }
  if ((mode === 'submit-topic' || mode === 'submit') && jsonPath) {
    await submitTopic(jsonPath);
    return;
  }
  throw new Error('Usage: node fill_topic.js inspect [/abs/output/dir] OR node fill_topic.js inspect-picker [/abs/output/dir] OR node fill_topic.js inspect-department-picker [/abs/output/dir] OR node fill_topic.js dry-run /abs/path/topic.json OR node fill_topic.js debug-main /abs/path/topic.json OR node fill_topic.js submit-topic /abs/path/topic.json OR node fill_topic.js submit-author /abs/path/topic.json');
}

module.exports = {
  applyLoggedInBpmEditor,
  ensureEditorIdentity,
  findUniqueBpmPersonLink,
  readLoggedInBpmProfile,
  selectBpmPerson,
  validateAuthorSaveEvidence,
  waitForSavedTopicLink,
};

if (require.main === module) {
  main().catch((err) => {
    if (err.bpmResult) console.log(JSON.stringify(err.bpmResult, null, 2));
    console.error(err);
    process.exit(1);
  });
}
