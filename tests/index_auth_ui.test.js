const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const source = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

function formMarkup(id) {
  const match = source.match(new RegExp(`<form[^>]*id="${id}"[\\s\\S]*?<\\/form>`));
  assert.ok(match, `${id} should be a form`);
  return match[0];
}

test("renders a quiet login and registration shell before the workspace", () => {
  assert.match(source, /id="authView"/);
  assert.match(source, /id="loginForm"/);
  assert.match(source, /id="registerForm"/);
  assert.match(source, /id="workspace"[^>]*hidden/);
});

test("registration collects only account, name, password, and password confirmation", () => {
  const registerForm = formMarkup("registerForm");
  const inputs = [...registerForm.matchAll(/<input\b[^>]*\bid="([^"]+)"[^>]*>/g)].map((match) => match[1]);

  assert.deepEqual(inputs, [
    "registerUsername",
    "registerDisplayName",
    "registerPassword",
    "registerPasswordConfirm"
  ]);
  assert.match(source, /id="registerDisplayName"/);
});

test("authenticated navigation exposes the current name and icon-only logout control", () => {
  assert.match(source, /id="currentUserName"/);
  assert.match(source, /id="bpmSettingsButton"[^>]*aria-label="BPM 配置"/);
  assert.match(source, /id="logoutButton"[^>]*aria-label="退出登录"/);
});

test("BPM credentials are configured per session without exposing stored secrets", () => {
  assert.doesNotMatch(source, /id="bpmUrl"/);
  assert.doesNotMatch(source, /id="bpmEditorName"/);
  assert.match(source, /id="bpmUser"/);
  assert.match(source, /id="bpmPassword"/);
  assert.match(source, /id="saveBpmCredentials"/);
  assert.match(source, /id="clearBpmCredentials"/);
  assert.match(source, /id="bpmCredentialAccount"/);
  assert.match(source, /async function loadBpmCredentialStatus\(/);
  assert.match(source, /apiFetch\("\/api\/integrations\/phei-bpm"/);
  assert.match(source, /method:\s*"PUT"/);
  assert.match(source, /method:\s*"DELETE"/);
  assert.match(source, /密码已保存/);
});

test("legacy browser BPM secrets are purged before user drafts are restored", () => {
  assert.match(source, /function purgeLegacyBpmStorage\(/);
  assert.match(source, /localStorage\.removeItem\("phei-bpm-credentials"\)/);
  assert.match(source, /delete data\.bpm/);
  assert.match(source, /delete data\.bpmTopic\.bpm/);
  assert.match(source, /purgeLegacyBpmStorage\(\);[\s\S]*loadCurrentUser\(\);/);
});

test("model configuration stays on the server and legacy browser configuration is removed", () => {
  ["modelUrl", "modelName", "apiKey", "saveModel"].forEach((id) => {
    assert.doesNotMatch(source, new RegExp(`id="${id}"`));
  });
  assert.doesNotMatch(source, /form\.append\("model(?:Url)?"/);
  assert.doesNotMatch(source, /form\.append\("apiKey"/);
  assert.match(source, /localStorage\.removeItem\("phei-model-config"\)/);
  assert.doesNotMatch(source, /localStorage\.(?:getItem|setItem)\("phei-model-config"/);
});

test("auth state is restored before the workspace is shown", () => {
  assert.match(source, /async function loadCurrentUser\(/);
  assert.match(source, /await apiFetch\("\/api\/auth\/me"/);
  assert.match(source, /showWorkspace\(data\.user\)/);
  assert.match(source, /showAuthView\("login"\)/);
});

test("business API requests use apiFetch and expired sessions return to login", () => {
  assert.match(source, /async function apiFetch\(url, options = \{\}\)/);
  assert.match(source, /response\.status === 401/);
  assert.doesNotMatch(source, /\bfetch\("\/api\//);
});

test("drafts are reset and restored only in the authenticated user's namespace", () => {
  assert.match(source, /function draftStorageKey\(user\)[\s\S]*user\.id/);
  assert.match(source, /function loadUserDraft\(user\)/);
  assert.match(source, /function showAuthView\([^)]*\)[\s\S]*clearWorkspaceState\(\)/);
  assert.match(source, /function showWorkspace\(user\)[\s\S]*clearWorkspaceState\(\)[\s\S]*loadUserDraft\(user\)/);
  assert.match(source, /localStorage\.setItem\(draftStorageKey\(currentUser\)/);
  assert.doesNotMatch(source, /localStorage\.getItem\(draftKey\)/);
  assert.doesNotMatch(source, /phei-report-draft-v2/);
});

test("untrusted report and job values are rendered as text instead of HTML", () => {
  const maliciousValue = '<img onerror="window.__pheiXss = true">';

  assert.match(maliciousValue, /<img onerror=/);
  assert.doesNotMatch(source, /\.innerHTML\s*=/);
  assert.match(source, /valueNode\.textContent = String\(value \|\| "未填写"\)/);
  assert.match(source, /jobTitle\.textContent = job\.title \|\| "未命名选题"/);
  assert.match(source, /jobLog\.textContent = logs/);
});

test("async workspace operations capture and verify the active session generation", () => {
  assert.match(source, /src="auth_session_generation\.js"/);
  assert.match(source, /const authSession = new AuthSessionGeneration\(\)/);
  assert.match(source, /function captureSession\(\)/);
  assert.match(source, /function isCurrentSession\(snapshot\)/);
  assert.match(source, /function showAuthView\([^)]*\)[\s\S]*authSession\.clear\(\)/);
  assert.match(source, /function showWorkspace\(user\)[\s\S]*authSession\.activate\(user\)/);
  assert.match(source, /async function loadCurrentUser\(session\)/);
  assert.match(source, /async function refreshBpmJobs\(session = captureSession\(\)\)/);
  assert.match(source, /const session = captureSession\(\);[\s\S]*await assertBackendReady\(session\)/);
  assert.match(source, /if \(!isCurrentSession\(session\)\) return;/);
  ["/api/import-bpm-sources", "/api/generate-report", "/api/export-docx", "/api/bpm-topic-jobs", "/api/bpm-author-jobs"].forEach((endpoint) => {
    const escaped = endpoint.replaceAll("/", "\\/");
    assert.match(source, new RegExp(`apiFetch\\("${escaped}",[\\s\\S]*?session`));
  });
});

test("auth view changes reset form busy state while stale submissions cannot restore it", () => {
  assert.match(source, /const authBusy = new AuthBusyState\(\)/);
  assert.match(source, /function setAuthControlsDisabled\(disabled\)/);
  assert.match(source, /\[loginForm, registerForm\][\s\S]*authSubmitButton\(form\)\.disabled = disabled/);
  assert.match(source, /document\.querySelectorAll\("\[data-auth-mode\]"\)[\s\S]*button\.disabled = disabled/);
  assert.match(source, /const busy = beginAuthSubmission\(form\)/);
  assert.match(source, /if \(!busy\) return;/);
  assert.match(source, /setAuthControlsDisabled\(true\)/);
  assert.match(source, /finishAuthSubmission\(form, busy\)/);
  assert.match(source, /async function loadCurrentUser[\s\S]*authBusy\.isBusy\(\)/);
});

test("loads only local fixed-version scripts and keeps Lucide initialization", () => {
  assert.doesNotMatch(source, /<script[^>]+src=["']https?:\/\//i);
  assert.doesNotMatch(source, /@latest/i);
  assert.match(source, /src="vendor\/lucide-0\.468\.0\.min\.js"/);
  assert.match(source, /window\.lucide\.createIcons\(\)/);
});
