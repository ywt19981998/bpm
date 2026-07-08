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
      contactorUid: 'yewt',
      contactorDeptId: '13640',
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
    projectEditorNo: '2024070801',
    projectEditorUid: 'yewt',
    editor: '叶文涛',
    editorNo: '2024070801',
    editorUid: 'yewt',
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
    if (!merged.authorMaintenance.contactorUid) merged.authorMaintenance.contactorUid = merged.projectEditorUid;
    if (!merged.authorMaintenance.contactorDeptId && merged.projectEditor === '叶文涛') merged.authorMaintenance.contactorDeptId = '13640';
    if (!data.authorMaintenance || data.authorMaintenance.enabled === undefined) {
      merged.authorMaintenance.enabled = Boolean(merged.authorMaintenance.name);
    }
  }
  if (merged.projectEditor !== '叶文涛') {
    merged.projectEditorNo = data.projectEditorNo || '';
    merged.projectEditorUid = data.projectEditorUid || '';
  }
  if (merged.editor !== '叶文涛') {
    merged.editorNo = data.editorNo || '';
    merged.editorUid = data.editorUid || '';
  }
  return merged;
}

function isValidPersonName(value) {
  const text = String(value || '').trim();
  return /^[\u4e00-\u9fff·]{2,8}$/.test(text);
}

async function setInputValue(frame, selector, value) {
  await frame.locator(selector).evaluate((el, v) => {
    el.value = v;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }, value);
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
  await locator.type(String(value), { delay: 20 });
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

async function fireSelectChange(locator) {
  await locator.evaluate((el) => {
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    if (typeof el.onchange === 'function') {
      el.onchange();
    }
  });
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

  await locator.evaluate((el, choice) => {
    const selected = Array.from(el.options || []).find((option) => option.value === choice.value)
      || Array.from(el.options || []).find((option) => option.textContent.trim() === choice.text);
    if (selected) {
      selected.selected = true;
      el.value = selected.value;
    } else {
      el.value = choice.value || choice.text;
    }
  }, match);
  await fireSelectChange(locator);
  if (settleMs) await frame.waitForTimeout(settleMs);
  return match;
}

async function setRadioValue(frame, name, value) {
  if (value === undefined || value === null || value === '') return;
  const result = await frame.evaluate(({ radioName, radioValue }) => {
    const candidates = Array.from(document.querySelectorAll('input'))
      .filter((el) => el.name === radioName);
    const target = candidates.find((el) => el.value === radioValue);
    if (!target) {
      return {
        ok: false,
        available: candidates.map((el) => el.value),
      };
    }
    target.checked = true;
    target.dispatchEvent(new Event('input', { bubbles: true }));
    target.dispatchEvent(new Event('change', { bubbles: true }));
    target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    if (typeof target.onclick === 'function') {
      target.onclick();
    }
    return { ok: true, available: candidates.map((el) => el.value) };
  }, { radioName: name, radioValue: value });

  if (!result.ok) {
    throw new Error(`Radio option not found for ${name}: "${value}". Available options: ${result.available.join(', ')}`);
  }
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
  await setInputValueIfExists(frame, '#SCORE', String(total));

  await frame.evaluate(({ scores: scoreValues, totalScore }) => {
    if (!window.Ext || !Ext.getCmp) return;
    const grid = Ext.getCmp('ext-comp-1022')
      || Object.values(Ext.ComponentMgr.all.map || {}).find((component) => component && component.title === '选题分级评分表');
    if (!grid || !grid.getStore) return;
    const store = grid.getStore();
    store.each((record) => {
      const item = String(record.get('ITEM') || '');
      if (item.includes('总分')) {
        record.set('SELFSCORE', totalScore);
        return;
      }
      const match = Object.keys(scoreValues).find((name) => item.includes(name));
      if (match) record.set('SELFSCORE', Number(scoreValues[match] || 0));
    });
    if (grid.getView) grid.getView().refresh();
  }, { scores, totalScore: total });
}

async function clickSaveAndWait(frame, { timeout = 30000, settleMs = 1000 } = {}) {
  await frame.evaluate(() => {
    if (typeof saveForm === 'function') {
      saveForm();
      return;
    }
    const button = document.querySelector('button.x-btn-text.save')
      || Array.from(document.querySelectorAll('button,input')).find((el) => /保存|暂存/.test(el.value || el.textContent || ''));
    if (!button) throw new Error('Save button not found in current frame');
    button.click();
  });
  await frame.waitForLoadState('domcontentloaded', { timeout }).catch(() => {});
  await frame.waitForTimeout(settleMs);
}

async function clickWorkflowSaveAndWait(popup, { timeout = 30000, settleMs = 1000 } = {}) {
  await popup.evaluate(() => {
    if (typeof saveFormData !== 'function') {
      throw new Error('saveFormData is not available');
    }
    saveFormData();
  });
  await popup.waitForTimeout(timeout);
  await popup.waitForTimeout(settleMs);
}

async function waitForCostFrame(popup) {
  for (let attempt = 0; attempt < 40; attempt += 1) {
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
  await setInputValueIfExists(formFrame, 'input[name="AUTHORCODE"]', '');
  await setInputValueIfExists(formFrame, 'input[name="AUTHORID"]', '');
  await setInputValueIfExists(formFrame, 'input[name="AUTHORNAME"]', '');
}

async function openCostEstimateForm(popup, formFrame, topic = {}) {
  await triggerCostEstimateForm(formFrame);
  let costFrame = await waitForCostFrame(popup);
  if (costFrame) return costFrame;

  if (topic.authorName) {
    await setInputValueIfExists(formFrame, 'input[name="AUTHORNAME"]', topic.authorName);
    await formFrame.waitForTimeout(300);
    await triggerCostEstimateForm(formFrame);
    costFrame = await waitForCostFrame(popup);
    await clearMainAuthorFields(formFrame);
    if (costFrame) return costFrame;
  }

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

  const popupPromise = page.waitForEvent('popup', { timeout: 8000 });
  await listFrame.evaluate(() => {
    if (typeof insertRowData2 !== 'function') {
      throw new Error('insertRowData2 is not available');
    }
    insertRowData2(frmMain, 'WorkFlow_Execute_Worklist_BindReport_S_Open', 2628);
  });
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
  await setInputValueIfExists(formFrame, 'input[name="CONTACTOR"]', author.contactor || topic.projectEditor);
  await setInputValueIfExists(formFrame, 'input[name="CONTACTORUID"]', author.contactorUid || topic.projectEditorUid);
  await setInputValueIfExists(formFrame, 'input[name="CONTACTORDEPID"]', author.contactorDeptId || '');
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
  await popup.locator('input[name="SAVEB"]').click();
  await popup.waitForTimeout(3000);
  const after = path.join(outputDir, 'bpm-author-after-save.png');
  await popup.screenshot({ path: after, fullPage: true });
  await popup.close().catch(() => {});
  return { skipped: false, authorName: author.name || topic.authorName, screenshots: [screenshot, after] };
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

async function fillForm(formFrame, topic) {
  await formFrame.locator('#BOOKNAME').fill(topic.bookName);

  await selectOptionWhenReady(formFrame, '#TYPE', topic.type, { fallback: true });
  await selectOptionWhenReady(formFrame, '#CLASS1', topic.class1, { fallback: true, settleMs: 1200 });
  await selectOptionWhenReady(formFrame, '#CLASS2', topic.class2, { fallback: true, timeout: 30000, settleMs: 1200 });
  await selectOptionWhenReady(formFrame, '#CLASS3', topic.class3, { fallback: true, timeout: 30000, settleMs: 1200 });
  await selectOptionWhenReady(formFrame, '#CLASS4', topic.class4, { required: false, fallback: true, timeout: 15000 });
  await selectOptionWhenReady(formFrame, '#GBCLASS', topic.gbClass, { fallback: true });
  await selectOptionWhenReady(formFrame, '#READLEVER', topic.readLevel, { fallback: true });
  await selectOptionWhenReady(formFrame, '#HAVEREPLACEBSN', topic.haveReplaceBsn, { fallback: true });
  await formFrame.locator('input[name="REPLACEBSN"]').fill(topic.replaceBsn);

  // The main declaration form's author fields should be selected from BPM's
  // author library manually. Leave them blank to avoid saving a name without
  // the corresponding author code.
  await clearMainAuthorFields(formFrame);

  await formFrame.locator('#BRIEF').fill(topic.brief);
  await formFrame.locator('#READER').fill(topic.reader);
  await formFrame.locator('#FEATURE').fill(topic.feature);
  await formFrame.locator('#COMPARE').fill(topic.compare);

  await formFrame.locator('input[name="READERNUM"]').fill(topic.readerNum);
  await selectOptionWhenReady(formFrame, '#LANGUAGE', topic.language, { fallback: true });
  await selectOptionWhenReady(formFrame, '#SCRIPTSOURCE', topic.scriptSource, { fallback: true });
  await selectOptionWhenReady(formFrame, '#SCRIPTSTYLE', topic.scriptStyle, { fallback: true });
  await setInputValue(formFrame, 'input[name="SCRIPTDATE"]', topic.scriptDate);
  await setInputValue(formFrame, 'input[name="MAKINGDATE"]', topic.makingDate);
  await setInputValue(formFrame, 'input[name="PUBLISHDATE"]', topic.publishDate);
  await selectOptionWhenReady(formFrame, '#AWARDS', topic.awards, { fallback: true });
  await selectOptionWhenReady(formFrame, '#COLORPRINT', topic.colorPrint, { fallback: true });
  await selectOptionWhenReady(formFrame, '#HAVECD', topic.haveCd, { required: false, fallback: true });
  await formFrame.locator('input[name="WORDS"]').fill(topic.words);
  await formFrame.locator('input[name="PRICE"]').fill(topic.price);
  await formFrame.locator('input[name="REMCHARNUM"]').fill(topic.remCharNum);
  await selectOptionWhenReady(formFrame, '#REMPAYMODE', topic.remPayMode, { fallback: true });
  await formFrame.locator('input[name="REMSTANDARD"]').fill(topic.remStandard);
  await selectOptionIfExists(formFrame, '#REMUNIT', topic.remUnit);
  await selectOptionWhenReady(formFrame, '#PUBLISHMODE', topic.publishMode, { fallback: true });
  await selectOptionWhenReady(formFrame, 'select[name="HAVEZZ"]', topic.haveZz, { fallback: true });
  await formFrame.locator('input[name="IMBURSEFEE"]').fill(topic.imburseFee);
  await formFrame.locator('input[name="IMBURSENUM"]').fill(topic.imburseNum);
  await selectOptionWhenReady(formFrame, 'select[name="HAVEBX"]', topic.haveBx, { fallback: true });
  await formFrame.locator('input[name="BSALENUM"]').fill(topic.bsaleNum);
  await formFrame.locator('input[name="BSALEDISCOUNT"]').fill(topic.bsaleDiscount);
  await selectOptionIfExists(formFrame, '#COMODE', topic.coMode);
  await setInputValueIfExists(formFrame, 'input[name="COBUYDISCOUNT"]', topic.coBuyDiscount);
  await selectOptionIfExists(formFrame, '#BSALEMODE', topic.bsaleMode);
  await selectOptionIfExists(formFrame, '#DIGITAL', topic.digital);
  await selectOptionIfExists(formFrame, '#EREMPAYMODE', topic.eRemPayMode);
  await setInputValueIfExists(formFrame, 'input[name="EREMSTANDARD"]', topic.eRemStandard);
  await formFrame.locator('input[name="TOTALNUM"]').fill(topic.totalNum);
  await formFrame.locator('input[name="FIRSTNUM"]').fill(topic.firstNum);
  await setRadioValue(formFrame, 'PROJECT', topic.project);
  await setRadioValue(formFrame, 'SCRIPTCLASSIFY', topic.scriptClassify);

  await setInputValue(formFrame, 'input[name="PRJEDITOR"]', topic.projectEditor);
  await setInputValue(formFrame, 'input[name="PRJEDITORNO"]', topic.projectEditorNo);
  await setInputValue(formFrame, 'input[name="PRJEDITORUID"]', topic.projectEditorUid);
  await setInputValue(formFrame, 'input[name="EDITOR"]', topic.editor);
  await setInputValue(formFrame, 'input[name="EDITORNO"]', topic.editorNo);
  await setInputValue(formFrame, 'input[name="EDITORUID"]', topic.editorUid);
  await setInputValue(formFrame, 'input[name="PRJDEPT"]', topic.projectDept);
  await setInputValue(formFrame, 'input[name="EDITORDEPT"]', topic.editorDept);
  await fillScoreGrid(formFrame, topic);
  await selectOptionWhenReady(formFrame, '#ISCOST', topic.isCost, { fallback: true });
  await selectOptionWhenReady(formFrame, '#IMPSCRIPT', topic.impScript, { fallback: true });
  await selectOptionWhenReady(formFrame, '#ISURGENT', topic.isUrgent, { fallback: true });
  await selectOptionWhenReady(formFrame, '#ISMEETING', topic.isMeeting, { fallback: true });
  await selectOptionIfExists(formFrame, '#BWCLASS', topic.bwClass);
  await setInputValueIfExists(formFrame, 'input[name="BWCIPCLASS"]', topic.bwCipClass);

  await typeTextLikeUser(formFrame, 'input[name="BOOKNAME"]', topic.bookName);
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
        options: el.tagName.toLowerCase() === 'select'
          ? Array.from(el.options).map((option) => ({ value: option.value, text: option.textContent.trim() }))
          : [],
      }));
  });
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
  await page.waitForTimeout(8000);
  const listFrame = page.frames().find((f) => f.url().includes('WorkFlow_Execute_Worklist'));
  if (!listFrame) throw new Error('Worklist frame not found during verification');

  const titles = await listFrame.locator('a').evaluateAll((anchors) => anchors
    .map((anchor) => (anchor.textContent || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean));
  const expectedCnoText = String(expectedCno || '').trim();
  const expectedBookNameText = String(expectedBookName || '').trim();
  const exactCurrent = titles.find((title) => (
    (!expectedCnoText || title.includes(expectedCnoText))
    && (!expectedBookNameText || title.includes(expectedBookNameText))
  ));
  const cnoOnly = expectedCnoText
    ? titles.find((title) => title.includes(expectedCnoText))
    : null;
  const bookNameOnly = expectedBookNameText
    ? titles.find((title) => title.includes(expectedBookNameText))
    : null;

  return {
    ok: !!exactCurrent,
    title: exactCurrent || null,
    cnoOnly: cnoOnly || null,
    bookNameOnly: bookNameOnly || null,
    recentTitles: titles.slice(0, 20),
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
      screenshot,
      popupUrl: popup.url(),
      frameUrl: formFrame.url(),
    };
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
}

async function submit(jsonPath) {
  const { absPath, data } = loadInput(jsonPath);
  const topic = withDefaults(data);
  if (!isValidPersonName(topic.authorName)) {
    throw new Error(`Invalid authorName: "${String(topic.authorName || '').slice(0, 80)}". Please provide a 2-8 character Chinese author name.`);
  }
  const outputDir = path.dirname(absPath);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });
  const dialogs = [];

  try {
    page.on('dialog', async (dialog) => {
      dialogs.push(dialog.message());
      await dialog.accept().catch(() => {});
    });

    await login(page);
    const authorResult = await saveAuthorMaintenance(page, topic, outputDir);
    const { popup, formFrame } = await openTopicPopup(page);
    await fillForm(formFrame, topic);
    const cno = await readInputValue(formFrame, '#CNO');

    const mainBefore = path.join(outputDir, 'bpm-main-before-save.png');
    const mainAfter = path.join(outputDir, 'bpm-main-after-save.png');
    await popup.screenshot({ path: mainBefore, fullPage: true });
    await clickWorkflowSaveAndWait(popup, { timeout: 8000, settleMs: 3000 });
    await popup.screenshot({ path: mainAfter, fullPage: true });

    const costFrame = await openCostEstimateForm(popup, formFrame, topic);
    await fillCostEstimateForm(costFrame, topic);
    const costBefore = path.join(outputDir, 'bpm-before-save.png');
    const costAfter = path.join(outputDir, 'bpm-after-save.png');
    await popup.screenshot({ path: costBefore, fullPage: true });
    await clickSaveAndWait(costFrame, { timeout: 30000, settleMs: 2000 });
    await popup.screenshot({ path: costAfter, fullPage: true });

    const verification = await verifyCreatedTitle(page, topic.bookName, cno);
    const result = {
      ok: verification.ok,
      title: verification.title,
      cno,
      verification,
      dialogs,
      expectedBookName: topic.bookName,
      authorResult,
      inputPath: absPath,
      screenshots: [
        mainBefore,
        mainAfter,
        costBefore,
        costAfter,
      ],
    };
    console.log(JSON.stringify(result, null, 2));
    if (!verification.ok) {
      const cnoMessage = cno ? ` with CNO "${cno}"` : '';
      const cnoOnlyMessage = verification.cnoOnly ? ` Found current CNO title: "${verification.cnoOnly}".` : '';
      const oldTitleMessage = verification.bookNameOnly ? ` Found another matching book title: "${verification.bookNameOnly}".` : '';
      throw new Error(`BPM save was not verified: "${topic.bookName}"${cnoMessage} was not found in the worklist after save.${cnoOnlyMessage}${oldTitleMessage}`);
    }
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
    await clickWorkflowSaveAndWait(popup, { timeout: 8000, settleMs: 3000 });
    const after = await collectFilledFormDiagnostics(formFrame);
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
  if (mode === 'dry-run' && jsonPath) {
    await dryRun(jsonPath);
    return;
  }
  if (mode === 'debug-main' && jsonPath) {
    await debugMain(jsonPath);
    return;
  }
  if (mode !== 'submit' || !jsonPath) {
    throw new Error('Usage: node fill_topic.js inspect [/abs/output/dir] OR node fill_topic.js dry-run /abs/path/topic.json OR node fill_topic.js debug-main /abs/path/topic.json OR node fill_topic.js submit /abs/path/topic.json');
  }
  await submit(jsonPath);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
