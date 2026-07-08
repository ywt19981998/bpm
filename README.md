# PHEI Report Web

电子工业出版社选题策划报告生成与 BPM 辅助填报工具。

## 本地启动

```bash
npm install
npx playwright install chromium
python3 -m pip install -r requirements.txt
export DEEPSEEK_API_KEY="你的模型 API Key"
python3 -u server.py
```

打开：

```text
http://127.0.0.1:4174/index.html
```

也可以不设置 `DEEPSEEK_API_KEY`，在网页的模型配置里临时填写 API Key。

## 重要说明

- BPM 密码只在当次请求里使用，不写入仓库。
- 运行日志、导出文件、上传文件和 `node_modules` 已通过 `.gitignore` 排除。
- `skills/` 目录中包含本项目需要的申报表解析和 BPM 自动填报脚本，方便换电脑继续使用。
- `templates/planning-report-template.docx` 是导出策划报告时使用的 Word 模板。
