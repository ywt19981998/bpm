# Project Center and BPM Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent per-user topic projects that retain source files and report state, provide a compact project center, and gate project-linked BPM jobs through a field preflight with verified stage outcomes.

**Architecture:** Extend `AppStore` with project, revision, file-metadata, and project-linked job storage. Put DOCX validation and atomic disk writes in a focused `ProjectFileStore`, and put status/preflight derivation in `project_domain.py` so HTTP routing and browser code do not duplicate business rules. Preserve the existing report generation, DOCX export, and Playwright worker, while making project-aware calls load trusted state from the authenticated user's project.

**Tech Stack:** Python 3.12+, SQLite, `http.server`, `python-docx`, vanilla HTML/CSS/JavaScript, Node test runner, Python `unittest`, Playwright.

## Global Constraints

- Existing authenticated report generation, DOCX export, author maintenance, and topic declaration behavior must remain available.
- Every project and project file is private to its owner; cross-user reads and writes return 404.
- Uploaded files are limited to valid `.docx` ZIP packages of at most 20 MB.
- Disk paths use generated IDs and database-relative paths, never client filenames.
- Project updates use an integer `version`; stale writes return HTTP 409 and never silently overwrite newer state.
- Browser drafts are removed only after their project migration succeeds.
- A topic BPM job may report `succeeded` only after the saved draft is found in the refreshed BPM worklist.
- Project archiving is reversible storage state; this release exposes no permanent delete action.
- Credentials, API keys, cookies, and other secrets must remain absent from project JSON, job data, logs, and API responses.
- Keep the existing single-page visual language and use a compact operational table rather than decorative project cards.

---

## File Structure

- Modify `app_storage.py`: schema migrations and owner-scoped project, revision, file metadata, and linked-job methods.
- Create `project_files.py`: DOCX validation, atomic storage, safe download resolution, and project-directory management.
- Create `project_domain.py`: canonical project state, summary/status derivation, and BPM preflight rows.
- Modify `server.py`: project APIs, project-aware generation/import/export, trusted project-linked BPM jobs, and file downloads.
- Modify `index.html`: project-center navigation, table, project context, autosave, draft migration, and BPM preflight UI.
- Modify `skills/phei-bpm-topic-declaration/scripts/fill_topic.js`: emit explicit verified milestones without changing field selectors.
- Modify `README.md`: project storage, backup, migration, and recovery instructions.
- Modify existing storage, auth, BPM, and frontend tests; create focused project/file/domain/API tests.

---

### Task 1: Persistent Project Storage

**Files:**
- Modify: `app_storage.py`
- Modify: `tests/test_app_storage.py`

**Interfaces:**
- Produces: `create_project(user_id: int, title: str, state: dict | None = None) -> dict`.
- Produces: `get_project(user_id: int, project_id: str) -> dict | None`.
- Produces: `list_projects(user_id: int, *, include_archived: bool = False, query: str = "", status: str = "") -> list[dict]`.
- Produces: `update_project(user_id: int, project_id: str, expected_version: int, patch: dict, *, revision_reason: str | None = None) -> dict | None`.
- Produces: `archive_project(user_id: int, project_id: str, expected_version: int) -> dict | None`.
- Produces: `add_project_file(...) -> dict`, `list_project_files(...) -> list[dict]`, and `get_project_file(...) -> dict | None`.
- Produces: `ProjectVersionConflict`, raised only when the project exists for the owner but `expected_version` is stale.

- [ ] **Step 1: Write failing project CRUD and isolation tests**

Add `AppStoreProjectTests` with real temporary SQLite storage:

```python
def test_project_round_trip_is_versioned_and_owner_scoped(self):
    project = self.store.create_project(
        self.user_id,
        "测试选题",
        {"sections": [{"key": "content", "text": "草稿", "confirmed": False}]},
    )
    self.assertEqual(project["version"], 1)
    self.assertIsNone(self.store.get_project(self.other_user_id, project["id"]))
    updated = self.store.update_project(
        self.user_id,
        project["id"],
        1,
        {"title": "修订选题", "report_status": "draft"},
    )
    self.assertEqual(updated["version"], 2)
    with self.assertRaises(ProjectVersionConflict):
        self.store.update_project(self.user_id, project["id"], 1, {"title": "旧值"})
```

Also test list ordering, keyword/status filtering, archive exclusion, revision creation only when `revision_reason` is supplied, and cross-user update returning `None` rather than revealing existence.

- [ ] **Step 2: Run the tests and verify RED**

Run: `python3 -m unittest tests.test_app_storage.AppStoreProjectTests -v`

Expected: FAIL because project tables, methods, and `ProjectVersionConflict` do not exist.

- [ ] **Step 3: Add migration version 4**

Create `projects`, `project_files`, and `project_revisions`, then add nullable `jobs.project_id` only when `PRAGMA table_info(jobs)` shows that it is absent. Add indexes for `(user_id, archived_at, updated_at DESC)`, project file lookup, revision lookup, and jobs by project.

Project rows store compact UTF-8 JSON and millisecond timestamps. Validate all status values in Python before SQL writes. Use one transaction for project update plus optional revision snapshot.

- [ ] **Step 4: Implement owner-scoped project methods**

Normalize outward records to camelCase-compatible dictionaries:

```python
{
    "id": row["id"],
    "title": row["title"],
    "authorName": row["author_name"],
    "editorName": row["editor_name"],
    "reportStatus": row["report_status"],
    "authorStatus": row["author_status"],
    "bpmStatus": row["bpm_status"],
    "state": json.loads(row["state_json"]),
    "version": row["version"],
    "createdAt": cls._format_job_timestamp(row["created_at"]),
    "updatedAt": cls._format_job_timestamp(row["updated_at"]),
    "archivedAt": cls._format_job_timestamp(row["archived_at"]),
}
```

`update_project` accepts only the explicit keys `title`, `author_name`, `editor_name`, `report_status`, `author_status`, `bpm_status`, and `state`; it cannot update ownership or IDs.

- [ ] **Step 5: Extend jobs with optional project ownership**

Change `create_job(..., project_id: str | None = None)` to verify that a non-null project belongs to the same user, persist it, and return `projectId`. Keep existing callers valid by defaulting to `None`.

- [ ] **Step 6: Run storage tests and commit**

Run: `python3 -m unittest tests.test_app_storage -v`

Expected: all existing auth/credential/job tests and new project tests PASS.

Commit:

```bash
git add app_storage.py tests/test_app_storage.py
git commit -m "feat: add persistent topic projects"
```

---

### Task 2: Safe DOCX Project File Storage

**Files:**
- Create: `project_files.py`
- Create: `tests/test_project_files.py`

**Interfaces:**
- Produces: `ProjectFileStore(root: Path, max_bytes: int = 20 * 1024 * 1024)`.
- Produces: `save_docx(user_id: int, project_id: str, file_id: str, content: bytes) -> StoredProjectFile`.
- Produces: `resolve(relative_path: str) -> Path` with root containment enforcement.
- Produces: `remove(relative_path: str) -> None` for rollback of uncommitted files.
- Produces: `InvalidProjectFile(message: str)`.

- [ ] **Step 1: Write failing file validation tests**

Use `python-docx` to create a real in-memory DOCX and assert:

```python
stored = self.files.save_docx(7, "project-id", "file-id", valid_docx_bytes())
self.assertEqual(stored.relative_path, "7/project-id/file-id.docx")
self.assertTrue(self.files.resolve(stored.relative_path).is_file())
self.assertEqual(stored.sha256, hashlib.sha256(valid_docx_bytes()).hexdigest())
```

Also reject random bytes named as DOCX, ZIPs without `[Content_Types].xml` and `word/document.xml`, payloads over `max_bytes`, unsafe IDs containing separators, and resolution attempts such as `../app.db`.

- [ ] **Step 2: Run the file tests and verify RED**

Run: `python3 -m unittest tests.test_project_files -v`

Expected: FAIL because `project_files` does not exist.

- [ ] **Step 3: Implement validation and atomic writes**

Inspect ZIP members with `zipfile.ZipFile(io.BytesIO(content))`. Write to a temporary file in the final project directory, `flush()` and `os.fsync()`, then `os.replace()` to the generated final path. Return a frozen dataclass containing `relative_path`, `sha256`, and `size_bytes`.

- [ ] **Step 4: Run tests and commit**

Run: `python3 -m unittest tests.test_project_files -v`

Expected: all file tests PASS.

Commit:

```bash
git add project_files.py tests/test_project_files.py
git commit -m "feat: store validated project documents"
```

---

### Task 3: Canonical Project State and BPM Preflight

**Files:**
- Create: `project_domain.py`
- Create: `tests/test_project_domain.py`
- Read: `skills/phei-bpm-topic-declaration/references/input-schema.md`

**Interfaces:**
- Produces: `normalize_project_state(value: dict | None) -> dict`.
- Produces: `summarize_project_state(state: dict, editor_name: str) -> dict`.
- Produces: `build_bpm_preflight(state: dict, *, bpm_configured: bool) -> dict`.
- Produces: `project_state_from_report(result: dict, *, source_kind: str) -> dict`.

- [ ] **Step 1: Write failing canonical-state tests**

Assert that malformed arrays/objects are replaced with safe empty values, six known section keys are retained in canonical order, client `editorName` is replaced by the authenticated editor, and unknown nested BPM fields are preserved without preserving credential-like keys.

- [ ] **Step 2: Write failing preflight tests**

Test a ready project and a blocking project:

```python
result = build_bpm_preflight(ready_state(), bpm_configured=True)
self.assertTrue(result["ready"])
self.assertEqual(result["blockingCount"], 0)
self.assertEqual({row["source"] for row in result["rows"]}, {
    "application", "report", "fixed", "model", "user", "bpm_profile"
})
```

Blocking checks are limited to facts the current workflow truly requires: project title, six confirmed report sections, valid score total, authenticated editor name, and saved BPM credentials. Optional BPM fields remain visible as `optional_missing` and do not disable queueing.

- [ ] **Step 3: Run domain tests and verify RED**

Run: `python3 -m unittest tests.test_project_domain -v`

Expected: FAIL because the module does not exist.

- [ ] **Step 4: Implement canonical state and source metadata**

Use one state shape:

```python
{
    "sections": [],
    "scoreItems": [],
    "bpmTopic": {},
    "authorMaintenance": {},
    "fieldSources": {},
    "sourceFiles": {},
    "docxExported": False,
}
```

Preflight rows use `{key, label, value, source, status, required}`. Escape nothing in Python; the browser must render values with `textContent`.

- [ ] **Step 5: Run tests and commit**

Run: `python3 -m unittest tests.test_project_domain -v`

Expected: all domain tests PASS.

Commit:

```bash
git add project_domain.py tests/test_project_domain.py
git commit -m "feat: derive project and BPM readiness"
```

---

### Task 4: Authenticated Project HTTP APIs

**Files:**
- Modify: `server.py`
- Create: `tests/test_server_projects.py`

**Interfaces:**
- Consumes: `AppStore` project methods, `ProjectFileStore`, and `project_domain` helpers.
- Produces: project CRUD, import, preflight, file upload, and authenticated download routes from the design spec.

- [ ] **Step 1: Add a real HTTP project test harness**

Start an ephemeral `ThreadingHTTPServer` with temporary `APP_STORE` and `PROJECT_FILE_STORE`, register two users, and add request helpers for JSON and multipart payloads.

- [ ] **Step 2: Write failing CRUD, isolation, and conflict tests**

Cover:

```python
status, _, body = self.request("POST", "/api/projects", {"title": "数据库原理"}, self.cookie)
self.assertEqual(status, 201)
project = json.loads(body)["project"]

status, _, _ = self.request(
    "PUT", f"/api/projects/{project['id']}",
    {"version": project["version"], "state": ready_state()}, self.cookie
)
self.assertEqual(status, 200)
```

Assert unauthenticated 401, cross-user 404, stale version 409, archive exclusion, search, and malformed project ID 404.

- [ ] **Step 3: Run API tests and verify RED**

Run: `python3 -m unittest tests.test_server_projects.ServerProjectApiTests -v`

Expected: FAIL with 404 because project routes do not exist.

- [ ] **Step 4: Add route parsing and JSON handlers**

Use `urllib.parse.urlsplit` and a strict UUID path matcher. Route project requests before the generic static-file branch. Return a common shape:

```json
{"project": {}, "files": [], "preflight": {}}
```

Map `ProjectVersionConflict` to `409 PROJECT_VERSION_CONFLICT`, invalid content to 400, and missing/foreign projects to 404.

- [ ] **Step 5: Add failing upload/download tests**

Upload a real DOCX as `kind=application`, verify metadata and bytes on authenticated download, verify cross-user 404, and assert rejected payloads leave neither a database row nor an orphan file.

- [ ] **Step 6: Implement atomic upload plus metadata transaction boundary**

Call `ProjectFileStore.save_docx`, then `AppStore.add_project_file`. If metadata persistence fails, call `remove`. Resolve downloads only after `get_project_file(user_id, project_id, file_id)` succeeds.

- [ ] **Step 7: Add preflight endpoint tests and implementation**

`GET /api/projects/<id>/preflight` loads the project, checks `APP_STORE.has_integration_credentials(user_id, "phei_bpm")`, and returns `build_bpm_preflight(...)` without decrypting or returning credentials.

- [ ] **Step 8: Run API and full Python tests, then commit**

Run: `python3 -m unittest tests.test_server_projects -v`

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -q`

Expected: all tests PASS.

Commit:

```bash
git add server.py tests/test_server_projects.py
git commit -m "feat: expose authenticated project APIs"
```

---

### Task 5: Bind Report Generation, Import, Export, and Jobs to Projects

**Files:**
- Modify: `server.py`
- Modify: `app_storage.py`
- Modify: `tests/test_server_projects.py`
- Modify: `tests/test_server_auth.py`
- Modify: `tests/server_bpm_jobs.test.js`

**Interfaces:**
- Existing `/api/generate-report`, `/api/import-bpm-sources`, and `/api/export-docx` accept optional trusted `projectId` integration.
- Existing `/api/bpm-author-jobs` and `/api/bpm-topic-jobs` require `projectId` for new browser calls and persist it on the job.
- Produces: `load_project_job_payload(user: dict, project_id: str, job_type: str) -> dict`.

- [ ] **Step 1: Write failing report integration tests**

Patch the current extractor/model and assert that generation with a valid `projectId` saves canonical report state, sets `reportStatus=draft`, retains the application file metadata, and returns the updated project. Assert export marks `docxExported`, writes an `exported_report` file, and still streams DOCX bytes.

- [ ] **Step 2: Write failing quick-import tests**

Post two valid DOCX files to `/api/projects/import`; patch existing parsing helpers and assert one project is created with both file kinds, all six sections confirmed, and `bpmStatus=ready` when preflight has no blockers.

- [ ] **Step 3: Run focused tests and verify RED**

Run: `python3 -m unittest tests.test_server_projects.ProjectBusinessFlowTests -v`

Expected: FAIL because business endpoints do not persist projects.

- [ ] **Step 4: Implement project-aware report operations**

Keep old request forms working for compatibility, but when `projectId` is present:

1. Verify owner before expensive parsing/model calls.
2. Load and update canonical state through `project_domain`.
3. Use the authenticated user's display name for editor fields.
4. Persist the project before sending success.
5. Return both existing generated fields and `project` so current frontend rendering can migrate incrementally.

- [ ] **Step 5: Write failing trusted BPM job tests**

Assert that a forged client `bpmTopic`, title, editor, author, or `userId` is ignored when `projectId` is supplied. Assert that a missing/foreign/not-ready project cannot enqueue and that the stored job includes `projectId` but no secrets.

- [ ] **Step 6: Implement project-linked job creation and status propagation**

Build worker input from persisted project state plus server-side user/BPM credentials. On queue/running/succeeded/failed transitions, update only the matching project status field with optimistic retries against the latest project version; job history remains authoritative if status propagation loses a race.

- [ ] **Step 7: Run integrations and commit**

Run: `python3 -m unittest tests.test_server_projects tests.test_server_auth -v`

Run: `node --test tests/server_bpm_jobs.test.js`

Expected: all focused tests PASS.

Commit:

```bash
git add app_storage.py server.py tests/test_server_projects.py tests/test_server_auth.py tests/server_bpm_jobs.test.js
git commit -m "feat: bind publishing workflows to projects"
```

---

### Task 6: Compact Project Center UI

**Files:**
- Modify: `index.html`
- Create: `tests/index_project_center.test.js`
- Modify: `package.json` only if the existing wildcard does not include the test automatically.

**Interfaces:**
- Produces browser state: `projects`, `currentProject`, `currentProjectVersion`, and `projectSaveState`.
- Produces functions: `loadProjects()`, `renderProjectTable()`, `openProject(projectId)`, `createProjectFromApplication(file)`, and `archiveCurrentProject()`.

- [ ] **Step 1: Write failing source-contract tests**

Assert that authenticated navigation has a `menuProjects` entry, `projectCenterView` is the default view, the table uses real column headers, there is no sample medical project, and project API calls use `apiFetch` with no client user ID.

- [ ] **Step 2: Run UI tests and verify RED**

Run: `node --test tests/index_project_center.test.js`

Expected: FAIL because the project-center elements and functions do not exist.

- [ ] **Step 3: Add the project-center layout**

Add a full-width operational table with search, status filter, archived toggle, loading/empty/error states, and icon actions. Reuse the current spacing, borders, blue accent, and Lucide icons. Stable row height and responsive horizontal scrolling must prevent text overlap.

- [ ] **Step 4: Add safe project rendering and navigation**

Build every user value with `textContent` and DOM methods. The “new topic” flow creates a server project before navigating to report generation. Opening a row hydrates report/BPM state and stores only the current project ID as a convenience pointer.

- [ ] **Step 5: Run UI and full JavaScript tests, then commit**

Run: `node --test tests/index_project_center.test.js`

Run: `npm test`

Expected: all tests PASS.

Commit:

```bash
git add index.html tests/index_project_center.test.js package.json
git commit -m "feat: add topic project center"
```

---

### Task 7: Project Autosave, Draft Migration, and BPM Preflight UI

**Files:**
- Modify: `index.html`
- Modify: `tests/index_project_center.test.js`
- Modify: `tests/index_bpm_actions.test.js`

**Interfaces:**
- Produces: `serializeWorkspaceState()`, `saveCurrentProject({checkpointReason})`, `scheduleProjectAutosave()`, `migrateLegacyDraft()`, `loadProjectPreflight()`, and `renderProjectPreflight()`.

- [ ] **Step 1: Write failing autosave and conflict tests**

Assert input/confirmation/scoring mutations schedule a server `PUT`, payload includes the last project `version`, success updates it, and HTTP 409 sets a visible unsaved conflict state rather than retrying over newer data.

- [ ] **Step 2: Write failing migration tests**

Assert legacy draft data is offered once, removed only after `POST /api/projects` succeeds, and retained after request failure or stale authenticated-session invalidation.

- [ ] **Step 3: Write failing BPM preflight UI tests**

Assert the BPM page fetches `/api/projects/<id>/preflight`, renders field/source/status columns with DOM text, disables topic queueing when `ready=false`, and keeps author maintenance as a separate explicit button.

- [ ] **Step 4: Run tests and verify RED**

Run: `node --test tests/index_project_center.test.js tests/index_bpm_actions.test.js`

Expected: FAIL on missing autosave, migration, and preflight behavior.

- [ ] **Step 5: Implement debounced project persistence**

Use a 700 ms trailing debounce. Capture the authenticated session generation and project ID before each request; discard late responses after logout or project switch. Maintain visible states `正在保存`, `已保存`, `未保存`, and `版本冲突`.

- [ ] **Step 6: Implement safe one-time draft migration**

Prompt only when the legacy draft contains non-empty report sections and no migration marker exists. Create a project with `sourceFiles.application.missing=true`; set the marker to the returned project ID only after success.

- [ ] **Step 7: Implement preflight rendering and queue gating**

Display a compact table above task logs. Queue calls send only `{projectId}`. Missing BPM credentials opens personal settings; other blockers link back to report editing. Optional missing fields remain visible but non-blocking.

- [ ] **Step 8: Run frontend tests and commit**

Run: `npm test`

Expected: all JavaScript tests PASS.

Commit:

```bash
git add index.html tests/index_project_center.test.js tests/index_bpm_actions.test.js
git commit -m "feat: persist project workspace and preflight"
```

---

### Task 8: Verified BPM Milestones

**Files:**
- Modify: `skills/phei-bpm-topic-declaration/scripts/fill_topic.js`
- Modify: `tests/fill_topic_interactions.test.js`
- Modify: `server.py`
- Modify: `tests/server_bpm_jobs.test.js`

**Interfaces:**
- Produces result property `milestones: string[]` from the Playwright script.
- Preserves existing CLI modes `submit-topic` and `submit-author`.

- [ ] **Step 1: Write failing milestone tests**

Assert `submitTopic` records `login_verified`, `topic_form_opened`, `topic_draft_saved`, `cost_estimate_saved`, and finally `worklist_verified`; assert success serialization requires the final milestone. Assert failures retain completed milestones.

- [ ] **Step 2: Run BPM interaction tests and verify RED**

Run: `node --test tests/fill_topic_interactions.test.js tests/server_bpm_jobs.test.js`

Expected: FAIL because explicit milestone output does not exist.

- [ ] **Step 3: Add a milestone recorder around existing verified actions**

Do not change selectors or replace current worklist discovery. Append a milestone only after the existing check for that stage succeeds. Include the accumulated list in both success results and structured failure output consumed by `server.py`.

- [ ] **Step 4: Persist milestones and derive project status**

Store milestones inside sanitized `result_json`. `process_bpm_job` may mark the project BPM status `succeeded` only when the worker result contains `worklist_verified`; otherwise it marks `failed` with the last completed milestone.

- [ ] **Step 5: Run BPM and full tests, then commit**

Run: `node --test tests/fill_topic_interactions.test.js tests/server_bpm_jobs.test.js`

Run: `npm test`

Expected: all tests PASS.

Commit:

```bash
git add skills/phei-bpm-topic-declaration/scripts/fill_topic.js tests/fill_topic_interactions.test.js server.py tests/server_bpm_jobs.test.js
git commit -m "feat: verify project BPM milestones"
```

---

### Task 9: Documentation, Full Regression, and Visual Verification

**Files:**
- Modify: `README.md`
- Modify: `.gitignore` only if project runtime directories are not already covered.

**Interfaces:**
- Documents backup and restore requirements for project metadata and files.

- [ ] **Step 1: Update operator documentation**

Document that `data/app.db` and `data/projects/` form one backup unit, explain browser-draft migration, project statuses, archive behavior, and how to diagnose the final completed BPM milestone.

- [ ] **Step 2: Run all automated verification**

Run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -q
npm test
git diff --check
```

Expected: all Python and JavaScript tests PASS and no whitespace errors are reported.

- [ ] **Step 3: Start the service on an unused local port**

Run: `PHEI_HOST=127.0.0.1 PHEI_PORT=4176 python3 -u server.py`

Verify: `curl -fsS http://127.0.0.1:4176/api/health` returns `{"ok": true, ...}`.

- [ ] **Step 4: Perform browser workflow and visual checks**

At desktop `1440x1000` and mobile `390x844`, verify login, empty project center, project creation, report reopening, autosave status, BPM preflight, table scrolling, and no overlap. Confirm project/API requests have no console errors and nonblank content is visible.

- [ ] **Step 5: Commit documentation and final adjustments**

```bash
git add README.md .gitignore index.html tests
git commit -m "docs: document persistent project workflow"
```

- [ ] **Step 6: Tag the completed upgrade after final review**

Create a descriptive tag only after the branch is clean and all verification passes:

```bash
git tag -a project-center-v1-20260811 -m "Project center and BPM preflight v1"
```
