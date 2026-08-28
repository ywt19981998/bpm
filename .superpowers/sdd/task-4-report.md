# Task 4 Report: Persistent BPM Settings and Trusted Identity Injection

## Status

Completed and committed.

## Commit

`5adc6b5 feat: use encrypted per-user BPM settings`

## Files committed

- `server.py`
- `skills/phei-bpm-topic-declaration/scripts/fill_topic.js`
- `tests/test_server_auth.py`
- `tests/server_bpm_jobs.test.js`
- `tests/fill_topic_interactions.test.js`

## Red evidence

Initial credential and injection tests failed as expected:

```bash
/Users/xiewentao/.cache/phei-task2-venv/bin/python3 -m unittest tests.test_server_auth.ServerCredentialHttpTests -v
node --test tests/server_bpm_jobs.test.js
node --test tests/fill_topic_interactions.test.js
```

- Credential API tests failed because `PUT` and `DELETE` returned `501`; authenticated save/update requests could not succeed.
- The server-source test failed because `create_bpm_job` did not call `get_integration_credentials(user["id"], "phei_bpm")` and still read `payload.get("bpm")`.
- The interaction test failed because `ensureEditorIdentity` did not exist.

A second editor-picker regression was added after self-review:

```bash
node --test tests/fill_topic_interactions.test.js
```

- 14 passed, 1 failed because `selectBpmPerson` returned early when the visible name matched, even if BPM's hidden editor number was missing.

## Green verification

```bash
/Users/xiewentao/.cache/phei-task2-venv/bin/python3 -m unittest tests.test_app_storage tests.test_server_auth -v
node --test tests/fill_topic_interactions.test.js
npm test
```

- Python storage/auth/credential suite: 20 passed.
- Focused Playwright interaction suite: 15 passed, 0 failed.
- Full npm suite: 26 passed, 0 failed.
- `git diff --check` and `git diff --cached --check`: passed.

## Self-review

- `GET`, `PUT`, and `DELETE /api/integrations/phei-bpm` all require a valid session and scope reads/writes/deletes to the authenticated user ID.
- Credential responses expose only `configured` and `accountMasked`; tests verify submitted passwords never appear in response bodies.
- `create_bpm_job` ignores client BPM credentials, loads the authenticated user's encrypted credentials, and adds the current display name to a deep-copied worker payload.
- Only the public job metadata enters `JOBS`; the trusted payload remains in the in-memory worker queue and its password is removed by the existing worker cleanup.
- `fillForm` preserves matching BPM-supplied editor names and IDs, otherwise uses the person picker before save. The script no longer writes BPM-owned editor number or UID fields directly.
- The picker error propagates before `clickWorkflowSaveAndWait`, and the hidden-ID-missing case cannot skip the picker.
- No job persistence or `index.html` changes were added.

## Concerns

- No live BPM submission was run because that would create or modify external BPM state; behavior is covered by route, source-contract, syntax, and interaction regression tests.
- Jobs remain process-local and globally visible exactly as before; per-user job persistence and isolation are intentionally outside Task 4.

## Review Fixes

### Status and commit

All four required Task 4 review findings were fixed and committed:

`6a08c3a fix: enforce trusted BPM identities`

### Changes

- `/api/bpm-submit` now resolves the current user and uses the same `trusted_bpm_payload` helper as queued jobs. Client `bpm` credentials and `editorName` are overwritten by the authenticated user's stored BPM credentials and display name.
- Removed the `editor_identity` mapping and all production `yewt` literals. Server payload merging now removes client/synthesized editor IDs and author contactor IDs.
- Author maintenance preserves BPM's existing contactor identity or uses the BPM person picker; it no longer writes `CONTACTORUID` or `CONTACTORDEPID` directly.
- Person picker completion now verifies both the selected name and the corresponding hidden person ID, and throws before save if either is invalid.
- `PRJEDITOR` and `EDITOR` are checked independently. A valid field is preserved while only the mismatched or ID-less field invokes the picker.
- No Task 5 job persistence was added.

### Red evidence

```bash
/Users/xiewentao/.cache/phei-task2-venv/bin/python3 -m unittest tests.test_server_auth.ServerCredentialHttpTests.test_legacy_bpm_submit_uses_current_users_stored_credentials -v
node --test tests/server_bpm_jobs.test.js
node --test tests/fill_topic_interactions.test.js
```

- Legacy submit test failed because the runner received the client-forged editor name instead of the current user's display name.
- Server source test failed because the hardcoded `yewt` identity mapping still existed.
- Interaction tests failed because identity helpers were not exported, author maintenance still directly wrote contactor IDs, and per-field picker/hidden-ID checks were missing.

### Green verification

```bash
/Users/xiewentao/.cache/phei-task2-venv/bin/python3 -m unittest tests.test_app_storage tests.test_server_auth -v
node --test tests/fill_topic_interactions.test.js
npm test
git diff --check
```

- Python storage/auth/credential suite: 21 passed.
- Focused Playwright interaction suite: 18 passed, 0 failed.
- Full npm suite: 30 passed, 0 failed.
- `git diff --check` and staged diff checks passed.

### Self-review and concerns

- Production `server.py` and `fill_topic.js` contain no hardcoded `yewt`; test fixtures in storage tests still use it only as an arbitrary encrypted account value.
- Remaining production `payload.get("bpm")` reads are inside the BPM execution layer, which now receives trusted payloads from both HTTP entry paths or credentials from the CLI environment.
- The picker regression tests cover both one-valid/one-invalid directions, both-valid preservation, and failure when the hidden ID remains empty.
- No live BPM save was executed because it would mutate external state; actual picker DOM behavior remains the only unverified external integration concern.

## Second Review Fixes

### Status and commit

The two additional Task 4 findings were fixed and committed:

`821e07d fix: validate complete BPM editor identities`

### Changes

- Confirmed from the BPM form integration that each main editor role has two required hidden identity fields: `PRJEDITORNO` plus `PRJEDITORUID`, and `EDITORNO` plus `EDITORUID`.
- `ensureEditorIdentity` now preserves a role only when its name, NO, and UID are all present and valid. A matching name with a missing UID invokes the picker; the two roles remain independent.
- `selectBpmPerson` waits for and verifies the selected name plus every required hidden ID. It reports the missing hidden selectors and fails before save if BPM does not populate all of them.
- Author contactor identity continues to use the same generic validation with its actual BPM hidden field, `CONTACTORUID`.
- Updated `references/input-schema.md` to remove the old editor name, `yewt`, hardcoded editor numbers, and stable-ID-default guidance. Names now come from the authenticated login user; NO and UID values remain empty in input and must come from the BPM page or person picker.

### Red evidence

```bash
node --test tests/fill_topic_interactions.test.js
node --test tests/server_bpm_jobs.test.js
```

- Interaction tests failed because `PRJEDITORUID` and `EDITORUID` were not part of the role guards, and picker callbacks received only the NO selector.
- Schema contract failed because the document still contained `yewt`, `2024070801`, and stable editor-ID defaults.

### Green verification

```bash
/Users/xiewentao/.cache/phei-task2-venv/bin/python3 -m unittest tests.test_app_storage tests.test_server_auth -v
npm test
git diff --check
```

- Python storage/auth/credential suite: 21 passed.
- Full npm suite: 31 passed, 0 failed.
- Focused interaction suite within npm: 18 passed, 0 failed.
- Staged and working-tree diff checks passed.

### Deferred scope

- Task 7: `index.html` still presents legacy client BPM fields. The Task 4 server security boundary already ignores those values; frontend removal/migration remains explicitly deferred to Task 7.
- Task 5: job visibility and per-user persisted job ownership remain explicitly deferred to Task 5. No job persistence or visibility behavior was changed in this review fix.
- No live BPM save was executed because it would mutate external state; the real BPM picker remains the external integration concern.

---

# Task 4 Report: Mail Delivery Batch Persistence

## Status

Implemented mail batch and per-recipient delivery persistence. The task adds a
user-scoped storage boundary for send history and retry preparation; SMTP transport
and HTTP/UI orchestration remain intentionally out of scope.

## Scope

- Modified `app_storage.py`.
- Modified `tests/test_mail_storage.py`.
- Left the pre-existing unrelated worktree changes untouched and outside the commit:
  `index.html`, `server.py`, `skills/phei-bpm-topic-declaration/SKILL.md`,
  `skills/phei-bpm-topic-declaration/references/input-schema.md`, and
  `tests/test_bpm_content_generation.py`.

## TDD Evidence

1. Added `MailBatchStorageTests` before implementing the storage methods.
2. Ran `.venv/bin/python -m unittest tests.test_mail_storage.MailBatchStorageTests -v`.
   The expected red result was five `AttributeError` failures because
   `create_mail_batch` did not yet exist.
3. Added schema migration 7 and the batch/delivery storage methods.
4. Re-ran mail-storage and core app-storage tests successfully.

## Implementation

- Added `mail_batches` and `mail_deliveries` with foreign keys, constrained status
  values, and indexes for user history and per-batch delivery lookup.
- Added `create_mail_batch`, `get_mail_batch`, `list_mail_batches`, and
  `start_mail_batch`; all reads and mutations enforce the owning user.
- Added `update_mail_delivery`, including persisted per-recipient error summaries
  and sent timestamps.
- Added transactional `finish_mail_batch`, which aggregates delivery rows into
  `succeeded`, `partial_failed`, or `failed` once all deliveries are terminal.
  Incomplete batches retain their queued/running state rather than being falsely
  marked finished.
- Added `create_retry_mail_batch`, which copies only failed recipients into a new
  queued batch and raises `ValueError("没有可重试的失败邮件")` when appropriate.

## Verification

- `.venv/bin/python -m unittest tests.test_mail_storage -v`
  - 10 tests passed.
- `.venv/bin/python -m unittest tests.test_app_storage -v`
  - 19 tests passed.
- `git diff --check`
  - Passed.

## Review Fix: Atomic Claim and Delivery State Machine

### Commit

`d8567ee fix: enforce atomic mail delivery states`

### Changes

- `start_mail_batch` now returns a batch only when its single SQL update wins the
  atomic `queued -> running` transition. Repeated or concurrent start attempts
  return `None` and cannot create a second sender.
- Delivery transitions are now enforced in SQL: a running batch permits only
  `queued -> sending -> succeeded|failed`. A queued batch, another user, and a
  terminal delivery cannot be changed.
- `finish_mail_batch` accepts only a running batch. It leaves incomplete work
  running and makes one terminal aggregate update; a completed batch cannot be
  finished or mutated again.
- Added regressions for repeated start claims, sending before a batch starts,
  terminal delivery rollback, and post-finish mutation attempts. Existing
  success and retry tests now follow the production transition sequence.

### Verification

```bash
.venv/bin/python -m unittest tests.test_mail_storage tests.test_app_storage
```

- 31 tests passed.
