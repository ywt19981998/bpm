const assert = require("node:assert/strict");
const test = require("node:test");

const { AuthBusyState, AuthSessionGeneration } = require("../auth_session_generation.js");

function deferred() {
  let resolve;
  const promise = new Promise((nextResolve) => {
    resolve = nextResolve;
  });
  return { promise, resolve };
}

test("drops a delayed user A response after logout and user B login", async () => {
  const session = new AuthSessionGeneration();
  session.activate({ id: 1 });
  const userARequest = session.capture();
  const delayedAResponse = deferred();
  const workspace = { userId: 1, draft: "A 草稿", jobs: ["A 任务"] };

  const applyAResponse = delayedAResponse.promise.then((result) => {
    session.commitIfCurrent(userARequest, () => Object.assign(workspace, result));
  });

  session.clear();
  session.activate({ id: 2 });
  Object.assign(workspace, { userId: 2, draft: "B 草稿", jobs: ["B 任务"] });
  delayedAResponse.resolve({ userId: 1, draft: "A 返回草稿", jobs: ["A 返回任务"] });
  await applyAResponse;

  assert.deepEqual(workspace, { userId: 2, draft: "B 草稿", jobs: ["B 任务"] });
});

test("invalidates concurrent auth restoration when a newer user becomes active", () => {
  const session = new AuthSessionGeneration();
  const restoringSession = session.capture();

  session.activate({ id: 2 });

  assert.equal(session.isCurrent(restoringSession), false);
  assert.equal(session.isCurrent(session.capture()), true);
});

test("cancelling auth resets both forms and ignores the stale request finally", async () => {
  const busy = new AuthBusyState();
  const pendingLogin = busy.begin("loginForm");
  const delayedLogin = deferred();
  const finishLogin = delayedLogin.promise.finally(() => busy.finish(pendingLogin));

  assert.equal(busy.isBusy("loginForm"), true);

  busy.reset();
  assert.equal(busy.isBusy("loginForm"), false);
  assert.equal(busy.isBusy("registerForm"), false);

  const pendingRegister = busy.begin("registerForm");
  delayedLogin.resolve();
  await finishLogin;

  assert.equal(busy.isBusy("loginForm"), false);
  assert.equal(busy.isBusy("registerForm"), true);
  assert.equal(busy.finish(pendingRegister), true);
  assert.equal(busy.isBusy("registerForm"), false);
});
