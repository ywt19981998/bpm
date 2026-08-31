const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.join(__dirname, "..");
const indexPath = path.join(root, "index.html");
const helperPath = path.join(root, "mail_ui_helpers.js");
const serverPath = path.join(root, "server.py");
const source = fs.readFileSync(indexPath, "utf8");
const serverSource = fs.readFileSync(serverPath, "utf8");

function functionBody(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} should exist`);
  const bodyStart = source.indexOf("{", start);
  let depth = 0;
  for (let index = bodyStart; index < source.length; index += 1) {
    if (source[index] === "{") depth += 1;
    if (source[index] === "}") depth -= 1;
    if (depth === 0) return source.slice(bodyStart + 1, index);
  }
  assert.fail(`${name} should have a complete body`);
}

function extractElement(id) {
  const start = source.indexOf(`id="${id}"`);
  assert.notEqual(start, -1, `${id} should exist`);
  const tagStart = source.lastIndexOf("<", start);
  const tag = source.slice(tagStart + 1).match(/^([a-z0-9-]+)/i)?.[1];
  assert.ok(tag, `${id} should have an opening tag`);
  const end = source.indexOf(`</${tag}>`, start);
  assert.notEqual(end, -1, `${id} should have a closing tag`);
  return source.slice(tagStart, end + tag.length + 3);
}

function loadHelpers() {
  assert.ok(fs.existsSync(helperPath), "mail_ui_helpers.js should exist");
  delete require.cache[require.resolve(helperPath)];
  return require(helperPath);
}

test("mail center is a first-level workspace with three operational columns", () => {
  assert.match(source, /id="menuMail"[^>]*title="邮件中心"/);
  assert.match(source, /id="mailView"/);
  assert.match(source, /id="mailTemplatePanel"/);
  assert.match(source, /id="mailComposeEditor"/);
  assert.match(source, /id="mailRecipientPanel"/);
  assert.match(source, /\.mail-workspace\s*\{[^}]*grid-template-columns:/s);
  assert.match(source, /@media[^}]+max-width:\s*1100px[\s\S]*#mailRecipientPanel\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/s);
});

test("mail recipients exist only in the right panel", () => {
  const editor = extractElement("mailComposeEditor");
  const recipientPanel = extractElement("mailRecipientPanel");

  assert.doesNotMatch(editor, /mail-recipient-(?:chip|list|row)/);
  assert.match(recipientPanel, /id="mailRecipientList"/);
  assert.match(recipientPanel, /id="mailInvalidRecipientList"/);
  assert.match(recipientPanel, /id="mailRecipientFile"[^>]+accept="[^"]*\.csv[^"]*\.xlsx/);
});

test("mail center exposes template CRUD, server draft, preview, history and retry actions", () => {
  for (const id of [
    "mailTemplateSearch",
    "createMailTemplate",
    "saveMailTemplate",
    "duplicateMailTemplate",
    "deleteMailTemplate",
    "mailSubject",
    "mailBody",
    "previewMail",
    "submitMail",
    "mailBatchHistory",
    "refreshMailBatches"
  ]) {
    assert.match(source, new RegExp(`id="${id}"`));
  }

  assert.match(source, /apiFetch\("\/api\/mail\/templates/);
  assert.match(source, /apiFetch\("\/api\/mail\/draft/);
  assert.match(source, /apiFetch\("\/api\/mail\/preview/);
  assert.match(source, /apiFetch\("\/api\/mail\/batches/);
  assert.match(functionBody("scheduleMailDraftSave"), /setTimeout\([^,]+,\s*700\)/s);
  assert.doesNotMatch(source, /localStorage\.(?:getItem|setItem)\([^\n]*mail/i);
  assert.doesNotMatch(source, /localStorage\.(?:getItem|setItem)\([^\n]*smtp/i);
});

test("recipient uploads replace the current list only after confirmation", () => {
  const body = functionBody("parseMailRecipientFile");

  assert.match(body, /\.csv/);
  assert.match(body, /\.xlsx/);
  assert.match(body, /mailState\.recipients\.length[\s\S]*window\.confirm\([^)]*替换/);
  assert.match(body, /FormData/);
  assert.match(body, /apiFetch\("\/api\/mail\/recipients\/parse/);
});

test("send action confirms, sends a stable idempotency key and blocks double clicks", () => {
  const body = functionBody("submitMailBatch");

  assert.match(body, /if \(mailState\.sending\) return/);
  assert.match(body, /window\.confirm\([^)]*发送/);
  assert.match(body, /confirmed:\s*true/);
  assert.match(body, /mailState\.pendingIdempotencyKey\s*\|\|=/);
  assert.match(body, /"Idempotency-Key":\s*mailState\.pendingIdempotencyKey/);
  assert.match(body, /submitMail\.disabled\s*=\s*true/);
  assert.match(body, /apiFetch\("\/api\/mail\/batches"/);
});

test("failed batches can be retried with confirmation and a stable key", () => {
  const body = functionBody("retryMailBatch");

  assert.match(body, /window\.confirm\([^)]*重试/);
  assert.match(body, /confirmed:\s*true/);
  assert.match(body, /mailState\.retryIdempotencyKeys/);
  assert.match(body, /"Idempotency-Key":\s*requestKey/);
  assert.match(body, /`\/api\/mail\/batches\/\$\{batchId\}\/retry`/);
});

test("mail send and retry responses are ignored after the active user changes", () => {
  for (const name of ["submitMailBatch", "retryMailBatch"]) {
    const body = functionBody(name);
    assert.match(body, /const session = captureSession\(\)/);
    assert.match(
      body,
      /const response = await apiFetch\([\s\S]*?if \(!isCurrentSession\(session\)\) return;[\s\S]*?if \(!response\.ok\)/
    );
  }
});

test("mail helper extracts unique variables in document order", () => {
  const { extractTemplateVariables } = loadHelpers();

  assert.deepEqual(
    extractTemplateVariables("{{ 姓名 }}老师，来自{{学校}}。{{姓名}}"),
    ["姓名", "学校"]
  );
});

test("mail helper maps batch states to user-facing metadata", () => {
  const { getMailBatchStatus } = loadHelpers();

  assert.deepEqual(getMailBatchStatus("partial_failed"), {
    label: "部分失败",
    tone: "warning",
    terminal: true
  });
  assert.equal(getMailBatchStatus("running").label, "发送中");
});

test("mail helper summarizes valid, invalid and duplicate recipients", () => {
  const { summarizeRecipients } = loadHelpers();
  const result = summarizeRecipients(
    [{ email: "a@example.com" }, { email: "b@example.com" }],
    [{ reason: "邮箱格式无效" }],
    3
  );

  assert.deepEqual(result, {
    validCount: 2,
    invalidCount: 1,
    duplicateCount: 3,
    totalCount: 6,
    canSend: true
  });
});

test("mail helper creates server-compatible idempotency keys", () => {
  const { createIdempotencyKey } = loadHelpers();
  const key = createIdempotencyKey("send", "fixed-random-value");

  assert.equal(key, createIdempotencyKey("send", "fixed-random-value"));
  assert.match(key, /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/);
});

test("mail helper is served as a fixed local asset", () => {
  assert.match(source, /src="mail_ui_helpers\.js"/);
  assert.match(serverSource, /"\/mail_ui_helpers\.js":\s*\("mail_ui_helpers\.js",\s*"application\/javascript; charset=utf-8"\)/s);
});
