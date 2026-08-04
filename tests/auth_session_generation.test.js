const assert = require("node:assert/strict");
const test = require("node:test");

const {
  AuthBusyState,
  AuthSessionGeneration,
  shouldRestoreAuthControls
} = require("../auth_session_generation.js");

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

test("serializes authentication so a delayed request cannot start a second login", async () => {
  const busy = new AuthBusyState();
  const pendingA = busy.begin("loginForm");
  const delayedA = deferred();
  const finishA = delayedA.promise.finally(() => busy.finish(pendingA));

  assert.ok(pendingA);
  assert.equal(busy.begin("registerForm"), null);
  assert.equal(busy.isBusy(), true);

  delayedA.resolve();
  await finishA;

  const pendingB = busy.begin("registerForm");
  assert.ok(pendingB);
  assert.equal(busy.finish(pendingB), true);
  assert.equal(busy.isBusy(), false);
});

test("keeps a delayed logout exclusive until its response has completed", async () => {
  const busy = new AuthBusyState();
  const pendingLogout = busy.begin("logout");
  const delayedLogout = deferred();
  const finishLogout = delayedLogout.promise.finally(() => busy.finish(pendingLogout));

  assert.ok(pendingLogout);
  assert.equal(busy.begin("loginForm"), null);
  assert.equal(busy.begin("registerForm"), null);

  delayedLogout.resolve();
  await finishLogout;

  const pendingLogin = busy.begin("loginForm");
  assert.ok(pendingLogin);
  assert.equal(busy.finish(pendingLogin), true);
});

test("recovers auth controls when a background 401 stales a pending logout", async () => {
  const busy = new AuthBusyState();
  const session = new AuthSessionGeneration();
  session.activate({ id: 1 });
  const logoutSession = session.capture();
  const pendingLogout = busy.begin("logout");
  const delayedLogout = deferred();
  let authViewVisible = false;
  let currentUser = { id: 1 };
  let authControlsDisabled = true;

  assert.ok(pendingLogout);
  assert.equal(busy.begin("loginForm"), null);

  // A concurrent business request receives 401 and moves the page to login.
  session.clear();
  currentUser = null;
  authViewVisible = true;
  assert.equal(session.isCurrent(logoutSession), false);
  assert.equal(authControlsDisabled, true);

  delayedLogout.resolve();
  await delayedLogout.promise;
  assert.equal(busy.finish(pendingLogout), true);
  if (shouldRestoreAuthControls({ authViewVisible, currentUser, isBusy: busy.isBusy() })) {
    authControlsDisabled = false;
  }

  assert.equal(authControlsDisabled, false);
  const pendingLogin = busy.begin("loginForm");
  assert.ok(pendingLogin);
  assert.equal(busy.finish(pendingLogin), true);
});
