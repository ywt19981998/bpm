# Digital Contract Intake Form Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a reusable Word `.docx` information-collection form for digital textbook publishing contracts.

**Architecture:** A focused Python generator creates a fixed-layout `.docx` from the approved field specification. A Python structural test opens the generated document and verifies the five required sections, contributor-table headers, delivery-table headers, and landscape contributor page. The generated document is visually rendered to PDF/PNG for a final layout inspection.

**Tech Stack:** Python 3, python-docx, LibreOffice headless conversion, pdftoppm.

## Global Constraints

- Produce `.docx`, not legacy `.doc`, for reliable author editing and later structured parsing.
- Include only the five approved information sections.
- Do not include a separate work-name field; the future contract uses the topic name as the work name.
- Preserve sensitive information as editable table fields; do not embed ID-card image files.
- Use A4 portrait for ordinary sections, A4 landscape for the all-copyright-holders table, and return to portrait for the delivery checklist.

---

### Task 1: Specify the approved form structure with a failing test

**Files:**
- Create: `tests/test_digital_contract_intake_form.py`

**Interfaces:**
- Consumes: `output/doc/数字教材出版合同信息采集表.docx` once generated.
- Produces: a repeatable structural assertion for the required sections, headers, and row counts.

- [ ] **Step 1: Write the failing structural test**

```python
def test_generated_form_has_approved_sections_and_tables():
    assert OUTPUT_PATH.exists(), "Run the intake-form generator first."
    document = Document(OUTPUT_PATH)
    text = "\n".join(p.text for p in document.paragraphs)
    assert "一、合同信息" in text
    assert "二、甲方信息" in text
    assert "三、全体著作权人表" in text
    assert "四、出版资助" in text
    assert "五、交付清单" in text
    assert header_cells(document.tables[2]) == COPYRIGHT_HEADERS
    assert header_cells(document.tables[4]) == DELIVERY_HEADERS
```

- [ ] **Step 2: Run the test to verify the expected failure**

Run:

```bash
/Users/xiewentao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests/test_digital_contract_intake_form.py -v
```

Expected: FAIL because the output file does not exist.

### Task 2: Generate and validate the approved Word intake form

**Files:**
- Create: `scripts/generate_digital_contract_intake_form.py`
- Create: `output/doc/数字教材出版合同信息采集表.docx`
- Verify: `tests/test_digital_contract_intake_form.py`

**Interfaces:**
- Consumes: the test's expected Word structure.
- Produces: `output/doc/数字教材出版合同信息采集表.docx`, an editable author-facing form.

- [ ] **Step 1: Implement the generator with approved fields and layout**

```python
CONTRACT_INFO_FIELDS = ["选题名称", "署名方式"]
PARTY_A_FIELDS = ["甲方名称", "著作权人代表", "电话", "身份证号", "邮箱", "通信地址"]
COPYRIGHT_HEADERS = ["序号", "姓名", "证件类型", "证件号", "著作权人电话", "报酬比例(%)", "身份证复印件文件名", "地址", "邮件", "邮编", "工作单位"]
DELIVERY_HEADERS = ["序号", "内容类型", "内容明细", "交付数量", "备注"]
```

- [ ] **Step 2: Generate the form and run the structural test**

Run:

```bash
/Users/xiewentao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/generate_digital_contract_intake_form.py
/Users/xiewentao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest tests/test_digital_contract_intake_form.py -v
```

Expected: PASS.

- [ ] **Step 3: Render and inspect the form**

Run:

```bash
mkdir -p /tmp/digital-contract-intake-preview
soffice -env:UserInstallation=file:///tmp/lo-contract-intake-profile --headless --convert-to pdf --outdir /tmp/digital-contract-intake-preview output/doc/数字教材出版合同信息采集表.docx
pdftoppm -png -r 150 /tmp/digital-contract-intake-preview/数字教材出版合同信息采集表.pdf /tmp/digital-contract-intake-preview/page
```

Expected: portrait pages for sections one, two, four and five; one readable landscape page for the 11-column contributor table; no clipped table headings.

- [ ] **Step 4: Commit**

```bash
git add tests/test_digital_contract_intake_form.py output/doc/数字教材出版合同信息采集表.docx
git commit -m "test: verify digital contract intake form"
```

## Plan Self-Review

- Spec coverage: task 1 captures the approved document contract as a failing test. Task 2 implements all five approved sections, required fields, row counts, file format, orientation, sensitive-file-name handling, and visual rendering.
- Placeholder scan: no unresolved placeholder steps or undefined functions remain; helper functions are specified as generator internals in task 1.
- Type consistency: the generator produces the output path consumed by the test, and the test verifies the exact headers declared in task 2.
