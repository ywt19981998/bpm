# User Authentication and BPM Credential Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add open internal registration, persistent authenticated sessions, encrypted per-user BPM credentials, user-owned persistent BPM jobs, and server-controlled DeepSeek V4 model configuration.

**Architecture:** Add a focused `AppStore` SQLite boundary for migrations, password hashing, sessions, encrypted integration credentials, and jobs. Keep the existing `SimpleHTTPRequestHandler` server, but route all business APIs through cookie authentication and inject trusted user identity and decrypted BPM credentials on the server. Keep the single-file frontend while adding an auth shell and a BPM settings panel; remove all client-side model and API-key configuration.

**Tech Stack:** Python 3.12+, SQLite, `hashlib.scrypt`, `cryptography` AES-GCM, `python-dotenv`, `http.server`, vanilla HTML/CSS/JavaScript, Node test runner, Python `unittest`, Playwright BPM worker.

## Global Constraints

- Registration collects only account, password, and display name.
- Anyone who can reach the internal URL can register; no invitation code, phone verification, or external OAuth.
- Website passwords are stored only as salted scrypt hashes.
- External credentials are stored only as one AES-GCM encrypted JSON payload per user and system type.
- `APP_CREDENTIAL_KEY` and `DEEPSEEK_API_KEY` stay in server environment configuration and never enter HTML, SQLite, logs, task payloads, or Git.
- Full report generation uses `deepseek-v4-pro`; targeted lightweight fallback calls may use `deepseek-v4-flash`.
- Existing report generation, DOCX export, author maintenance, and topic declaration behavior must remain available after login.
- Existing unrelated uncommitted changes in `fill_topic.js` and `tests/fill_topic_interactions.test.js` must not be reverted or mixed into unrelated commits.

---

## File Structure

- Create `app_storage.py`: SQLite migrations, password hashing, sessions, integration credential encryption, and persistent jobs.
- Create `tests/test_app_storage.py`: real database and crypto tests using temporary directories.
- Create `tests/test_server_auth.py`: HTTP integration tests against an ephemeral `ThreadingHTTPServer`.
- Create `tests/index_auth_ui.test.js`: source-level UI contract tests for auth, BPM settings, and hidden model configuration.
- Create `.env.example`: non-secret server configuration names and generation command for the credential key.
- Modify `server.py`: load local environment, initialize `AppStore`, add auth/credential APIs, protect business APIs, inject user identity and BPM credentials, persist jobs, and fix model routing.
- Modify `index.html`: login/register shell, current-user menu, persistent BPM settings, authenticated fetch handling, and removal of model controls.
- Modify `requirements.txt`: add `cryptography` and `python-dotenv`.
- Modify `.gitignore`: ignore `data/`, SQLite sidecar files, and local environment files while retaining `.env.example`.
- Modify `README.md`: document initial configuration, key generation, startup, registration, and backup.

---

### Task 0: Preserve the Existing BPM Worklist Repair

**Files:**
- Modify: `skills/phei-bpm-topic-declaration/scripts/fill_topic.js`
- Modify: `tests/fill_topic_interactions.test.js`

**Interfaces:**
- Preserves: `waitForSavedTopicLink(page, options)` and its stale-iframe regression test from the already completed repair.

- [ ] **Step 1: Re-run the existing BPM interaction and full test suites**

Run: `node --test tests/fill_topic_interactions.test.js && npm test`

Expected: the saved-draft lookup regression passes and the full suite is green.

- [ ] **Step 2: Review the isolated diff**

Run: `git diff --check -- skills/phei-bpm-topic-declaration/scripts/fill_topic.js tests/fill_topic_interactions.test.js && git diff --stat`

Expected: no whitespace errors and only the previously reviewed stale-worklist repair appears in these two files.

- [ ] **Step 3: Commit the repair separately**

```bash
git add skills/phei-bpm-topic-declaration/scripts/fill_topic.js tests/fill_topic_interactions.test.js
git commit -m "fix: rescan BPM worklists after draft save"
```

---

### Task 1: SQLite Users, Password Hashes, and Sessions

**Files:**
- Create: `app_storage.py`
- Create: `tests/test_app_storage.py`
- Modify: `requirements.txt`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `AppStore(db_path: Path, credential_key: str | None)`.
- Produces: `register_user(username: str, password: str, display_name: str) -> dict`.
- Produces: `authenticate_user(username: str, password: str) -> dict | None`.
- Produces: `create_session(user_id: int, ttl_seconds: int = 604800) -> str`.
- Produces: `get_user_for_session(token: str) -> dict | None`.
- Produces: `delete_session(token: str) -> None`.

- [ ] **Step 1: Add failing database tests**

Add tests that create a temporary SQLite database, register `editor01`, assert that duplicate normalized usernames fail, assert that the raw password is absent from every text column, authenticate successfully, reject a wrong password, create a session, resolve it, and delete it.

```python
def test_register_authenticate_and_session_round_trip(self):
    user = self.store.register_user(" Editor01 ", "S3cure-pass", "张编辑")
    self.assertEqual(user["username"], "editor01")
    self.assertEqual(user["display_name"], "张编辑")
    self.assertNotIn("S3cure-pass", self.database_text())
    self.assertEqual(self.store.authenticate_user("EDITOR01", "S3cure-pass")["id"], user["id"])
    self.assertIsNone(self.store.authenticate_user("editor01", "wrong-pass"))
    token = self.store.create_session(user["id"], ttl_seconds=3600)
    self.assertEqual(self.store.get_user_for_session(token)["id"], user["id"])
    self.store.delete_session(token)
    self.assertIsNone(self.store.get_user_for_session(token))
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run: `python3 -m unittest tests.test_app_storage.AppStoreAuthTests -v`

Expected: FAIL because `app_storage.AppStore` does not exist.

- [ ] **Step 3: Implement migrations, scrypt hashes, and session tokens**

Implement migrations for `schema_migrations`, `users`, and `sessions`. Normalize usernames with `strip().lower()`, enforce 3-40 characters using `[a-z0-9._-]`, require a non-empty display name and an 8-character password, store scrypt metadata in a versioned string, and store only SHA-256 session-token hashes.

```python
class AppStore:
    def __init__(self, db_path: Path, credential_key: str | None = None):
        self.db_path = Path(db_path)
        self.credential_key = credential_key
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection
```

Use `hashlib.scrypt(password_bytes, salt=salt, n=16384, r=8, p=1, dklen=32)` and `hmac.compare_digest` for password verification. Generate session tokens with `secrets.token_urlsafe(32)` and store `sha256(token).hexdigest()`.

- [ ] **Step 4: Add dependencies and ignore runtime data**

Set `requirements.txt` to include:

```text
python-docx>=1.1.2
cryptography>=42.0.0
python-dotenv>=1.0.1
```

Add `data/`, `*.db-wal`, and `*.db-shm` to `.gitignore`; retain the existing `.env` rules and add `!.env.example` so the non-secret template can be committed.

- [ ] **Step 5: Run the storage tests**

Run: `python3 -m unittest tests.test_app_storage.AppStoreAuthTests -v`

Expected: all authentication and session tests PASS.

- [ ] **Step 6: Commit the storage foundation**

```bash
git add app_storage.py tests/test_app_storage.py requirements.txt .gitignore
git commit -m "feat: add SQLite user and session storage"
```

---

### Task 2: Encrypted Integration Credentials

**Files:**
- Modify: `app_storage.py`
- Modify: `tests/test_app_storage.py`

**Interfaces:**
- Consumes: `AppStore` from Task 1.
- Produces: `put_integration_credentials(user_id: int, system_type: str, account: str, password: str) -> None`.
- Produces: `get_integration_credentials(user_id: int, system_type: str) -> dict | None`.
- Produces: `get_integration_status(user_id: int, system_type: str) -> dict`.
- Produces: `delete_integration_credentials(user_id: int, system_type: str) -> None`.

- [ ] **Step 1: Add failing credential-encryption tests**

Test a round trip with a random 32-byte URL-safe base64 key, assert that neither account nor password appears in the database bytes, assert that status returns `configured` plus a masked account without a password, assert user isolation, assert deletion, and assert that a wrong or missing key raises `CredentialConfigurationError`.

```python
def test_credentials_are_encrypted_and_isolated(self):
    self.store.put_integration_credentials(self.user_id, "phei_bpm", "yewt", "bpm-secret")
    self.assertNotIn("yewt", self.database_text())
    self.assertNotIn("bpm-secret", self.database_text())
    self.assertEqual(
        self.store.get_integration_credentials(self.user_id, "phei_bpm"),
        {"account": "yewt", "password": "bpm-secret"},
    )
    self.assertEqual(
        self.store.get_integration_status(self.user_id, "phei_bpm"),
        {"configured": True, "accountMasked": "y***t"},
    )
```

- [ ] **Step 2: Run the credential tests and verify the expected failure**

Run: `python3 -m unittest tests.test_app_storage.AppStoreCredentialTests -v`

Expected: FAIL because integration credential methods do not exist.

- [ ] **Step 3: Implement one-payload AES-GCM encryption**

Create the `integration_credentials` migration with `UNIQUE(user_id, system_type)`. Decode `APP_CREDENTIAL_KEY` with URL-safe base64 and require exactly 32 bytes. Encrypt one compact JSON payload using a new 12-byte nonce per save and authenticated associated data `f"{user_id}:{system_type}:v1"`.

```python
payload = json.dumps(
    {"account": account.strip(), "password": password},
    ensure_ascii=False,
    separators=(",", ":"),
).encode("utf-8")
nonce = os.urandom(12)
ciphertext = AESGCM(key).encrypt(nonce, payload, associated_data)
```

Never return decrypted credentials from `get_integration_status`.

- [ ] **Step 4: Run all storage tests**

Run: `python3 -m unittest tests.test_app_storage -v`

Expected: authentication, session, encryption, isolation, and deletion tests PASS.

- [ ] **Step 5: Commit encrypted credentials**

```bash
git add app_storage.py tests/test_app_storage.py
git commit -m "feat: encrypt per-user integration credentials"
```

---

### Task 3: HTTP Authentication and Protected Business APIs

**Files:**
- Modify: `server.py`
- Create: `tests/test_server_auth.py`

**Interfaces:**
- Consumes: `AppStore` authentication and sessions.
- Produces: `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`.
- Produces: `Handler.current_user() -> dict | None` and `Handler.require_user() -> dict | None`.

- [ ] **Step 1: Add failing HTTP authentication tests**

Start `ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)` with a temporary `server.APP_STORE`. Test registration response and `Set-Cookie`, authenticated `/api/auth/me`, logout, rejected wrong login, and a 401 response from `/api/bpm-jobs` and `/api/generate-report` without a session.

```python
status, headers, body = self.request(
    "POST",
    "/api/auth/register",
    {"username": "editor01", "password": "S3cure-pass", "displayName": "张编辑"},
)
self.assertEqual(status, 201)
self.cookie = headers["Set-Cookie"].split(";", 1)[0]
status, _, me = self.request("GET", "/api/auth/me", cookie=self.cookie)
self.assertEqual(status, 200)
self.assertEqual(json.loads(me)["user"]["displayName"], "张编辑")
```

- [ ] **Step 2: Run the HTTP tests and verify 404/unauthorized failures**

Run: `python3 -m unittest tests.test_server_auth.ServerAuthHttpTests -v`

Expected: FAIL because authentication routes and authorization guards do not exist.

- [ ] **Step 3: Load environment configuration before server constants**

Call `load_dotenv(ROOT / ".env")` before reading model, database, or key settings. Initialize:

```python
APP_STORE = AppStore(
    Path(os.environ.get("PHEI_DB_PATH", ROOT / "data" / "app.db")),
    os.environ.get("APP_CREDENTIAL_KEY", ""),
)
SESSION_COOKIE_NAME = "phei_session"
```

- [ ] **Step 4: Implement JSON helpers, cookie parsing, and auth routes**

Use `http.cookies.SimpleCookie`. Set successful session cookies with `Path=/; HttpOnly; SameSite=Lax; Max-Age=604800`. Clear them with `Max-Age=0`. Return only `{id, username, displayName}`.

```python
def require_user(self):
    user = self.current_user()
    if user:
        return user
    self.send_json(401, {"error": "请先登录。", "code": "AUTH_REQUIRED"})
    return None
```

Protect every existing `/api/*` route except `/api/health`, `/api/auth/register`, and `/api/auth/login`. Static files remain reachable so the login shell can load.

- [ ] **Step 5: Run HTTP and existing tests**

Run: `python3 -m unittest tests.test_server_auth -v && npm test`

Expected: auth tests PASS and existing source/syntax tests remain green.

- [ ] **Step 6: Commit HTTP authentication**

```bash
git add server.py tests/test_server_auth.py
git commit -m "feat: add session-authenticated HTTP APIs"
```

---

### Task 4: Persistent BPM Settings and Server-Side Credential Injection

**Files:**
- Modify: `server.py`
- Modify: `skills/phei-bpm-topic-declaration/scripts/fill_topic.js`
- Modify: `tests/test_server_auth.py`
- Modify: `tests/server_bpm_jobs.test.js`
- Modify: `tests/fill_topic_interactions.test.js`

**Interfaces:**
- Consumes: `AppStore` integration credential methods.
- Produces: `GET`, `PUT`, and `DELETE /api/integrations/phei-bpm`.
- Changes: BPM job creation receives `user: dict`, obtains credentials from `APP_STORE`, and ignores client-supplied `bpm` values.
- Changes: Playwright preserves editor identity automatically supplied by the logged-in BPM account, or uses the BPM person picker by website display name before any save.

- [ ] **Step 1: Add failing BPM settings API tests**

Test 401 without a session, 400 for empty account/password, successful save, masked GET response, update, clear, and user isolation. Assert no response body contains the test password.

```python
status, _, body = self.request(
    "PUT",
    "/api/integrations/phei-bpm",
    {"account": "editor-bpm", "password": "bpm-secret"},
    cookie=self.cookie,
)
self.assertEqual(status, 200)
self.assertNotIn("bpm-secret", body)
status, _, body = self.request("GET", "/api/integrations/phei-bpm", cookie=self.cookie)
self.assertEqual(json.loads(body), {"configured": True, "accountMasked": "e********m"})
```

- [ ] **Step 2: Add a failing server-source test for trusted credential injection**

Require `create_bpm_job` to accept the authenticated user and obtain `phei_bpm` credentials from `APP_STORE`; reject direct password reads from `payload.get("bpm")`.

```javascript
assert.match(source, /get_integration_credentials\(user\["id"\],\s*"phei_bpm"\)/);
assert.doesNotMatch(createJobBody, /credentials\s*=\s*payload\.get\("bpm"\)/);
```

- [ ] **Step 3: Run the new tests and verify failures**

Run: `python3 -m unittest tests.test_server_auth.ServerCredentialHttpTests -v && node --test tests/server_bpm_jobs.test.js`

Expected: FAIL because credential APIs and server-side injection are missing.

- [ ] **Step 4: Implement credential routes and BPM job injection**

Add `do_PUT` and `do_DELETE` routing. In `handle_bpm_job`, resolve the current user, load credentials, and create an in-memory worker-only payload copy:

```python
credentials = APP_STORE.get_integration_credentials(user["id"], "phei_bpm")
if not credentials:
    raise ValueError("请先保存 BPM 账号和密码。")
trusted_payload = deepcopy(payload)
trusted_payload["editorName"] = user["display_name"]
trusted_payload["bpm"] = {
    "url": os.environ.get("BPM_URL", "http://bpm.phei.com.cn:8088/portal/r/w"),
    "user": credentials["account"],
    "name": user["display_name"],
    "password": credentials["password"],
}
```

Keep the existing worker cleanup that removes `payload["bpm"]["password"]` after completion. Do not persist `trusted_payload`.

- [ ] **Step 5: Run auth, credential, and full tests**

Before the full run, add a Playwright interaction regression that requires `fillForm` to call `ensureEditorIdentity(formFrame, topic)` and verifies that `ensureEditorIdentity` reads existing `PRJEDITOR`, `PRJEDITORNO`, `EDITOR`, and `EDITORNO` values before it calls `selectBpmPerson`. Implement this behavior:

```javascript
async function ensureEditorIdentity(formFrame, topic) {
  const projectEditor = await readInputValue(formFrame, 'input[name="PRJEDITOR"]');
  const editor = await readInputValue(formFrame, 'input[name="EDITOR"]');
  if (projectEditor === topic.projectEditor && editor === topic.editor) return;
  await selectBpmPerson(formFrame, 'input[name="PRJEDITOR"]', topic.projectEditor, '策划编辑');
  await selectBpmPerson(formFrame, 'input[name="EDITOR"]', topic.editor, '拟责任编辑');
}
```

The picker must populate BPM's associated hidden IDs. If the person is not found, propagate the existing picker error before the temporary-save button is clicked. Remove unconditional writes of `PRJEDITORNO`, `PRJEDITORUID`, `EDITORNO`, and `EDITORUID`; BPM owns those values.

Run: `python3 -m unittest tests.test_app_storage tests.test_server_auth -v && node --test tests/fill_topic_interactions.test.js && npm test`

Expected: all tests PASS.

- [ ] **Step 6: Commit persistent BPM settings**

```bash
git add server.py skills/phei-bpm-topic-declaration/scripts/fill_topic.js tests/test_server_auth.py tests/server_bpm_jobs.test.js tests/fill_topic_interactions.test.js
git commit -m "feat: use encrypted per-user BPM settings"
```

---

### Task 5: User-Owned Persistent BPM Jobs

**Files:**
- Modify: `app_storage.py`
- Modify: `server.py`
- Modify: `tests/test_app_storage.py`
- Modify: `tests/test_server_auth.py`

**Interfaces:**
- Produces: `create_job(user_id, job_type, title, public_payload) -> dict`.
- Produces: `update_job(job_id, user_id, status, result=None, error_summary=None) -> None`.
- Produces: `append_job_log(job_id, user_id, message) -> None`.
- Produces: `list_jobs(user_id, limit=50) -> list[dict]`.

- [ ] **Step 1: Add failing persistent-job tests**

Create jobs for two users, restart `AppStore` using the same database, and assert each user sees only their own jobs. Assert `queued -> running -> succeeded` and `queued -> running -> failed` transitions persist. Search database bytes for test BPM passwords and confirm absence.

```python
job = self.store.create_job(self.user_id, "topic", "测试选题", {"createdBy": "张编辑"})
self.store.update_job(job["id"], self.user_id, "running")
self.store.append_job_log(job["id"], self.user_id, "开始填报")
self.store.update_job(job["id"], self.user_id, "succeeded", result={"cno": "XT20260001"})
reopened = AppStore(self.db_path, self.key)
self.assertEqual(reopened.list_jobs(self.user_id)[0]["status"], "succeeded")
```

- [ ] **Step 2: Run persistent-job tests and verify failure**

Run: `python3 -m unittest tests.test_app_storage.AppStoreJobTests -v`

Expected: FAIL because the jobs migration and methods do not exist.

- [ ] **Step 3: Implement the jobs migration and repository methods**

Store public job fields and JSON logs/results only. Use `succeeded`, not the old `completed`, as the terminal success status. Enforce user ownership in every update query with `WHERE id = ? AND user_id = ?`.

- [ ] **Step 4: Replace process-memory public job state**

Keep `JOB_QUEUE` for active worker coordination, but replace `JOBS` reads/writes with `APP_STORE`. Queue items remain `(job_id, user_id, job_type, trusted_payload)`. `/api/bpm-jobs` calls `APP_STORE.list_jobs(current_user["id"])`.

- [ ] **Step 5: Add and run HTTP persistence/isolation tests**

Test that a second authenticated user cannot see the first user's jobs and that jobs remain visible after a new `AppStore` instance is assigned to `server.APP_STORE`.

Run: `python3 -m unittest tests.test_app_storage tests.test_server_auth -v && npm test`

Expected: all storage, HTTP, and existing tests PASS.

- [ ] **Step 6: Commit persistent jobs**

```bash
git add app_storage.py server.py tests/test_app_storage.py tests/test_server_auth.py
git commit -m "feat: persist user-owned BPM jobs"
```

---

### Task 6: Login/Register Frontend and Authenticated App Shell

**Files:**
- Modify: `index.html`
- Create: `tests/index_auth_ui.test.js`

**Interfaces:**
- Consumes: `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`.
- Produces: `apiFetch(url, options)` that redirects to the auth shell on 401.
- Produces: `showAuthView(mode)`, `showWorkspace(user)`, and `loadCurrentUser()`.

- [ ] **Step 1: Add failing UI contract tests**

Assert that login and registration forms exist, registration has exactly username/password/confirmation/display-name fields, authenticated user name and logout controls exist, all business fetches use `apiFetch`, and the workspace remains hidden until `/api/auth/me` succeeds.

```javascript
assert.match(source, /id="loginForm"/);
assert.match(source, /id="registerForm"/);
assert.match(source, /id="registerDisplayName"/);
assert.match(source, /id="currentUserName"/);
assert.match(source, /function apiFetch\(/);
assert.match(source, /response\.status === 401/);
```

- [ ] **Step 2: Run the UI tests and verify failure**

Run: `node --test tests/index_auth_ui.test.js`

Expected: FAIL because the auth shell does not exist.

- [ ] **Step 3: Add the auth shell and user menu**

Add a quiet full-height auth view with Login and Register tabs. Keep form controls compact, use the existing typography and colors, and hide the application workspace with a single root-level `hidden` attribute until authenticated. Add the current user's display name and a logout icon button to the existing navigation.

- [ ] **Step 4: Implement authenticated fetch behavior**

Implement:

```javascript
async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 401) {
    currentUser = null;
    showAuthView("login");
    throw new Error("登录已过期，请重新登录");
  }
  return response;
}
```

Replace existing business `fetch` calls with `apiFetch`. Registration validates matching passwords before sending. On successful login or registration, set `currentUser`, show the workspace, populate the user's name, and initialize report/BPM data.

- [ ] **Step 5: Run UI and full tests**

Run: `node --test tests/index_auth_ui.test.js && npm test`

Expected: auth UI tests and all existing tests PASS.

- [ ] **Step 6: Commit the authenticated frontend shell**

```bash
git add index.html tests/index_auth_ui.test.js
git commit -m "feat: add login and registration interface"
```

---

### Task 7: Persistent BPM Settings UI and Trusted User Name

**Files:**
- Modify: `index.html`
- Modify: `tests/index_auth_ui.test.js`
- Modify: `tests/index_bpm_actions.test.js`

**Interfaces:**
- Consumes: `/api/integrations/phei-bpm`.
- Changes: `bpmEditorName()` returns `currentUser.displayName`.
- Changes: `currentBpmPayload()` no longer includes `bpm` credentials or an editable `editorName`.

- [ ] **Step 1: Add failing BPM settings UI tests**

Assert that the BPM address and editor-name inputs are removed, saved state is loaded from the integration API, save and clear buttons exist, queue payloads contain no password, and the current user's name is used for report export and BPM editor fields.

```javascript
assert.doesNotMatch(source, /id="bpmEditorName"/);
assert.doesNotMatch(source, /id="bpmUrl"/);
assert.match(source, /id="saveBpmCredentials"/);
assert.match(source, /id="clearBpmCredentials"/);
assert.match(source, /currentUser\.displayName/);
assert.doesNotMatch(currentPayloadBody, /password:/);
```

- [ ] **Step 2: Run the BPM UI tests and verify failure**

Run: `node --test tests/index_auth_ui.test.js tests/index_bpm_actions.test.js`

Expected: FAIL because credentials are still sent in each job payload.

- [ ] **Step 3: Replace the BPM login form with persistent settings**

Show account and password inputs only for saving/updating. GET status populates the masked account indicator and “密码已保存”. Saving calls PUT; clearing calls DELETE after confirmation. Queue buttons require only `bpmCredentialConfigured === true`.

- [ ] **Step 4: Remove client credential transport and trust the session name**

Set:

```javascript
function bpmEditorName() {
  return currentUser?.displayName || "";
}

function currentBpmPayload() {
  const title = document.getElementById("projectName").textContent || "选题策划报告";
  bpmTopic = currentBpmTopic();
  return { title, sections, scores: scoreItems, total: currentScoreTotal(), bpmTopic };
}
```

Do not clear the saved credential state after a job is queued.

Update `jobStatusLabel` and `jobStatusClass` to treat `succeeded` as the successful terminal status; remove the old `completed` branch after persistent-job migration.

- [ ] **Step 5: Run UI and full tests**

Run: `node --test tests/index_auth_ui.test.js tests/index_bpm_actions.test.js && npm test`

Expected: all tests PASS.

- [ ] **Step 6: Commit persistent BPM settings UI**

```bash
git add index.html tests/index_auth_ui.test.js tests/index_bpm_actions.test.js
git commit -m "feat: add persistent per-user BPM settings UI"
```

---

### Task 8: Server-Controlled DeepSeek V4 Configuration

**Files:**
- Modify: `server.py`
- Modify: `index.html`
- Modify: `tests/test_server_auth.py`
- Modify: `tests/index_auth_ui.test.js`
- Create: `.env.example`

**Interfaces:**
- Changes: `generate_report_from_upload(file_bytes, filename)` uses server constants.
- Produces: `DEFAULT_MODEL = "deepseek-v4-pro"` and `FAST_MODEL = "deepseek-v4-flash"`.
- Removes: client `modelUrl`, `modelName`, and `apiKey` form fields.

- [ ] **Step 1: Add failing model-configuration tests**

Assert that a client-supplied model URL, model name, and API key are ignored; the model call receives the server's Pro model. Assert that HTML has no model URL/model/API-key inputs and clears legacy `phei-model-config` local storage.

```python
with mock.patch.object(server, "call_model", return_value=self.valid_model_result) as call:
    self.post_generate_form(
        fields={"model": "attacker-model", "apiKey": "attacker-key", "modelUrl": "https://attacker.invalid"},
        cookie=self.cookie,
    )
    self.assertEqual(call.call_args.args[3], "deepseek-v4-pro")
```

- [ ] **Step 2: Run model tests and verify failure**

Run: `python3 -m unittest tests.test_server_auth.ServerModelConfigTests -v && node --test tests/index_auth_ui.test.js`

Expected: FAIL because the current form controls model configuration.

- [ ] **Step 3: Move all model settings to server configuration**

Set:

```python
DEFAULT_MODEL_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
DEFAULT_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro").strip()
FAST_MODEL = os.environ.get("DEEPSEEK_FAST_MODEL", "deepseek-v4-flash").strip()
```

`handle_generate_report` must not read model-related multipart fields. Remove model parameters from `generate_report_from_upload` and call `call_model(prompt, DEFAULT_MODEL_URL, DEFAULT_API_KEY, DEFAULT_MODEL)`.

- [ ] **Step 4: Remove model controls from the frontend**

Delete the model configuration panel, API-key field, save handler, multipart fields, and legacy load logic. On successful workspace initialization, call `localStorage.removeItem("phei-model-config")` once.

- [ ] **Step 5: Add the non-secret environment template**

Create `.env.example`:

```text
PHEI_HOST=0.0.0.0
PHEI_PORT=4175
PHEI_DB_PATH=data/app.db
APP_CREDENTIAL_KEY=
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_FAST_MODEL=deepseek-v4-flash
BPM_URL=http://bpm.phei.com.cn:8088/portal/r/w
```

- [ ] **Step 6: Run model, UI, and full tests**

Run: `python3 -m unittest tests.test_server_auth -v && npm test`

Expected: client model override tests PASS and all existing tests remain green.

- [ ] **Step 7: Commit centralized DeepSeek configuration**

```bash
git add server.py index.html tests/test_server_auth.py tests/index_auth_ui.test.js .env.example
git commit -m "feat: centralize DeepSeek V4 configuration"
```

---

### Task 9: Security Verification, Documentation, and Browser Validation

**Files:**
- Modify: `README.md`
- Modify: tests only if validation reveals a missing regression case.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: documented startup and backup workflow plus browser-verified authenticated flows.

- [ ] **Step 1: Document secure local setup**

Document these commands without inserting real secrets:

```bash
cp .env.example .env
python3 - <<'PY'
import base64, os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
python3 -m pip install -r requirements.txt
python3 -u server.py
```

Explain that the generated value goes in `APP_CREDENTIAL_KEY`, the DeepSeek key goes in `DEEPSEEK_API_KEY`, and changing the credential key makes saved BPM credentials unreadable. Document daily backup of `data/app.db` while the server is stopped or through SQLite backup tooling.

- [ ] **Step 2: Run the complete automated suite**

Run:

```bash
python3 -m unittest tests.test_app_storage tests.test_server_auth tests.test_digital_contract_intake_form -v
npm test
git diff --check
```

Expected: all Python and Node tests PASS; `git diff --check` produces no output.

- [ ] **Step 3: Start a clean test server**

Use a temporary database and generated key:

```bash
PHEI_DB_PATH=/tmp/phei-auth-test.db \
APP_CREDENTIAL_KEY="$(python3 -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')" \
DEEPSEEK_API_KEY="test-key-not-used" \
PHEI_HOST=127.0.0.1 PHEI_PORT=4176 \
python3 -u server.py
```

Expected: health endpoint returns `{"ok": true, ...}` and the login page loads.

- [ ] **Step 4: Validate desktop and mobile UI with Playwright**

At desktop `1440x900` and mobile `390x844`, verify registration, logout, login, current-user name, BPM save/update/clear state, no model configuration controls, no overlapping text, and usable navigation. Capture screenshots under `output/ui-validation/` and inspect them.

- [ ] **Step 5: Verify secret absence**

Register with distinctive test values, save test BPM credentials, queue no real BPM task, then run:

```bash
rg -a "AUTH_TEST_PASSWORD|BPM_TEST_PASSWORD|DEEPSEEK_TEST_KEY" data output server-runtime.log || true
```

Expected: no matches in SQLite, outputs, or logs. Confirm only the one-way website password hash and encrypted credential ciphertext are present through database queries.

- [ ] **Step 6: Commit documentation and any validation tests**

```bash
git add README.md tests
git commit -m "docs: document authenticated local deployment"
```

- [ ] **Step 7: Review final branch state**

Run: `git status --short --branch && git log --oneline -12`

Expected: only pre-existing unrelated BPM repair changes remain uncommitted, and the new feature is represented by focused commits.
