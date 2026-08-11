# DOCX Structured Field Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reliably extract topic title and first-author name from DOCX application forms, with a single source-grounded DeepSeek Flash fallback only when native parsing leaves a core field empty.

**Architecture:** Keep deterministic Word parsing in `extract_application_docx.py`, including label aliases and row-level masking. Add a small recovery boundary in `server.py` that detects missing core fields, calls the existing fast model once, validates candidates against sanitized source text, and merges only grounded values before report generation or BPM import.

**Tech Stack:** Python 3.12+, `python-docx`, Python `unittest`, existing DeepSeek OpenAI-compatible API client.

## Global Constraints

- DOCX remains the only accepted application format.
- Native parsing is always attempted first; no OCR or local multimodal model is added.
- The fast model is called at most once and only when `选题名称` or `姓名` remains missing.
- Model candidates must occur in sanitized source text before they are accepted.
- Sensitive values must not appear in the fallback prompt or runtime logs.
- A fallback failure must not prevent the normal report model from running.

---

### Task 1: Deterministic DOCX Field Extraction

**Files:**
- Modify: `skills/phei-topic-planning-report/scripts/extract_application_docx.py`
- Create: `tests/test_extract_application_docx.py`

**Interfaces:**
- Produces: `canonical_key(key: str) -> str` with aliases for `姓 名` and `选题名`.
- Produces: `extract_field_pairs(table_rows: list[dict], include_sensitive: bool) -> dict[str, str]` that scans recognized adjacent labels.
- Produces: `mask_table_rows(table_rows: list[dict]) -> list[dict]` for safe model input.

- [x] Write synthetic-DOCX tests for a leading section cell, spaced name label, canonical title alias, and masked sensitive row values.
- [x] Run `python3 -m unittest tests.test_extract_application_docx -v` and verify failures.
- [x] Implement label aliases, known-label scanning, duplicate-safe field insertion, and row masking.
- [x] Re-run the focused tests and verify they pass.

### Task 2: Source-Grounded Fast-Model Fallback

**Files:**
- Modify: `server.py`
- Create: `tests/test_structured_field_recovery.py`
- Modify: `tests/test_server_auth.py`

**Interfaces:**
- Produces: `missing_core_fields(facts: dict) -> list[str]`.
- Produces: `recover_missing_structured_fields(facts: dict) -> dict`.
- Produces: `source_contains_candidate(facts: dict, value: str) -> bool`.

- [x] Write tests proving complete native facts skip Flash, missing facts call it once, grounded candidates merge, hallucinated candidates are rejected, and model errors are non-blocking.
- [x] Run `python3 -m unittest tests.test_structured_field_recovery -v` and verify failures.
- [x] Implement the minimal recovery prompt, strict candidate validation, safe merge, and field-name-only logging.
- [x] Invoke recovery before full report generation and before direct BPM source import.
- [x] Add `选题名` to remaining title aliases and compact fact selection.
- [x] Re-run focused tests and model configuration tests.

### Task 3: Regression Verification

**Files:**
- No production-file additions.

**Interfaces:**
- Consumes the existing stored DOCX only for local validation; it is never copied into Git.

- [x] Run all Node tests with `npm test`.
- [x] Run all Python tests with `python3 -m unittest discover -s tests -p 'test_*.py' -q`.
- [x] Run the extractor against the stored regression DOCX and confirm the expected title and first author without a model call.
- [x] Scan tracked changes for credentials and sensitive sample values.
- [x] Restart the service on `0.0.0.0:4175` and verify `/api/health` or the static page responds.
