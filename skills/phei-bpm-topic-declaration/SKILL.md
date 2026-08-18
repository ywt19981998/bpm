---
name: phei-bpm-topic-declaration
description: Use when the user asks to log into PHEI BPM at bpm.phei.com.cn and complete 编辑 -> 选题申报 from a user-provided topic sheet or draft book proposal. Parse the proposal into the field schema, run the bundled Playwright automation, save the draft, verify the created title/number, and report the result. Credentials must come from the user message or environment variables, not from this skill.
---

# PHEI BPM Topic Declaration

Use this skill for PHEI BPM `编辑 -> 选题申报` work.

## Inputs

Read [references/input-schema.md](references/input-schema.md) and normalize the user's material into JSON before running the script.

Minimum practical input:

- `bookName`
- `brief`
- `reader`
- `feature`
- `compare`

Prefer also filling:

- `readerNum`
- `scriptDate`
- `makingDate`
- `publishDate`
- `words`
- `price`
- `totalNum`
- `firstNum`

## Current Business Rules

Apply these defaults unless the user explicitly changes them:

- Keep the main topic declaration form's `主要作（译）者编号` and `主要作（译）者姓名` blank. These fields should be associated from BPM's author library manually, so do not write `authorCode`, `authorId`, or `authorName` into the main topic form even when the uploaded application form contains author information.
- For the separate `作译者信息维护 -> 新增作译者` step, extract all available author fields from the uploaded application form and submit them directly. Do not add a separate review/listing page for every author field. `作者简介` is the only field that must be substantively present: if the application form lacks it, use the configured model/search workflow to retrieve public school/department official information and summarize it into a 50-1000 character author bio. In the web app, this means adding `author_official_search_context` to the report-generation prompt when official search results are available. Other missing author-maintenance fields may be filled with a single full-width space `　` so the BPM form can save, rather than blocking the workflow.
- 网页中由用户明确选择是否点击“新增作译者”；作者已经存在时只点击“填报选题”。填报选题流程不得新增或修改作译者，新增作译者流程不得创建选题、评分或成本估算。
- After BPM login, open the top-right personal profile panel and read the full account-holder name shown there. This BPM profile name is authoritative for both `projectEditor`/策划编辑 and `editor`/拟责任编辑. The web account `displayName` is only a pre-login fallback and continues to control the exported planning-report filename/template责任编辑 field.
- BPM declaration classification has fixed top-level values: `class1` must be 教育 (`02`), `class2` must be 本科研究生 (`0201`), `gbClass` must be `G`, and `readLevel` must be 高等理工. Only `class3` and `class4` should be chosen from the topic title, discipline, generated report, or model-provided classification suggestion.
- `feature` and `compare` are BPM required fields. Prefer the dedicated report-generation output `bpmFields.feature` and `bpmFields.compare`; only fall back to source form text or report sections when those dedicated fields are missing. `feature` should cover 内容范围、写作特点、实践教学、教学资源建设、其他特点.
- Fixed topic-form values:
  - reader group base: `100`
  - language: `中文`
  - manuscript source: `作者独立投稿`
  - manuscript format: `电子文件`
  - planned award: `无`
  - color printing: `单色`
  - estimated words: `350.00`
  - estimated price: `59.8`
  - remuneration word count: `0`
  - remuneration mode: `销数版税`
  - remuneration standard: `8%`
  - publication mode: `常规出版`
  - subsidy: `否`, amount `0`, complimentary copies `0`
  - guaranteed sale: `否`, copies `0`, discount `0`
  - digital authorization: `授权`
  - digital remuneration allocation: `是`, standard `8`
  - total print run: `3000`
  - first print run: `1200`
  - project: `无`
  - internal topic category: `普通选题`
  - cost estimation: `是`
  - major topic filing: `否`
  - urgency: `普通`
  - meeting: `否`
- Topic score table uses the scores generated in the planning report. Fill the Ext grid `选题分级评分表` self-score column (`SELFSCORE`) for the six rows and the total row, and set the main total score field (`SCORE`) to the same total.
- Cost estimation uses fixed values from `references/input-schema.md` `costDefaults`. Fill the `成本估算单V2` subform after the main form: 编加单价 `6.50`, 校对单价 `1.00`, 三校核红单价 `1.50`, 排版单价 `11.50`, 封面单价 `800.00`, 印张 `14.000`, 印数浮动值 `200`, 总印次 `1`, 装帧 `平装覆膜`, 开本 `16(185*260)`, 正文纸规格 `787*1092`, 正文纸名称 `胶版`, 正文纸克重 `70克`, 正文印刷色数 `1`, 正文制版方式 `CTP制版`, 正文印刷方式 `对开`, CTP 数码打样面数 `0`, 封面纸名称 `铜版`, 封面纸克重 `200克`, 封面印刷色数 `4`, 封面整饰 `亚膜`, 封面制版方式 `CTP制版`, 封面印刷方式 `对开`, 产发率 `85.00`, 退货率 `20.00`, 发货折扣 `65.00`, 储运费扣点 `6.00`, 管理费 `7500.00`, 总发货册数 `2550.0`, 总销售册数 `2040.00`, 销售周期 `3` 年, 资助 `否`/`0`. Do not fill the cost-subform `版权字数`/`CHARNUM` field; leave it to the system.

## Credentials

Do not write credentials into the skill.

Use one of:

- `BPM_USER`
- `BPM_PASSWORD`
- `BPM_URL` optional, defaults to `http://bpm.phei.com.cn:8088/portal/index.jsp`

If the user supplied credentials in the chat, pass them to the script via env vars for that run only.

## Workflow

For web-app testing, the workflow can be split from report generation:

- Upload the original topic application DOCX plus an already confirmed topic planning report DOCX.
- Use the application form for author/contact/date/base BPM fields.
- Use the planning report for sections one through six, self-scores, title, and final report prose.
- Mark imported report sections as confirmed so the user can test BPM filling without rerunning LLM generation.

1. For a new or changed BPM page, first inspect the form without saving:

```bash
NODE_PATH=/abs/project/node_modules node scripts/fill_topic.js inspect /abs/output/dir
```

This logs visible fields and writes `bpm-inspect-form.png`.

2. Parse the user's topic sheet into JSON using the schema reference.
3. Save the JSON to a temp file in the current workspace.
4. If the user selected “填报选题”, run:

```bash
NODE_PATH=/abs/project/node_modules node scripts/fill_topic.js submit-topic /abs/path/topic.json
```

5. If the user selected “新增作译者”, run:

```bash
NODE_PATH=/abs/project/node_modules node scripts/fill_topic.js submit-author /abs/path/topic.json
```

6. Inspect the script result JSON for the selected operation.
7. Confirm the created title/number or saved author name back to the user.

## Validation

The script already:

- logs in
- opens `编辑 -> 选题申报`
- creates a new draft
- fills the known fields
- clicks `暂存`
- re-reads the worklist to verify the saved title

Topic results include ordered verification milestones:

- `login_verified`
- `topic_form_opened`
- `topic_draft_saved`
- `cost_estimate_saved`
- `worklist_verified`

`inspect` mode opens the same form and captures fields/screenshots, but does not click `暂存`.

If verification fails, inspect screenshots written next to the JSON file and report the blocker.

For the web app queue, do not mark a job completed just because the Node process returned JSON. 选题任务 is successful only when the returned JSON has `ok: true`, a non-empty verified `title`, and the final `worklist_verified` milestone. 作译者任务 is successful only when the returned JSON has `ok: true`, a non-empty `authorName`, a non-empty BPM-generated `authorCode`, and `verified: true` after querying the BPM author list by exact name and code. If the required result is missing, mark that job failed. Preserve completed milestones even on failure, together with the run's `topic.json`, stdout/stderr, and screenshots under the web app's `output/bpm-runs/` directory for diagnosis.

## Safety

- Do not auto-delete extra blank drafts unless the user explicitly asks.
- Do not query, skip, or merge duplicate authors automatically; the user decides whether to run “新增作译者”.
- If the site workflow changes, update the selectors in the bundled script instead of improvising repeated manual probing.
- If `playwright` is missing, install it in the current workspace, not in the user's home directory, unless the user explicitly asks otherwise.
