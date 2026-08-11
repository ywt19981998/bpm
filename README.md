# PHEI Report Web

电子工业出版社选题策划报告生成与 BPM 辅助填报工具，仅面向受信任的本机或局域网使用。

## 安装与安全配置

需要 Python 3、Node.js 和 npm。首次使用时，在项目根目录执行：

```bash
cp .env.example .env
python3 - <<'PY'
import base64, os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
python3 -m pip install -r requirements.txt
npm install
npx playwright install chromium
```

将第二条命令输出的随机值填入 `.env` 的 `APP_CREDENTIAL_KEY`；将 DeepSeek 服务端 API Key 填入 `DEEPSEEK_API_KEY`。`.env` 已被 Git 忽略，不应提交、发送或截图。建议限制本机文件权限：

```bash
chmod 600 .env
```

`APP_CREDENTIAL_KEY` 用于加密数据库中的 BPM 账号和密码，必须保存在受控的密码管理器或安全配置中。不要把它写入源代码、脚本、数据库或 Git。更换或丢失该值后，已保存的 BPM 凭据将无法解密；恢复原密钥，或由每位用户清除并重新保存自己的 BPM 配置。

## 启动与局域网访问

启动服务：

```bash
python3 -u server.py
```

`.env.example` 默认监听 `0.0.0.0:4175`，本机打开：

```text
http://127.0.0.1:4175/index.html
```

同一受信任局域网的设备可使用运行这台 Mac 的局域网 IP，例如：

```bash
ipconfig getifaddr en0
```

再打开 `http://<该 IP>:4175/index.html`。仅在受信任的内网中使用；本项目未提供公网部署、HTTPS 或管理员权限管理。若只允许本机访问，将 `.env` 中的 `PHEI_HOST` 改为 `127.0.0.1` 后重启服务。

## 注册与个人 BPM 配置

首次访问时，在“注册”页签填写账号、姓名、密码和确认密码；注册成功后会自动进入工作台。之后可用账号和密码登录，顶部会显示当前用户姓名，并可随时退出。

在顶部的 “BPM 配置” 入口或 BPM 工作区中，填写自己的 BPM 账号和密码并保存。BPM 地址由服务端 `BPM_URL` 统一配置，普通用户不能修改。已保存后页面只显示脱敏账号和“密码已保存”状态，密码不会回显；可以更新，或确认后清除。未保存配置时，BPM 队列操作会提示先完成配置。

BPM 凭据按用户隔离并以 `APP_CREDENTIAL_KEY` 加密保存。后端仅在当前用户发起的 BPM 任务进程内解密使用，不将明文写入任务记录或 API 响应。不要把 BPM 密码放进浏览器草稿、日志或仓库文件。

## 选题项目工作流

登录后默认进入“选题项目”。每个项目独立保存申报表、已确认策划报告、六段正文、评分、作译者状态、BPM 状态和导出的 DOCX。可以按选题名、作者或编辑搜索，也可以按状态筛选和归档。

正文和评分在停止输入约 700 毫秒后自动保存，页面顶部会显示“未保存”“正在保存”或“已保存”。同一项目在其他窗口被更新时，当前窗口会显示“版本冲突”；此时重新从项目列表打开项目，再继续编辑，避免覆盖较新的内容。

旧版浏览器草稿在登录后只提示迁移一次。只有服务端成功创建新项目后，旧草稿才会从浏览器删除；若迁移失败，原草稿仍保留。没有申报表的迁移项目会明确记录来源文件缺失。

进入 BPM 工作区前，系统会从服务端项目生成填报前检查表，列出字段内容、来源和状态。只有六段正文、评分、选题名称、策划编辑及 BPM 账号等必填项全部就绪，才允许加入选题填报队列。浏览器入队时只发送项目 ID，后端始终读取当前用户已保存的项目数据。

BPM 选题任务按五个已验证里程碑记录结果：`login_verified`、`topic_form_opened`、`topic_draft_saved`、`cost_estimate_saved`、`worklist_verified`。只有最后一次在工作列表回查到选题后才标记成功；失败任务仍保留已经完成的里程碑和运行目录，便于定位卡在哪一步。

## DeepSeek 服务端配置

所有用户共享服务端的 DeepSeek 配置；网页不提供模型 URL、模型名称或 API Key 输入。`.env.example` 给出默认值：

- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-v4-pro`
- `DEEPSEEK_FAST_MODEL=deepseek-v4-flash`

必须在 `.env` 中配置 `DEEPSEEK_API_KEY` 才能生成报告。未配置时，报告生成功能会显示服务暂不可用；请由维护者检查服务端环境，而不是让用户在网页中输入 Key。修改配置后重启服务生效。

## 数据备份与恢复

本地数据由两部分组成，必须作为一个整体备份：

- `data/app.db`：用户、会话、项目状态、任务历史和加密后的 BPM 凭据。
- `data/projects/`：各用户项目上传和生成的 DOCX 文件。

`data/` 已被 Git 忽略。为保证数据库记录与文件一致，备份前先停止服务，再复制整个目录：

```bash
mkdir -p backups
cp -R data "backups/data-$(date +%F-%H%M%S)"
```

也可以打成一个归档文件：

```bash
mkdir -p backups
tar -czf "backups/phei-data-$(date +%F-%H%M%S).tar.gz" data
```

不要在服务仍在写入时分别复制数据库和项目目录，否则可能出现数据库有文件记录但文件缺失的情况。恢复前必须停止服务，并先保留当前 `data/` 的回滚副本；随后整体恢复备份目录，再启动服务。恢复加密的 BPM 凭据还需要备份创建时的同一个 `APP_CREDENTIAL_KEY`。不要把数据备份和 `.env` 一起上传到 Git、邮件或共享网盘。

## 自动化验证

安装依赖后可运行完整本地测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -q
npm test
git diff --check
```

`skills/` 目录包含申报表解析和 BPM 自动填报脚本；`templates/planning-report-template.docx` 是导出策划报告使用的 Word 模板。请只在已确认的工作流中运行 BPM 自动化。
