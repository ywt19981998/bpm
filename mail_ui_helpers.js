(function exposeMailUiHelpers(root, factory) {
  const api = factory();
  root.MailUiHelpers = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createMailUiHelpers() {
  function extractTemplateVariables(text) {
    const variables = [];
    const seen = new Set();
    const pattern = /{{\s*([^{}]+?)\s*}}/g;
    let match = pattern.exec(String(text || ""));
    while (match) {
      const name = match[1].trim();
      if (name && !seen.has(name)) {
        seen.add(name);
        variables.push(name);
      }
      match = pattern.exec(String(text || ""));
    }
    return variables;
  }

  function getMailBatchStatus(status) {
    const statuses = {
      queued: { label: "排队中", tone: "neutral", terminal: false },
      running: { label: "发送中", tone: "active", terminal: false },
      succeeded: { label: "已完成", tone: "success", terminal: true },
      partial_failed: { label: "部分失败", tone: "warning", terminal: true },
      failed: { label: "失败", tone: "danger", terminal: true }
    };
    return statuses[status] || { label: "状态未知", tone: "neutral", terminal: true };
  }

  function summarizeRecipients(valid = [], invalid = [], duplicates = 0) {
    const validCount = Array.isArray(valid) ? valid.length : 0;
    const invalidCount = Array.isArray(invalid) ? invalid.length : 0;
    const duplicateCount = Math.max(0, Number(duplicates) || 0);
    return {
      validCount,
      invalidCount,
      duplicateCount,
      totalCount: validCount + invalidCount + duplicateCount,
      canSend: validCount > 0
    };
  }

  function createIdempotencyKey(prefix = "mail", randomValue) {
    const safePrefix = String(prefix || "mail").replace(/[^A-Za-z0-9._:-]/g, "-") || "mail";
    let seed = randomValue;
    if (!seed && typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      seed = crypto.randomUUID();
    }
    if (!seed) seed = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    let key = `${safePrefix}:${String(seed).replace(/[^A-Za-z0-9._:-]/g, "-")}`;
    if (!/^[A-Za-z0-9]/.test(key)) key = `m${key}`;
    if (key.length < 8) key = `${key}:request`;
    return key.slice(0, 128);
  }

  return {
    extractTemplateVariables,
    getMailBatchStatus,
    summarizeRecipients,
    createIdempotencyKey
  };
});
