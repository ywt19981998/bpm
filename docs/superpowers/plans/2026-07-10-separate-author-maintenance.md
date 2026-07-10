# Separate Author Maintenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split BPM author creation and topic declaration into two explicit web actions and two isolated Playwright commands.

**Architecture:** Keep the existing single serial worker queue, but attach a task type to every job and dispatch to either the topic or author runner. The browser sends each button to a separate endpoint, while the Playwright script exposes `submit-topic` and `submit-author`; the legacy `submit` command remains a topic-only alias.

**Tech Stack:** Static HTML/CSS/JavaScript frontend, Python 3 standard-library HTTP server, Node.js, Playwright, Node test runner.

## Global Constraints

- Keep the existing model URL, model name, and API Key behavior unchanged.
- Topic submission must never create or update an author.
- Author submission must never create a topic declaration, score grid, or cost estimate.
- Main-topic author code and author name remain blank for later manual BPM association.
- Author duplicate detection remains a manual user decision.
- Both task types use the existing serial queue and preserve diagnostics under `output/bpm-runs/`.

---

### Task 1: Split the Playwright commands

**Files:**
- Modify: `skills/phei-bpm-topic-declaration/scripts/fill_topic.js`
- Modify: `tests/fill_topic_interactions.test.js`

**Interfaces:**
- Consumes: normalized topic JSON from `server.py`, `BPM_USER`, `BPM_PASSWORD`, and `BPM_URL`.
- Produces: `submitTopic(jsonPath): Promise<void>`, `submitAuthor(jsonPath): Promise<void>`, CLI modes `submit-topic`, `submit-author`, and topic-only alias `submit`.

- [ ] **Step 1: Write failing command-isolation tests**

Add source-contract tests that extract each function body and assert its call graph:

```javascript
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
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `node --test tests/fill_topic_interactions.test.js`

Expected: FAIL because `submitTopic` and `submitAuthor` do not exist.

- [ ] **Step 3: Rename the existing topic flow and remove its author call**

Change the current `submit(jsonPath)` declaration to `submitTopic(jsonPath)` and remove this line:

```javascript
const authorResult = await saveAuthorMaintenance(page, topic, outputDir);
```

Remove `authorResult` from the topic result object. Keep login, topic form, temporary save, score, cost estimate, and worklist verification unchanged.

- [ ] **Step 4: Add the author-only command**

Add an isolated function before `main()`:

```javascript
async function submitAuthor(jsonPath) {
  const { absPath, data } = loadInput(jsonPath);
  const topic = withDefaults(data);
  const authorName = topic.authorMaintenance?.name || topic.authorName;
  const authorBio = String(topic.authorMaintenance?.bio || '').trim();
  if (!isValidPersonName(authorName)) {
    throw new Error(`Invalid authorName: "${String(authorName || '').slice(0, 80)}".`);
  }
  if (!authorBio) throw new Error('Author bio is required');

  const outputDir = path.dirname(absPath);
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1400 } });
  try {
    await login(page);
    const authorResult = await saveAuthorMaintenance(page, topic, outputDir);
    if (authorResult.skipped) throw new Error(authorResult.reason || 'Author maintenance was skipped');
    console.log(JSON.stringify({
      ok: true,
      mode: 'submit-author',
      authorName,
      authorResult,
      inputPath: absPath,
    }, null, 2));
  } finally {
    await browser.close();
  }
}
```

- [ ] **Step 5: Dispatch the new CLI modes**

Add these branches to `main()` before usage validation:

```javascript
if (mode === 'submit-author' && jsonPath) {
  await submitAuthor(jsonPath);
  return;
}
if ((mode === 'submit-topic' || mode === 'submit') && jsonPath) {
  await submitTopic(jsonPath);
  return;
}
```

Update the usage error to list both commands and remove the old final `submit(jsonPath)` call.

- [ ] **Step 6: Run the script tests**

Run: `node --check skills/phei-bpm-topic-declaration/scripts/fill_topic.js && node --test tests/fill_topic_interactions.test.js`

Expected: all tests PASS.

- [ ] **Step 7: Commit the script split**

```bash
git add skills/phei-bpm-topic-declaration/scripts/fill_topic.js tests/fill_topic_interactions.test.js
git commit -m "feat: split BPM author and topic commands"
```

### Task 2: Add typed backend jobs and isolated endpoints

**Files:**
- Modify: `server.py`
- Create: `tests/server_bpm_jobs.test.js`

**Interfaces:**
- Consumes: topic payloads from `/api/bpm-topic-jobs` and author payloads from `/api/bpm-author-jobs`.
- Produces: `run_bpm_topic_submit(payload)`, `run_bpm_author_submit(payload)`, typed jobs with `type: "topic" | "author"`, and a shared `GET /api/bpm-jobs` list.

- [ ] **Step 1: Write failing backend source-contract tests**

Create `tests/server_bpm_jobs.test.js`:

```javascript
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'server.py'), 'utf8');

test('backend exposes separate author and topic job endpoints', () => {
  assert.match(source, /\/api\/bpm-topic-jobs/);
  assert.match(source, /\/api\/bpm-author-jobs/);
});

test('backend invokes isolated Playwright modes', () => {
  assert.match(source, /"submit-topic"/);
  assert.match(source, /"submit-author"/);
});

test('worker dispatches jobs by explicit type', () => {
  assert.match(source, /job_type\s*==\s*"author"/);
  assert.match(source, /"type":\s*job_type/);
});
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run: `node --test tests/server_bpm_jobs.test.js`

Expected: FAIL because the two endpoints and modes are absent.

- [ ] **Step 3: Extract a shared BPM script runner**

Replace the monolithic runner with:

```python
def run_bpm_script(payload: dict, mode: str, required_result: str) -> dict:
    credentials = payload.get("bpm") or {}
    bpm_user = (credentials.get("user") or os.environ.get("BPM_USER") or "").strip()
    bpm_password = (credentials.get("password") or os.environ.get("BPM_PASSWORD") or "").strip()
    bpm_url = (credentials.get("url") or os.environ.get("BPM_URL") or "http://bpm.phei.com.cn:8088/portal/r/w").strip()
    if not bpm_user or not bpm_password:
        raise ValueError("请填写 BPM 账号和密码。")

    topic = merge_bpm_topic(payload)
    run_root = ROOT / "output" / "bpm-runs"
    run_root.mkdir(parents=True, exist_ok=True)
    run_dir = run_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    topic_path = run_dir / "topic.json"
    topic_path.write_text(json.dumps(topic, ensure_ascii=False, indent=2), encoding="utf-8")
    env = {**os.environ, "BPM_USER": bpm_user, "BPM_PASSWORD": bpm_password, "BPM_URL": bpm_url, "NODE_PATH": str(NODE_MODULES)}
    completed = subprocess.run(
        ["node", str(BPM_SCRIPT), mode, str(topic_path)],
        cwd=str(ROOT), env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=180, check=False,
    )
    (run_dir / "stdout.txt").write_text(completed.stdout or "", encoding="utf-8")
    (run_dir / "stderr.txt").write_text(completed.stderr or "", encoding="utf-8")
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"{required_result}失败"
        raise RuntimeError(f"{detail}\n运行记录已保存：{run_dir}")
    result = json.loads(completed.stdout)
    result["runDir"] = str(run_dir)
    if not result.get("ok"):
        raise RuntimeError(f"{required_result}未验证成功。运行记录已保存：{run_dir}")
    return result
```

Define `run_bpm_topic_submit()` with author-name-independent topic validation and `mode="submit-topic"`. Define `run_bpm_author_submit()` to require `authorMaintenance.name` and `authorMaintenance.bio`, then call `mode="submit-author"`.

- [ ] **Step 4: Make jobs explicitly typed**

Change job creation to `create_bpm_job(payload: dict, job_type: str)`. For `topic`, retain the six-section confirmation checks. For `author`, skip section checks and validate only author name and bio. Store:

```python
"type": job_type,
"title": topic.get("bookName") if job_type == "topic" else topic["authorMaintenance"]["name"],
"logs": [f"{created} 已加入{'选题填报' if job_type == 'topic' else '作译者维护'}队列"],
```

Queue `(job_id, job_type, payload)`. In the worker, dispatch `run_bpm_author_submit(payload)` when `job_type == "author"`; otherwise dispatch `run_bpm_topic_submit(payload)`.

- [ ] **Step 5: Route the two POST endpoints**

Add:

```python
if path == "/api/bpm-topic-jobs":
    self.handle_bpm_job("topic")
    return
if path == "/api/bpm-author-jobs":
    self.handle_bpm_job("author")
    return
```

Change `handle_bpm_job(self, job_type: str)` to pass the type to `create_bpm_job`. Keep `POST /api/bpm-jobs` as a topic-only compatibility alias.

- [ ] **Step 6: Run backend and full tests**

Run: `python3 -m py_compile server.py && node --test tests/*.test.js`

Expected: all tests PASS.

- [ ] **Step 7: Commit typed backend jobs**

```bash
git add server.py tests/server_bpm_jobs.test.js
git commit -m "feat: add separate BPM author job endpoint"
```

### Task 3: Add the independent author button and task labels

**Files:**
- Modify: `index.html`
- Create: `tests/index_bpm_actions.test.js`

**Interfaces:**
- Consumes: current `bpmTopic.authorMaintenance`, shared BPM credential fields, `/api/bpm-topic-jobs`, and `/api/bpm-author-jobs`.
- Produces: `queueBpm` topic action, `queueAuthor` author action, and typed job cards.

- [ ] **Step 1: Write failing frontend source-contract tests**

Create `tests/index_bpm_actions.test.js`:

```javascript
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

test('BPM view has separate topic and author buttons', () => {
  assert.match(source, /id="queueAuthor"/);
  assert.match(source, /id="queueBpm"[^>]*>.*填报选题/s);
});

test('buttons use separate backend endpoints', () => {
  assert.match(source, /fetch\("\/api\/bpm-author-jobs"/);
  assert.match(source, /fetch\("\/api\/bpm-topic-jobs"/);
});

test('author copy no longer promises automatic creation', () => {
  assert.doesNotMatch(source, /BPM 填报时会先新增作译者/);
  assert.match(source, /可单独新增至 BPM 作译者库/);
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `node --test tests/index_bpm_actions.test.js`

Expected: FAIL because `queueAuthor` and the two explicit endpoints are absent.

- [ ] **Step 3: Add the second top-bar button**

Replace the existing action area with:

```html
<div class="top-actions">
  <button id="refreshBpmJobs"><i data-lucide="refresh-cw" size="16"></i>刷新任务</button>
  <button id="queueAuthor"><i data-lucide="user-round-plus" size="16"></i>新增作译者</button>
  <button class="primary" id="queueBpm"><i data-lucide="send" size="16"></i>填报选题</button>
</div>
```

- [ ] **Step 4: Share credential and payload construction**

Add `currentBpmCredentials()` returning `url`, `user`, `name`, and `password`. Add `currentBpmPayload()` returning title, editor name, sections, scores, total, current topic, and credentials. Both handlers call these functions so credentials and editor identity remain consistent.

- [ ] **Step 5: Make topic submission call only the topic endpoint**

Keep the six-section confirmation and confirmation dialog. Change the request URL to `/api/bpm-topic-jobs`, update progress text to “正在加入选题填报队列...”, and use the success message “选题填报已加入队列”.

- [ ] **Step 6: Add the author-only handler**

Add a click handler that validates credentials, author name, and author bio, confirms the author name, and posts the shared payload to `/api/bpm-author-jobs`. It must not check report-section confirmation state. On success, clear the password, refresh jobs, and display “作译者维护已加入队列”.

- [ ] **Step 7: Render task types and update author copy**

Show `job.type === "author" ? "作译者维护" : "选题填报"` in each job card. Change author status text to `工作单位：${unit}；可单独新增至 BPM 作译者库。` and update the empty-state wording accordingly.

- [ ] **Step 8: Run frontend and full tests**

Run: `npm test`

Expected: all tests PASS.

- [ ] **Step 9: Commit the web controls**

```bash
git add index.html tests/index_bpm_actions.test.js
git commit -m "feat: add independent BPM author action"
```

### Task 4: Update workflow instructions and verify the complete feature

**Files:**
- Modify: `skills/phei-bpm-topic-declaration/SKILL.md`
- Modify: `/Users/xiewentao/.codex/skills/phei-bpm-topic-declaration/SKILL.md`

**Interfaces:**
- Consumes: the two implemented CLI modes and web actions.
- Produces: matching project and installed-skill instructions for future maintenance.

- [ ] **Step 1: Update both skill copies**

Document these exact commands:

```bash
NODE_PATH=/abs/project/node_modules node scripts/fill_topic.js submit-topic /abs/path/topic.json
NODE_PATH=/abs/project/node_modules node scripts/fill_topic.js submit-author /abs/path/topic.json
```

State that web users choose whether to add an author; topic filling never calls author maintenance. Preserve all current field defaults and credential rules.

- [ ] **Step 2: Run placeholder and consistency scans**

Run:

```bash
rg -n "submit-author|submit-topic|填报选题|新增作译者" index.html server.py skills/phei-bpm-topic-declaration tests
rg -n "T[B]D|T[O]DO|implement[[:space:]]+later" docs/superpowers/plans/2026-07-10-separate-author-maintenance.md skills/phei-bpm-topic-declaration/SKILL.md
```

Expected: both workflows appear in code and instructions; the placeholder scan returns no matches.

- [ ] **Step 3: Run the complete automated verification**

Run: `npm test && git diff --check`

Expected: Python compile, JavaScript syntax check, and all Node tests PASS; diff check is silent.

- [ ] **Step 4: Start the local service and verify health**

Run: `npm start`

In another terminal run: `curl -fsS http://127.0.0.1:4174/api/health`

Expected: JSON containing `"ok": true`.

- [ ] **Step 5: Browser smoke test**

Open `http://127.0.0.1:4174/index.html`, switch to BPM, and verify both buttons are visible, task type labels render, and each button performs its own validation without invoking the other action.

- [ ] **Step 6: Commit instructions and push the completed feature**

```bash
git add skills/phei-bpm-topic-declaration/SKILL.md
git commit -m "docs: document isolated BPM workflows"
git push origin main
```
