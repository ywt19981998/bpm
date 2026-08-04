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
  assert.match(source, /id="logoutButton"[^>]*aria-label="退出登录"/);
});

test("auth state is restored before the workspace is shown", () => {
  assert.match(source, /async function loadCurrentUser\(\)/);
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
