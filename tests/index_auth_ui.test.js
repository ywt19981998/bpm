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
