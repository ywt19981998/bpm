# Task 8 Report: Server-Controlled DeepSeek

## Completed

- Moved DeepSeek base URL, API key, Pro model, and Flash model configuration to server environment variables.
- Routed complete report generation through `deepseek-v4-pro`; kept a server-only Flash wrapper for future narrow structured tasks.
- Ignored multipart `model`, `modelUrl`, and `apiKey` values.
- Removed model controls, generation request fields, legacy configuration reads/writes, and retained one-time legacy localStorage cleanup after workspace initialization.
- Added `.env.example` with placeholders only.
- Returned a generic 503 configuration error when the server key is absent and prevented client-supplied keys from appearing in the response or runtime log.

## TDD Evidence

- RED: `ServerModelConfigTests` failed while the default model was Flash, missing-key errors directed users to enter a key, and the UI still had model controls.
- GREEN: targeted model and UI tests pass after server routing and frontend cleanup.

## Verification

- `/Users/xiewentao/.venvs/phei-report-web/bin/python -m unittest tests.test_server_auth tests.test_app_storage -v`
- `npm test`
