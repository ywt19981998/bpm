# 邮件中心实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有登录工作台中增加按用户隔离的邮件中心，支持 SMTP 个人配置、教师名单上传、邮件模板管理、个性化预览、二次确认逐封发送和发送记录。

**Architecture:** 复用现有 SQLite 用户体系和 AES-GCM 凭据表；新增 `mail_center.py` 承担名单解析、变量替换与 SMTP 传输，`app_storage.py` 负责模板、草稿和发送批次持久化，`server.py` 只增加鉴权路由与后台任务调度。前端继续使用现有单页 `index.html`，邮件编辑区不重复展示收件人，名单只在右侧管理。

**Tech Stack:** Python 3、SQLite、`cryptography`、`openpyxl`、标准库 `csv`/`smtplib`/`email.message.EmailMessage`、原生 HTML/CSS/JavaScript、Node test runner、Python `unittest`。

## Global Constraints

- 收件人名单支持 `.xlsx` 和 `.csv`，姓名、邮箱为必需字段，其他列作为可选个性化变量。
- 每位用户只能访问自己的 SMTP 配置、模板、草稿、名单和发送记录。
- SMTP 密码或授权码使用现有 AES-GCM 机制加密，不返回前端、不写入日志。
- SMTP 默认值为 `smtp.qiye.163.com`、端口 `465`、SSL 开启，但允许用户修改。
- 邮件必须逐封发送；点击发送后必须经过最终确认，不能把所有教师放入同一收件人列表。
- 中间编辑区不显示收件人标签；名单只在右侧管理。
- 第一版不包含教师网络检索、附件、定时发送、打开率追踪和营销统计。
- 现有选题策划报告、BPM 和作译者功能不得发生行为回归。

## 文件结构

- Create: `mail_center.py`，名单解析、模板变量、邮件校验和 SMTP 连接。
- Modify: `app_storage.py`，通用加密凭据载荷及邮件数据表/方法。
- Modify: `server.py`，邮件和 SMTP API、发送后台任务。
- Modify: `index.html`，邮件入口、邮件中心和个人 SMTP 配置。
- Create: `mail_ui_helpers.js`，前端邮件状态和变量预览的纯函数。
- Modify: `requirements.txt`，增加 `openpyxl>=3.1.5`。
- Create: `tests/test_mail_center.py`，名单、变量、SMTP 单元测试。
- Create: `tests/test_mail_storage.py`，模板、草稿、批次和用户隔离测试。
- Create: `tests/test_server_mail.py`，邮件 API 和发送任务测试。
- Create: `tests/index_mail_center.test.js`，邮件页面结构与交互契约测试。
- Modify: `tests/index_auth_ui.test.js`，个人 SMTP 配置测试。
- Modify: `README.md`，补充 SMTP 配置和邮件中心使用说明。

---

### Task 1: 扩展加密凭据以保存完整 SMTP 配置

**Files:**
- Modify: `app_storage.py`
- Modify: `tests/test_app_storage.py`

**Interfaces:**
- Produces: `put_integration_secret(user_id: int, system_type: str, payload: dict) -> None`
- Produces: `get_integration_secret(user_id: int, system_type: str) -> dict | None`
- Preserves: `put_integration_credentials`、`get_integration_credentials` 现有 BPM 行为。

- [ ] **Step 1: 写通用加密载荷失败测试**

```python
def test_smtp_secret_payload_is_encrypted_masked_and_user_isolated(self):
    payload = {
        "host": "smtp.qiye.163.com",
        "port": 465,
        "security": "ssl",
        "account": "editor@example.com",
        "password": "smtp-auth-code",
        "fromName": "张编辑",
        "fromAddress": "editor@example.com",
    }
    self.store.put_integration_secret(self.user_id, "smtp", payload)
    self.assertEqual(self.store.get_integration_secret(self.user_id, "smtp"), payload)
    self.assertIsNone(self.store.get_integration_secret(self.other_user_id, "smtp"))
    self.assertNotIn("smtp-auth-code", self.database_text())
```

- [ ] **Step 2: 运行测试并确认因方法不存在而失败**

Run: `.venv/bin/python -m unittest tests.test_app_storage.AppStoreCredentialTests.test_smtp_secret_payload_is_encrypted_masked_and_user_isolated -v`

Expected: `ERROR`，提示 `AppStore` 没有 `put_integration_secret`。

- [ ] **Step 3: 抽取通用 AES-GCM 方法并保留 BPM 包装器**

```python
def put_integration_secret(self, user_id, system_type, payload):
    if not isinstance(payload, dict) or not payload:
        raise ValueError("integration secret payload must be a non-empty object")
    key = self._credential_key()
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(
        nonce, encoded, self._credential_associated_data(user_id, system_type)
    )
    self._upsert_integration_ciphertext(user_id, system_type, ciphertext, nonce)

def get_integration_secret(self, user_id, system_type):
    row = self._integration_ciphertext_row(user_id, system_type)
    if row is None:
        return None
    payload = AESGCM(self._credential_key()).decrypt(
        row["nonce"], row["ciphertext"],
        self._credential_associated_data(user_id, system_type),
    )
    result = json.loads(payload.decode("utf-8"))
    if not isinstance(result, dict):
        raise CredentialConfigurationError("integration credentials payload is invalid")
    return result
```

让 `put_integration_credentials` 调用 `put_integration_secret`，让 `get_integration_credentials` 从通用载荷中校验并返回 `account/password`，保持已有 BPM 测试不变。

- [ ] **Step 4: 运行凭据测试**

Run: `.venv/bin/python -m unittest tests.test_app_storage.AppStoreCredentialTests -v`

Expected: 全部通过，数据库明文扫描找不到 SMTP 授权码。

- [ ] **Step 5: 提交凭据扩展**

```bash
git add app_storage.py tests/test_app_storage.py
git commit -m "feat: store encrypted smtp settings"
```

### Task 2: 实现教师名单解析和个性化变量替换

**Files:**
- Create: `mail_center.py`
- Create: `tests/test_mail_center.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `parse_recipient_file(data: bytes, filename: str) -> dict`
- Produces: `render_mail_text(template: str, variables: dict) -> str`
- Produces: `validate_mail_compose(subject: str, body: str, recipients: list[dict]) -> list[str]`

- [ ] **Step 1: 写 CSV/XLSX、别名、去重和变量替换失败测试**

```python
class MailRecipientTests(unittest.TestCase):
    def test_csv_aliases_and_duplicate_email(self):
        data = "教师姓名,电子邮箱,学校\n张三,ZHANG@example.com,A大学\n李四,zhang@example.com,B大学\n".encode("utf-8-sig")
        result = parse_recipient_file(data, "teachers.csv")
        self.assertEqual(len(result["valid"]), 1)
        self.assertEqual(result["duplicates"], 1)
        self.assertEqual(result["valid"][0]["name"], "张三")

    def test_missing_optional_variable_becomes_empty(self):
        rendered = render_mail_text("{{姓名}}老师，您好，{{学院}}", {"姓名": "王五"})
        self.assertEqual(rendered, "王五老师，您好，")
```

另写 XLSX 内存工作簿测试、非法邮箱测试、缺少姓名/邮箱表头测试和 `gb18030` CSV 测试。

- [ ] **Step 2: 运行测试并确认导入失败**

Run: `.venv/bin/python -m unittest tests.test_mail_center -v`

Expected: `ERROR`，提示找不到 `mail_center`。

- [ ] **Step 3: 增加依赖并实现解析器**

在 `requirements.txt` 增加：

```text
openpyxl>=3.1.5
```

安装项目锁定依赖：

Run: `.venv/bin/python -m pip install -r requirements.txt`

Expected: `openpyxl` 安装成功，命令退出码为 0。

实现规范化表头：

```python
NAME_HEADERS = {"姓名", "教师姓名", "老师姓名", "name"}
EMAIL_HEADERS = {"邮箱", "电子邮箱", "e-mail", "email"}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

def render_mail_text(template, variables):
    normalized = {normalize_header(key): str(value or "") for key, value in variables.items()}
    return VARIABLE_RE.sub(
        lambda match: normalized.get(normalize_header(match.group(1)), ""),
        str(template or ""),
    )
```

CSV 按 `utf-8-sig`、`gb18030` 顺序解码；XLSX 使用 `load_workbook(BytesIO(data), read_only=True, data_only=True)`。返回值固定为 `valid`、`invalid`、`duplicates`、`columns` 四项。

- [ ] **Step 4: 运行名单解析测试**

Run: `.venv/bin/python -m unittest tests.test_mail_center.MailRecipientTests -v`

Expected: 全部通过。

- [ ] **Step 5: 提交名单解析模块**

```bash
git add mail_center.py requirements.txt tests/test_mail_center.py
git commit -m "feat: parse and personalize mail recipients"
```

### Task 3: 持久化模板和当前邮件草稿

**Files:**
- Modify: `app_storage.py`
- Create: `tests/test_mail_storage.py`

**Interfaces:**
- Produces: `create_mail_template`、`list_mail_templates`、`update_mail_template`、`delete_mail_template`
- Produces: `ensure_default_mail_templates(user_id: int, defaults: list[dict]) -> list[dict]`
- Produces: `get_mail_draft(user_id)`、`put_mail_draft(user_id, payload)`

- [ ] **Step 1: 写模板 CRUD、默认模板、草稿恢复和用户隔离测试**

```python
def test_template_crud_is_user_scoped(self):
    created = self.store.create_mail_template(
        self.user_id, "教材主编邀请", "主题 {{姓名}}", "{{姓名}}老师，您好"
    )
    self.assertEqual(len(self.store.list_mail_templates(self.user_id)), 1)
    self.assertEqual(self.store.list_mail_templates(self.other_user_id), [])
    updated = self.store.update_mail_template(
        self.user_id, created["id"], "主编邀请", "新主题", "新正文"
    )
    self.assertEqual(updated["name"], "主编邀请")
    self.assertTrue(self.store.delete_mail_template(self.user_id, created["id"]))
```

默认模板测试调用 `ensure_default_mail_templates` 两次，并断言只创建一次；草稿测试必须断言主题、正文、模板 ID、收件人快照可在重新创建 `AppStore` 后恢复，其他用户不可见。

- [ ] **Step 2: 运行测试并确认表不存在**

Run: `.venv/bin/python -m unittest tests.test_mail_storage.MailTemplateStorageTests -v`

Expected: `ERROR`，提示方法不存在。

- [ ] **Step 3: 增加迁移和存储方法**

新增：

```sql
CREATE TABLE IF NOT EXISTS mail_templates (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  last_used_at INTEGER,
  UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS mail_drafts (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  template_id TEXT REFERENCES mail_templates(id) ON DELETE SET NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  recipients_json TEXT NOT NULL,
  updated_at INTEGER NOT NULL
);
```

模板 ID 使用 `uuid.uuid4().hex[:12]`，所有更新和删除 SQL 同时带 `user_id`。草稿收件人保存标准化后的 JSON，不保存上传原文件。

默认模板由服务器传入固定的 `[{"name", "subject", "body"}]` 列表；`ensure_default_mail_templates` 仅在该用户模板数为零时用一个事务插入，防止重复初始化。

- [ ] **Step 4: 运行存储测试**

Run: `.venv/bin/python -m unittest tests.test_mail_storage.MailTemplateStorageTests -v`

Expected: 全部通过。

- [ ] **Step 5: 提交模板和草稿存储**

```bash
git add app_storage.py tests/test_mail_storage.py
git commit -m "feat: persist mail templates and drafts"
```

### Task 4: 持久化发送批次和逐封结果

**Files:**
- Modify: `app_storage.py`
- Modify: `tests/test_mail_storage.py`

**Interfaces:**
- Produces: `create_mail_batch(user_id, subject, body, deliveries) -> dict`
- Produces: `start_mail_batch(user_id, batch_id) -> dict`
- Produces: `update_mail_delivery(user_id, batch_id, delivery_id, status, error_summary=None) -> None`
- Produces: `finish_mail_batch(user_id, batch_id) -> dict`
- Produces: `list_mail_batches(user_id, limit=30)`、`get_mail_batch(user_id, batch_id)`
- Produces: `create_retry_mail_batch(user_id, batch_id) -> dict`

- [ ] **Step 1: 写批次状态汇总和失败重试数据测试**

```python
def test_batch_rolls_up_partial_failure(self):
    batch = self.store.create_mail_batch(
        self.user_id,
        "合作邀请",
        "{{姓名}}老师，您好",
        [
            {"name": "张三", "email": "a@example.com", "subject": "合作邀请", "body": "张三老师，您好"},
            {"name": "李四", "email": "b@example.com", "subject": "合作邀请", "body": "李四老师，您好"},
        ],
    )
    first, second = batch["deliveries"]
    self.store.update_mail_delivery(self.user_id, batch["id"], first["id"], "succeeded")
    self.store.update_mail_delivery(self.user_id, batch["id"], second["id"], "failed", "连接中断")
    finished = self.store.finish_mail_batch(self.user_id, batch["id"])
    self.assertEqual(finished["status"], "partial_failed")
    self.assertEqual(finished["sentCount"], 1)
    self.assertEqual(finished["failedCount"], 1)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `.venv/bin/python -m unittest tests.test_mail_storage.MailBatchStorageTests -v`

Expected: `ERROR`，提示批次方法不存在。

- [ ] **Step 3: 增加批次和投递表**

```sql
CREATE TABLE IF NOT EXISTS mail_batches (
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subject_template TEXT NOT NULL,
  body_template TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','running','succeeded','partial_failed','failed')),
  total_count INTEGER NOT NULL,
  sent_count INTEGER NOT NULL DEFAULT 0,
  failed_count INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  finished_at INTEGER,
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS mail_deliveries (
  id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL REFERENCES mail_batches(id) ON DELETE CASCADE,
  recipient_name TEXT NOT NULL,
  recipient_email TEXT NOT NULL,
  rendered_subject TEXT NOT NULL,
  rendered_body TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','sending','succeeded','failed')),
  error_summary TEXT,
  sent_at INTEGER,
  updated_at INTEGER NOT NULL
);
```

`finish_mail_batch` 在一个事务中统计投递行：全成功为 `succeeded`，成功和失败并存为 `partial_failed`，全失败为 `failed`。

`create_retry_mail_batch` 只复制原批次中 `failed` 的投递行，并使用新的批次 ID；原批次和成功投递记录保持不变。没有失败项时抛出 `ValueError("没有可重试的失败邮件")`。

- [ ] **Step 4: 运行批次测试**

Run: `.venv/bin/python -m unittest tests.test_mail_storage.MailBatchStorageTests -v`

Expected: 全部通过。

- [ ] **Step 5: 提交发送记录存储**

```bash
git add app_storage.py tests/test_mail_storage.py
git commit -m "feat: persist mail delivery batches"
```

### Task 5: 实现 SMTP 连接测试和逐封发送

**Files:**
- Modify: `mail_center.py`
- Modify: `tests/test_mail_center.py`

**Interfaces:**
- Produces: `normalize_smtp_settings(payload: dict) -> dict`
- Produces: `test_smtp_connection(settings: dict, smtp_factory=None) -> None`
- Produces: `send_smtp_message(settings: dict, recipient: dict, smtp_factory=None) -> None`

- [ ] **Step 1: 用假 SMTP 写连接、登录和邮件头测试**

```python
def test_send_uses_one_recipient_and_never_exposes_password(self):
    fake = FakeSMTP()
    settings = smtp_settings(password="smtp-auth-code")
    send_smtp_message(
        settings,
        {"name": "张三", "email": "teacher@example.edu.cn", "subject": "教材合作", "body": "张老师您好"},
        smtp_factory=lambda *_args, **_kwargs: fake,
    )
    self.assertEqual(fake.login_args, ("editor@example.com", "smtp-auth-code"))
    self.assertEqual(fake.messages[0]["To"], "teacher@example.edu.cn")
    self.assertNotIn("smtp-auth-code", fake.messages[0].as_string())
```

同时覆盖 `ssl`、`starttls`、无加密、非法端口和登录失败。

- [ ] **Step 2: 运行测试并确认发送函数不存在**

Run: `.venv/bin/python -m unittest tests.test_mail_center.MailSmtpTests -v`

Expected: `ERROR`，提示导入发送函数失败。

- [ ] **Step 3: 使用标准库实现 SMTP**

```python
message = EmailMessage()
message["From"] = formataddr((settings["fromName"], settings["fromAddress"]))
message["To"] = recipient["email"]
message["Subject"] = recipient["subject"]
message.set_content(recipient["body"])
```

`ssl` 使用 `smtplib.SMTP_SSL`，`starttls` 使用 `smtplib.SMTP` 后调用 `starttls(context=ssl.create_default_context())`。连接超时固定为 20 秒。任何异常只向上抛出类型和可读摘要，不拼接密码。

- [ ] **Step 4: 运行 SMTP 单元测试**

Run: `.venv/bin/python -m unittest tests.test_mail_center.MailSmtpTests -v`

Expected: 全部通过且不访问真实网络。

- [ ] **Step 5: 提交 SMTP 传输层**

```bash
git add mail_center.py tests/test_mail_center.py
git commit -m "feat: send personalized mail through smtp"
```

### Task 6: 增加 SMTP、模板、名单、预览和发送 API

**Files:**
- Modify: `server.py`
- Create: `tests/test_server_mail.py`

**Interfaces:**
- Produces: `/api/integrations/smtp` GET/PUT/DELETE
- Produces: `/api/integrations/smtp/test` POST
- Produces: `/api/mail/templates` GET/POST
- Produces: `/api/mail/templates/{id}` PUT/DELETE
- Produces: `/api/mail/draft` GET/PUT
- Produces: `/api/mail/recipients/parse` POST multipart
- Produces: `/api/mail/preview` POST
- Produces: `/api/mail/batches` GET/POST
- Produces: `/api/mail/batches/{id}` GET
- Produces: `/api/mail/batches/{id}/retry` POST

- [ ] **Step 1: 写鉴权、用户隔离、密码不回显和二次确认测试**

```python
def test_create_batch_requires_explicit_confirmation(self):
    self.save_smtp_config()
    status, _, body = self.request(
        "POST", "/api/mail/batches",
        {"confirmed": False, "subject": "邀请", "body": "{{姓名}}老师您好", "recipients": [recipient()]},
        cookie=self.cookie,
    )
    self.assertEqual(status, 400)
    self.assertEqual(json.loads(body)["code"], "MAIL_CONFIRMATION_REQUIRED")
```

接口测试还需覆盖：无会话 401、另一用户看不到模板/批次、SMTP GET 只返回掩码、解析无效文件 400、预览变量替换、发送后台线程使用服务器端 SMTP 凭据。

- [ ] **Step 2: 运行 API 测试并确认路由 404**

Run: `.venv/bin/python -m unittest tests.test_server_mail -v`

Expected: 失败状态为 404。

- [ ] **Step 3: 实现路由和后台发送调度**

后台任务入口固定为：

```python
def process_mail_batch(batch_id: str, user_id: int):
    settings = APP_STORE.get_integration_secret(user_id, "smtp")
    batch = APP_STORE.start_mail_batch(user_id, batch_id)
    try:
        for delivery in batch["deliveries"]:
            APP_STORE.update_mail_delivery(user_id, batch_id, delivery["id"], "sending")
            try:
                send_smtp_message(settings, delivery)
                APP_STORE.update_mail_delivery(user_id, batch_id, delivery["id"], "succeeded")
            except Exception as error:
                APP_STORE.update_mail_delivery(
                    user_id, batch_id, delivery["id"], "failed", safe_mail_error(error)
                )
        APP_STORE.finish_mail_batch(user_id, batch_id)
    finally:
        if isinstance(settings, dict):
            settings.clear()
```

创建批次前在服务器端重新执行名单、主题、正文和 SMTP 配置校验；客户端不得上传 SMTP 密码。后台线程使用 `daemon=True`，服务启动时把遗留的 `queued/running` 邮件批次标记为失败并提示人工核对。

- [ ] **Step 4: 运行邮件 API 测试**

Run: `.venv/bin/python -m unittest tests.test_server_mail -v`

Expected: 全部通过。

- [ ] **Step 5: 提交邮件 API**

```bash
git add server.py tests/test_server_mail.py
git commit -m "feat: expose authenticated mail center api"
```

### Task 7: 在个人设置中增加 SMTP 配置

**Files:**
- Modify: `index.html`
- Modify: `tests/index_auth_ui.test.js`

**Interfaces:**
- Consumes: `/api/integrations/smtp`、`/api/integrations/smtp/test`
- Produces: `loadSmtpCredentialStatus`、`saveSmtpCredentials`、`testSmtpCredentials`、`clearSmtpCredentials`

- [ ] **Step 1: 写个人设置 DOM 和不回显密码测试**

```javascript
test('SMTP credentials are stored in personal settings without client persistence', () => {
  assert.match(source, /id="smtpHost"/);
  assert.match(source, /id="smtpPassword"[^>]+type="password"/);
  assert.match(source, /\/api\/integrations\/smtp/);
  assert.doesNotMatch(source, /localStorage\.setItem\([^\n]*smtp/i);
  assert.match(source, /smtpPassword\.value\s*=\s*""/);
});
```

- [ ] **Step 2: 运行前端测试并确认缺少 SMTP 控件**

Run: `node --test tests/index_auth_ui.test.js`

Expected: 新测试失败。

- [ ] **Step 3: 扩展个人设置对话框**

在 BPM 配置卡下增加“发件邮箱（SMTP）”卡，字段为主机、端口、加密方式、账号、密码/授权码、发件人名称、发件地址。默认填入 `smtp.qiye.163.com`、`465`、`ssl`；状态只显示掩码和已配置标记。

保存后立即执行：

```javascript
smtpPassword.value = "";
await loadSmtpCredentialStatus();
showToast("发件邮箱配置已保存");
```

“测试连接”调用服务器接口并展示结果，不能在前端直接连接 SMTP。

- [ ] **Step 4: 运行个人设置测试**

Run: `node --test tests/index_auth_ui.test.js`

Expected: 全部通过。

- [ ] **Step 5: 提交个人 SMTP 配置界面**

```bash
git add index.html tests/index_auth_ui.test.js
git commit -m "feat: add smtp personal settings"
```

### Task 8: 实现邮件中心界面和交互

**Files:**
- Modify: `index.html`
- Create: `mail_ui_helpers.js`
- Create: `tests/index_mail_center.test.js`
- Modify: `server.py`

**Interfaces:**
- Consumes: Task 6 的全部 `/api/mail/*` 接口。
- Produces: 邮件一级导航、模板栏、编辑区、右侧名单/检查栏、预览对话框、发送记录。

- [ ] **Step 1: 写页面结构和纯函数测试**

```javascript
test('mail recipients exist only in the right panel', () => {
  assert.match(source, /id="mailRecipientPanel"/);
  assert.doesNotMatch(extractElement(source, 'mailComposeEditor'), /mail-recipient-chip/);
});

test('send action requires a browser confirmation', () => {
  assert.match(source, /window\.confirm\([^)]*发送/);
  assert.match(source, /confirmed:\s*true/);
});
```

`mail_ui_helpers.js` 测试模板变量提取、批次状态文案和名单统计，采用与 `auth_session_generation.js` 相同的浏览器/Node 双环境导出方式。

- [ ] **Step 2: 运行前端邮件测试并确认失败**

Run: `node --test tests/index_mail_center.test.js`

Expected: 失败，提示缺少邮件中心节点。

- [ ] **Step 3: 添加静态资源并实现确认版布局**

将 `/mail_ui_helpers.js` 加入 `STATIC_ASSETS`。在一级导航加入 `menuMail`，增加 `mailView`：左侧模板库、中间主题正文、右侧上传和发送检查。响应式窄屏时右栏移到编辑区下方，不隐藏关键发送控件。

- [ ] **Step 4: 实现模板、名单、草稿、预览和发送交互**

关键发送函数必须执行：

```javascript
async function submitMailBatch() {
  const validCount = mailState.recipients.length;
  if (!window.confirm(`确认逐封发送 ${validCount} 封邮件吗？`)) return;
  const response = await apiFetch("/api/mail/batches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      confirmed: true,
      subject: mailSubject.value,
      body: mailBody.value,
      recipients: mailState.recipients,
    }),
  });
  if (!response.ok) throw new Error(await responseError(response, "邮件任务创建失败"));
  await refreshMailBatches();
}
```

模板删除和上传名单替换同样使用二次确认。正文草稿使用服务器 API 防抖保存，不写入 `localStorage`。

- [ ] **Step 5: 运行邮件界面测试和 JavaScript 语法检查**

Run: `node --test tests/index_mail_center.test.js tests/index_auth_ui.test.js && node --check mail_ui_helpers.js`

Expected: 全部通过。

- [ ] **Step 6: 提交邮件中心界面**

```bash
git add index.html mail_ui_helpers.js server.py tests/index_mail_center.test.js
git commit -m "feat: build mail center workspace"
```

### Task 9: 全量回归、真实小批次验证和文档

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: 完整邮件中心。
- Produces: 可复现的配置、测试和真实验证说明。

- [ ] **Step 1: 更新 README**

记录个人设置中的 SMTP 字段、网易企业邮箱默认值、名单表头、模板变量、预览流程、最终确认和失败项重试。明确授权码不会回显，真实发送应先用两个受控邮箱测试。

- [ ] **Step 2: 运行 Python 全量测试**

Run: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v`

Expected: 全部通过。

- [ ] **Step 3: 运行 Node 全量测试和静态检查**

Run: `npm test && node --check mail_ui_helpers.js && git diff --check`

Expected: 全部通过且无空白错误。

- [ ] **Step 4: 启动本地服务并检查健康状态**

Run: `PHEI_HOST=0.0.0.0 PHEI_PORT=4175 .venv/bin/python -u server.py`

Run: `curl -fsS http://127.0.0.1:4175/api/health`

Expected: 返回 `{"ok": true}` 及当前时间。

- [ ] **Step 5: 在浏览器完成操作回归**

使用两个不同账号验证模板和 SMTP 配置互相不可见；分别完成新建模板、修改模板、删除确认、CSV/XLSX 上传、无效邮箱提示、个性化预览、取消发送和确认发送。

- [ ] **Step 6: 用两个受控测试邮箱真实发送**

先在个人设置中保存测试 SMTP 并通过“测试连接”，再上传两个自有测试邮箱。核对两封邮件分别到达、收件人栏只有各自地址、称呼正确、页面记录成功；随后故意使用一个无效目标地址，验证批次显示“部分失败”且只允许重试失败项。

- [ ] **Step 7: 提交文档和最终修正**

```bash
git add README.md
git commit -m "docs: document mail center workflow"
```
