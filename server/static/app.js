let token = localStorage.getItem("windsentinel_token");
let currentAgent = null;
let agentGroupFilter = "";
let agentTagFilter = "";
let agentSearch = "";
let agentOffset = 0;
let agentLimit = 200;
let lastBatchFailed = [];
let metaTimer = null;

function api(path, options = {}) {
  const headers = options.headers || {};
  const authToken = token || localStorage.getItem("windsentinel_token");
  if (authToken) headers["Authorization"] = "Bearer " + authToken;
  if (!headers["Content-Type"] && options.body) headers["Content-Type"] = "application/json";
  return fetch(path, { ...options, headers });
}

function bind(id, event, handler) {
  const el = document.getElementById(id);
  if (el) el.addEventListener(event, handler);
}

bind("btn-login", "click", login);
bind("btn-bind-mfa", "click", bindMfa);
bind("btn-verify-mfa", "click", verifyMfa);
bind("btn-change-pass", "click", changePassword);
bind("btn-load-agents", "click", loadAgents);
bind("agent-list", "change", selectAgent);
bind("btn-send-policy", "click", sendPolicy);
bind("btn-lock", "click", lockAgent);
bind("btn-unlock", "click", unlockAgent);
bind("btn-load-users", "click", loadUsers);
bind("btn-create-user", "click", createUser);
bind("btn-delete-user", "click", deleteUser);
bind("btn-load-audits", "click", loadAudits);
bind("btn-audit-chart", "click", loadAuditCharts);
bind("btn-load-rules", "click", loadRules);
bind("rule-list", "change", selectRule);
bind("btn-save-rule", "click", saveRule);
bind("btn-restore-rule", "click", restoreRule);
bind("btn-diff-rule", "click", diffRule);
bind("btn-copy-diff", "click", copyDiff);
bind("btn-rule-export", "click", exportRules);
bind("btn-rule-import", "click", importRules);
bind("btn-rule-import-preview", "click", previewImportRules);
bind("btn-run-query", "click", runQuery);
bind("btn-policy-group", "click", sendPolicyToGroup);
bind("btn-policy-tag", "click", sendPolicyToTag);
bind("btn-policy-retry", "click", retryPolicyBatch);
bind("btn-cfg-template", "click", loadConfigTemplate);
bind("btn-cfg-sign", "click", signConfigPreview);
bind("btn-cfg-download", "click", () => downloadConfig("config"));
bind("btn-cfg-package", "click", () => downloadConfig("zip"));
bind("btn-cfg-meta", "click", loadPackageMeta);
bind("btn-cfg-template-save", "click", saveConfigTemplate);
bind("btn-cfg-template-load", "click", loadSelectedTemplate);
bind("btn-cfg-template-delete", "click", deleteSelectedTemplate);
bind("btn-cfg-template-export", "click", exportTemplates);
bind("btn-cfg-template-import", "click", importTemplates);
bind("btn-cfg-template-versions", "click", loadTemplateVersions);
bind("btn-cfg-template-rollback", "click", rollbackTemplateVersion);
bind("btn-agent-filter", "click", applyAgentFilter);
bind("btn-agent-filter-reset", "click", resetAgentFilter);
bind("btn-agent-prev", "click", () => pageAgents(-1));
bind("btn-agent-next", "click", () => pageAgents(1));
bind("btn-agent-load", "click", loadAgentProfile);
bind("btn-agent-save", "click", saveAgentProfile);
bind("btn-group-create", "click", createGroup);
bind("btn-group-delete", "click", deleteGroup);
bind("btn-tag-create", "click", createTag);
bind("btn-tag-delete", "click", deleteTag);

function initDefaults() {
  const auditSince = document.getElementById("audit-since-date");
  const auditUntil = document.getElementById("audit-until-date");
  if (auditSince && auditUntil && !auditSince.value && !auditUntil.value) {
    const now = new Date();
    const since = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    auditSince.value = toLocalInput(since);
    auditUntil.value = toLocalInput(now);
  }
  const searchInput = document.getElementById("agent-search");
  if (searchInput) {
    searchInput.addEventListener("keydown", event => {
      if (event.key === "Enter") applyAgentFilter();
    });
  }
  const metaAuto = document.getElementById("cfg-meta-auto");
  if (metaAuto) {
    metaAuto.addEventListener("change", () => {
      if (metaAuto.checked) {
        startMetaAutoRefresh();
      } else {
        stopMetaAutoRefresh();
      }
    });
  }
}

function getConfigPayload() {
  const agentId = document.getElementById("cfg-agent-id")?.value || "";
  const serverUrl = document.getElementById("cfg-server-url")?.value || "";
  const sharedKey = document.getElementById("cfg-shared-key")?.value || "";
  return {
    agent_id: agentId || null,
    server_url: serverUrl,
    shared_key_b64: sharedKey
  };
}

async function loadConfigTemplate() {
  const res = await api("/admin/agent-config/template");
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    document.getElementById("cfg-meta").textContent = "";
    return;
  }
  const data = await res.json();
  const cfg = data.config || {};
  if (document.getElementById("cfg-agent-id")) document.getElementById("cfg-agent-id").value = cfg.agent_id || "";
  if (document.getElementById("cfg-server-url")) document.getElementById("cfg-server-url").value = cfg.server_url || "";
  if (document.getElementById("cfg-shared-key")) document.getElementById("cfg-shared-key").value = cfg.shared_key_b64 || "";
  document.getElementById("cfg-preview").textContent = JSON.stringify(data, null, 2);
  if (data.package) document.getElementById("cfg-meta").textContent = JSON.stringify(data.package, null, 2);
  await loadConfigTemplates();
}

async function signConfigPreview() {
  const payload = getConfigPayload();
  const res = await api("/admin/agent-config/sign", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    document.getElementById("cfg-meta").textContent = "";
    return;
  }
  const data = await res.json();
  document.getElementById("cfg-preview").textContent = JSON.stringify(data, null, 2);
  document.getElementById("cfg-meta").textContent = JSON.stringify(data.package || {}, null, 2);
}

async function downloadConfig(format) {
  const payload = getConfigPayload();
  const res = await api("/admin/agent-config/download?format=" + format, {
    method: "POST",
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    document.getElementById("cfg-meta").textContent = "";
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = format === "zip" ? "windsentinel-agent-package.zip" : "windsentinel-agent-config.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function readError(res) {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = await res.json();
    return JSON.stringify(data, null, 2);
  }
  return await res.text();
}

async function loadPackageMeta() {
  const res = await api("/admin/agent-config/meta");
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-meta").textContent = text;
    return;
  }
  const data = await res.json();
  document.getElementById("cfg-meta").textContent = JSON.stringify(data, null, 2);
}

async function loadConfigTemplates() {
  const res = await api("/admin/agent-config/templates");
  if (!res.ok) return;
  const data = await res.json();
  const select = document.getElementById("cfg-template-list");
  if (!select) return;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "选择模板";
  select.appendChild(empty);
  data.forEach(item => {
    const opt = document.createElement("option");
    opt.value = item.name;
    opt.textContent = item.name;
    select.appendChild(opt);
  });
}

async function saveConfigTemplate() {
  const name = document.getElementById("cfg-template-name")?.value || "";
  if (!name) return;
  const payload = { name, config: getConfigPayload() };
  const res = await api("/admin/agent-config/templates", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    return;
  }
  await loadConfigTemplates();
}

async function loadSelectedTemplate() {
  const name = document.getElementById("cfg-template-list")?.value || "";
  if (!name) return;
  const res = await api("/admin/agent-config/templates/" + encodeURIComponent(name));
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    return;
  }
  const data = await res.json();
  const cfg = data.config || {};
  if (document.getElementById("cfg-agent-id")) document.getElementById("cfg-agent-id").value = cfg.agent_id || "";
  if (document.getElementById("cfg-server-url")) document.getElementById("cfg-server-url").value = cfg.server_url || "";
  if (document.getElementById("cfg-shared-key")) document.getElementById("cfg-shared-key").value = cfg.shared_key_b64 || "";
  document.getElementById("cfg-template-name").value = data.name || "";
  document.getElementById("cfg-preview").textContent = JSON.stringify(data, null, 2);
}

async function deleteSelectedTemplate() {
  const name = document.getElementById("cfg-template-list")?.value || "";
  if (!name) return;
  const res = await api("/admin/agent-config/templates/" + encodeURIComponent(name), { method: "DELETE" });
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    return;
  }
  await loadConfigTemplates();
}

function startMetaAutoRefresh() {
  if (metaTimer) return;
  loadPackageMeta();
  metaTimer = setInterval(loadPackageMeta, 10000);
}

function stopMetaAutoRefresh() {
  if (metaTimer) {
    clearInterval(metaTimer);
    metaTimer = null;
  }
}

async function exportTemplates() {
  const res = await api("/admin/agent-config/templates/export");
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "windsentinel-agent-templates.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function importTemplates() {
  const fileInput = document.getElementById("cfg-template-import");
  const file = fileInput?.files?.[0];
  if (!file) return;
  const text = await file.text();
  let payload = null;
  try {
    payload = JSON.parse(text);
  } catch (err) {
    document.getElementById("cfg-preview").textContent = String(err);
    return;
  }
  const res = await api("/admin/agent-config/templates/import", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) {
    const errText = await readError(res);
    document.getElementById("cfg-preview").textContent = errText;
    return;
  }
  const data = await res.json();
  document.getElementById("cfg-preview").textContent = JSON.stringify(data, null, 2);
  await loadConfigTemplates();
}

async function loadTemplateVersions() {
  const name = document.getElementById("cfg-template-list")?.value || "";
  if (!name) return;
  const res = await api("/admin/agent-config/templates/" + encodeURIComponent(name) + "/versions");
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    return;
  }
  const data = await res.json();
  const select = document.getElementById("cfg-template-version-list");
  if (!select) return;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "选择版本";
  select.appendChild(empty);
  data.forEach(item => {
    const opt = document.createElement("option");
    opt.value = String(item.id);
    opt.textContent = item.name + "@" + item.id;
    select.appendChild(opt);
  });
}

async function rollbackTemplateVersion() {
  const name = document.getElementById("cfg-template-list")?.value || "";
  const versionId = document.getElementById("cfg-template-version-list")?.value || "";
  if (!name || !versionId) return;
  const res = await api("/admin/agent-config/templates/" + encodeURIComponent(name) + "/rollback/" + encodeURIComponent(versionId), {
    method: "POST"
  });
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("cfg-preview").textContent = text;
    return;
  }
  const data = await res.json();
  document.getElementById("cfg-preview").textContent = JSON.stringify(data, null, 2);
  await loadConfigTemplates();
  await loadTemplateVersions();
}

document.addEventListener("DOMContentLoaded", initDefaults);

async function login() {
  const username = document.getElementById("login-user").value;
  const password = document.getElementById("login-pass").value;
  const mfa = document.getElementById("login-mfa").value;
  const res = await fetch("/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, mfa: mfa || null })
  });
  if (!res.ok) {
    document.getElementById("login-status").textContent = await readError(res);
    return;
  }
  const data = await res.json();
  token = data.token;
  localStorage.setItem("windsentinel_token", data.token);
  localStorage.setItem("windsentinel_role", data.role || "");
  localStorage.setItem("windsentinel_mfa_bound", data.mfa_bound ? "1" : "0");
  localStorage.setItem("windsentinel_must_change", data.must_change ? "1" : "0");
  document.getElementById("login-status").textContent = JSON.stringify(data, null, 2);
  await loadAgents();
  await loadGroups();
  await loadTags();
  await loadConfigTemplates();
}

async function bindMfa() {
  const res = await api("/admin/bind_mfa", { method: "POST" });
  const data = await res.json();
  const qr = document.getElementById("mfa-qr");
  if (qr && data.qr_png_b64) {
    qr.src = "data:image/png;base64," + data.qr_png_b64;
    qr.style.width = "200px";
    qr.style.height = "200px";
    qr.style.background = "#ffffff";
    qr.style.padding = "8px";
    qr.style.borderRadius = "8px";
  }
  const secret = document.getElementById("mfa-secret");
  if (secret) secret.textContent = data.mfa_secret || "";
  const status = document.getElementById("mfa-status");
  if (status) status.textContent = "";
}

async function verifyMfa() {
  const code = document.getElementById("mfa-code")?.value || "";
  if (!code) return;
  const res = await api("/admin/verify_mfa", {
    method: "POST",
    body: JSON.stringify({ code })
  });
  const data = await res.json();
  const status = document.getElementById("mfa-status");
  if (res.ok) {
    if (status) status.textContent = JSON.stringify(data, null, 2);
    localStorage.setItem("windsentinel_mfa_bound", "1");
    if (typeof loadPage === "function") {
      await loadPage("personal_password");
    }
  } else {
    if (status) status.textContent = JSON.stringify(data, null, 2);
  }
}

async function changePassword() {
  const oldPassword = document.getElementById("old-pass").value;
  const newPassword = document.getElementById("new-pass").value;
  const mfa = document.getElementById("change-mfa").value;
  const res = await api("/admin/change_password", {
    method: "POST",
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword, mfa })
  });
  const data = await res.json();
  document.getElementById("login-status").textContent = JSON.stringify(data, null, 2);
  if (res.ok) {
    localStorage.setItem("windsentinel_must_change", "0");
    if (typeof loadPage === "function") {
      await loadPage("agents");
    }
  }
}

async function loadAgents() {
  const params = new URLSearchParams();
  if (agentGroupFilter) params.set("group_id", agentGroupFilter);
  if (agentTagFilter) params.set("tag_id", agentTagFilter);
  if (agentSearch) params.set("q", agentSearch);
  params.set("offset", String(agentOffset));
  params.set("limit", String(agentLimit));
  const res = await api("/admin/agents" + (params.toString() ? "?" + params.toString() : ""));
  const data = await res.json();
  const totalEl = document.getElementById("agent-total");
  if (totalEl) totalEl.textContent = "总数: " + (data.total ?? 0);
  const select = document.getElementById("agent-list");
  select.innerHTML = "";
  (data.items || []).forEach(item => {
    const opt = document.createElement("option");
    opt.value = item.agent_id;
    const name = item.display_name ? item.display_name : "未命名";
    const group = item.group_name ? item.group_name : "未分组";
    opt.textContent = item.agent_id + " (" + name + ", " + group + ")";
    select.appendChild(opt);
  });
  if ((data.items || []).length > 0) {
    currentAgent = select.value;
    await loadHealth();
    await loadAgentProfile();
    await loadClientControlState();
    await loadClientControlTasks();
  } else {
    currentAgent = null;
  }
}

async function selectAgent() {
  currentAgent = document.getElementById("agent-list").value;
  await loadHealth();
  await loadAgentProfile();
  await loadClientControlState();
  await loadClientControlTasks();
}

async function loadHealth() {
  if (!currentAgent) return;
  const res = await api("/admin/health/" + currentAgent);
  const data = await res.json();
  document.getElementById("agent-health").textContent = JSON.stringify(data, null, 2);
  const policyEl = document.getElementById("policy-json");
  if (policyEl) {
    policyEl.value = JSON.stringify({
      enabled_modules: ["process", "network", "health", "lock"],
      kill_pids: [],
      block_network_pids: [],
      block_all_network: false,
      lock: null,
      unlock: null,
    }, null, 2);
  }
}

async function loadGroups() {
  const res = await api("/admin/groups");
  const data = await res.json();
  const select = document.getElementById("agent-group");
  const policySelect = document.getElementById("policy-group");
  const filterSelect = document.getElementById("agent-filter-group");
  if (select) {
    select.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "未分组";
    select.appendChild(empty);
    data.forEach(item => {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.name;
      select.appendChild(opt);
    });
  }
  if (policySelect) {
    policySelect.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "选择分组";
    policySelect.appendChild(empty);
    data.forEach(item => {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.name;
      policySelect.appendChild(opt);
    });
  }
  if (filterSelect) {
    filterSelect.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "全部分组";
    filterSelect.appendChild(empty);
    data.forEach(item => {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.name;
      filterSelect.appendChild(opt);
    });
    filterSelect.value = agentGroupFilter;
  }
  const out = document.getElementById("group-list");
  if (out) out.textContent = JSON.stringify(data, null, 2);
}

async function loadTags() {
  const res = await api("/admin/tags");
  const data = await res.json();
  const policySelect = document.getElementById("policy-tag");
  const filterSelect = document.getElementById("agent-filter-tag");
  if (policySelect) {
    policySelect.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "选择标签";
    policySelect.appendChild(empty);
    data.forEach(item => {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.name;
      policySelect.appendChild(opt);
    });
  }
  if (filterSelect) {
    filterSelect.innerHTML = "";
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "全部标签";
    filterSelect.appendChild(empty);
    data.forEach(item => {
      const opt = document.createElement("option");
      opt.value = String(item.id);
      opt.textContent = item.name;
      filterSelect.appendChild(opt);
    });
    filterSelect.value = agentTagFilter;
  }
  const out = document.getElementById("tag-list");
  if (out) out.textContent = JSON.stringify(data, null, 2);
}

async function loadAgentProfile() {
  if (!currentAgent) return;
  const res = await api("/admin/agents/" + currentAgent);
  if (!res.ok) return;
  const data = await res.json();
  const display = document.getElementById("agent-display-name");
  const notes = document.getElementById("agent-notes");
  const group = document.getElementById("agent-group");
  const tags = document.getElementById("agent-tags");
  if (display) display.value = data.display_name || "";
  if (notes) notes.value = data.notes || "";
  if (group) group.value = data.group_id ? String(data.group_id) : "";
  if (tags) tags.value = (data.tags || []).join(",");
}

async function saveAgentProfile() {
  if (!currentAgent) return;
  const display = document.getElementById("agent-display-name")?.value || "";
  const notes = document.getElementById("agent-notes")?.value || "";
  const groupValue = document.getElementById("agent-group")?.value || "";
  const tagValue = document.getElementById("agent-tags")?.value || "";
  const groupId = groupValue ? parseInt(groupValue, 10) : null;
  await api("/admin/agents/" + currentAgent + "/profile", {
    method: "POST",
    body: JSON.stringify({ display_name: display, notes, group_id: groupId })
  });
  await api("/admin/agents/" + currentAgent + "/tags", {
    method: "POST",
    body: JSON.stringify({ tags: parseTags(tagValue) })
  });
  await loadGroups();
  await loadTags();
  await loadAgents();
  await loadAgentProfile();
}

async function createGroup() {
  const name = document.getElementById("group-name")?.value || "";
  const desc = document.getElementById("group-desc")?.value || "";
  if (!name) return;
  await api("/admin/groups", { method: "POST", body: JSON.stringify({ name, description: desc }) });
  document.getElementById("group-name").value = "";
  document.getElementById("group-desc").value = "";
  await loadGroups();
}

async function deleteGroup() {
  const value = document.getElementById("group-delete-id")?.value || "";
  if (!value) return;
  await api("/admin/groups/" + value, { method: "DELETE" });
  document.getElementById("group-delete-id").value = "";
  await loadGroups();
  await loadAgents();
  await loadAgentProfile();
}

async function createTag() {
  const name = document.getElementById("tag-name")?.value || "";
  if (!name) return;
  await api("/admin/tags", { method: "POST", body: JSON.stringify({ name }) });
  document.getElementById("tag-name").value = "";
  await loadTags();
}

async function deleteTag() {
  const value = document.getElementById("tag-delete-id")?.value || "";
  if (!value) return;
  await api("/admin/tags/" + value, { method: "DELETE" });
  document.getElementById("tag-delete-id").value = "";
  await loadTags();
  await loadAgentProfile();
}

function parseTags(value) {
  return value
    .split(",")
    .map(item => item.trim())
    .filter(Boolean);
}

async function sendPolicy() {
  if (!currentAgent) return;
  const payload = JSON.parse(document.getElementById("policy-json").value);
  const res = await api("/admin/policy/" + currentAgent, { method: "POST", body: JSON.stringify(payload) });
  const data = await res.json();
  document.getElementById("policy-status").textContent = JSON.stringify(data, null, 2);
}

async function sendPolicyToGroup() {
  const groupId = document.getElementById("policy-group")?.value || "";
  if (!groupId) return;
  const previewRes = await api("/admin/agents?group_id=" + groupId + "&offset=0&limit=100000");
  const previewData = await previewRes.json();
  if (!previewData.items?.length) {
    document.getElementById("policy-status").textContent = JSON.stringify({ status: "empty", count: 0 }, null, 2);
    document.getElementById("policy-batch-result").textContent = "";
    return;
  }
  if (!confirm("将向 " + previewData.items.length + " 个 agent 下发策略，是否继续？")) return;
  const payload = JSON.parse(document.getElementById("policy-json").value);
  const res = await api("/admin/policy/group/" + groupId, { method: "POST", body: JSON.stringify(payload) });
  const data = await res.json();
  document.getElementById("policy-status").textContent = JSON.stringify(data, null, 2);
  lastBatchFailed = data.failed || [];
  document.getElementById("policy-batch-result").textContent = JSON.stringify({ ok: data.ok || [], failed: data.failed || [] }, null, 2);
}

async function sendPolicyToTag() {
  const tagId = document.getElementById("policy-tag")?.value || "";
  if (!tagId) return;
  const previewRes = await api("/admin/agents?tag_id=" + tagId + "&offset=0&limit=100000");
  const previewData = await previewRes.json();
  if (!previewData.items?.length) {
    document.getElementById("policy-status").textContent = JSON.stringify({ status: "empty", count: 0 }, null, 2);
    document.getElementById("policy-batch-result").textContent = "";
    return;
  }
  if (!confirm("将向 " + previewData.items.length + " 个 agent 下发策略，是否继续？")) return;
  const payload = JSON.parse(document.getElementById("policy-json").value);
  const res = await api("/admin/policy/tag/" + tagId, { method: "POST", body: JSON.stringify(payload) });
  const data = await res.json();
  document.getElementById("policy-status").textContent = JSON.stringify(data, null, 2);
  lastBatchFailed = data.failed || [];
  document.getElementById("policy-batch-result").textContent = JSON.stringify({ ok: data.ok || [], failed: data.failed || [] }, null, 2);
}

async function retryPolicyBatch() {
  if (!lastBatchFailed.length) return;
  const retryIds = lastBatchFailed.map(item => (typeof item === "string" ? item : item.agent_id)).filter(Boolean);
  if (!retryIds.length) return;
  const payload = JSON.parse(document.getElementById("policy-json").value);
  const res = await api("/admin/policy/batch", {
    method: "POST",
    body: JSON.stringify({ agent_ids: retryIds, policy: payload })
  });
  const data = await res.json();
  lastBatchFailed = data.failed || [];
  document.getElementById("policy-status").textContent = JSON.stringify(data, null, 2);
  document.getElementById("policy-batch-result").textContent = JSON.stringify({ ok: data.ok || [], failed: data.failed || [] }, null, 2);
}

function applyAgentFilter() {
  agentSearch = document.getElementById("agent-search")?.value || "";
  agentGroupFilter = document.getElementById("agent-filter-group")?.value || "";
  agentTagFilter = document.getElementById("agent-filter-tag")?.value || "";
  agentOffset = parseInt(document.getElementById("agent-offset")?.value || "0", 10);
  agentLimit = parseInt(document.getElementById("agent-limit")?.value || "200", 10);
  loadAgents();
}

function resetAgentFilter() {
  agentGroupFilter = "";
  agentTagFilter = "";
  agentSearch = "";
  agentOffset = 0;
  agentLimit = 200;
  const groupSelect = document.getElementById("agent-filter-group");
  const tagSelect = document.getElementById("agent-filter-tag");
  const searchInput = document.getElementById("agent-search");
  const offsetInput = document.getElementById("agent-offset");
  const limitInput = document.getElementById("agent-limit");
  if (groupSelect) groupSelect.value = "";
  if (tagSelect) tagSelect.value = "";
  if (searchInput) searchInput.value = "";
  if (offsetInput) offsetInput.value = "0";
  if (limitInput) limitInput.value = "200";
  loadAgents();
}

function pageAgents(direction) {
  const offsetInput = document.getElementById("agent-offset");
  const limitInput = document.getElementById("agent-limit");
  const offset = parseInt(offsetInput?.value || "0", 10);
  const limit = parseInt(limitInput?.value || "200", 10);
  const next = Math.max(0, offset + direction * limit);
  if (offsetInput) offsetInput.value = String(next);
  agentOffset = next;
  agentLimit = limit;
  loadAgents();
}

async function lockAgent() {
  if (!currentAgent) return;
  const res = await api("/admin/policy/" + currentAgent + "/lock", { method: "POST" });
  const data = await res.json();
  document.getElementById("policy-status").textContent = JSON.stringify(data, null, 2);
}

async function unlockAgent() {
  if (!currentAgent) return;
  const res = await api("/admin/policy/" + currentAgent + "/unlock", { method: "POST" });
  const data = await res.json();
  document.getElementById("policy-status").textContent = JSON.stringify(data, null, 2);
}

function getClientControlContext() {
  const statusEl = document.getElementById("control-task-status");
  const metaEl = document.getElementById("control-offline-meta");
  const codeEl = document.getElementById("control-offline-code");
  const taskEl = document.getElementById("control-task-list");
  return { statusEl, metaEl, codeEl, taskEl };
}

function setClientControlStatus(value) {
  const { statusEl } = getClientControlContext();
  if (statusEl) statusEl.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function loadClientControlState() {
  const { metaEl, codeEl } = getClientControlContext();
  if (!currentAgent) {
    if (metaEl) metaEl.textContent = "请先选择 Agent";
    if (codeEl) codeEl.textContent = "";
    return;
  }
  const res = await api("/admin/agents/" + currentAgent + "/control/offline-code");
  if (!res.ok) {
    const text = await readError(res);
    if (metaEl) metaEl.textContent = text;
    if (codeEl) codeEl.textContent = "";
    return;
  }
  const data = await res.json();
  if (metaEl) metaEl.textContent = JSON.stringify(data, null, 2);
  if (codeEl) codeEl.textContent = "";
}

async function loadClientControlTasks() {
  const { taskEl } = getClientControlContext();
  if (!currentAgent) {
    if (taskEl) taskEl.textContent = "请先选择 Agent";
    return;
  }
  const res = await api("/admin/agents/" + currentAgent + "/control/tasks");
  if (!res.ok) {
    const text = await readError(res);
    if (taskEl) taskEl.textContent = text;
    return;
  }
  const data = await res.json();
  if (taskEl) taskEl.textContent = JSON.stringify(data, null, 2);
}

async function rotateOfflineAuthorizationCode() {
  const { codeEl } = getClientControlContext();
  if (!currentAgent) {
    setClientControlStatus("请先选择 Agent");
    return;
  }
  const mfaCode = document.getElementById("control-mfa-code")?.value || "";
  const reason = document.getElementById("control-reason")?.value || "";
  const res = await api("/admin/agents/" + currentAgent + "/control/offline-code/rotate", {
    method: "POST",
    body: JSON.stringify({ mfa_code: mfaCode, reason: reason || null })
  });
  if (!res.ok) {
    setClientControlStatus(await readError(res));
    if (codeEl) codeEl.textContent = "";
    return;
  }
  const data = await res.json();
  if (codeEl) codeEl.textContent = JSON.stringify({
    agent_id: data.agent_id,
    offline_code: data.offline_code,
    code_version: data.code_version,
    correlation_id: data.correlation_id
  }, null, 2);
  setClientControlStatus({ status: "ok", action: "offline_code_rotated", correlation_id: data.correlation_id });
  await loadClientControlState();
}

async function createClientControlTask(taskType) {
  if (!currentAgent) {
    setClientControlStatus("请先选择 Agent");
    return;
  }
  const mfaCode = document.getElementById("control-mfa-code")?.value || "";
  const reason = document.getElementById("control-reason")?.value || "";
  const res = await api("/admin/agents/" + currentAgent + "/control/task", {
    method: "POST",
    body: JSON.stringify({ task_type: taskType, mfa_code: mfaCode, reason: reason || null })
  });
  if (!res.ok) {
    setClientControlStatus(await readError(res));
    return;
  }
  const data = await res.json();
  setClientControlStatus(data);
  await loadClientControlTasks();
}

async function runQuery() {
  const query = document.getElementById("sql-query").value;
  const res = await api("/admin/logs/query", { method: "POST", body: JSON.stringify({ query }) });
  const data = await res.json();
  document.getElementById("query-result").textContent = JSON.stringify(data, null, 2);
}

async function loadUsers() {
  const res = await api("/admin/users");
  const data = await res.json();
  document.getElementById("user-list").textContent = JSON.stringify(data, null, 2);
}

async function createUser() {
  const username = document.getElementById("new-user").value;
  const password = document.getElementById("new-pass").value;
  const role = document.getElementById("new-role").value;
  const res = await api("/admin/users", { method: "POST", body: JSON.stringify({ username, password, role }) });
  const data = await res.json();
  document.getElementById("user-list").textContent = JSON.stringify(data, null, 2);
  await loadUsers();
}

async function deleteUser() {
  const username = document.getElementById("delete-user").value;
  const res = await api("/admin/users/" + username, { method: "DELETE" });
  const data = await res.json();
  document.getElementById("user-list").textContent = JSON.stringify(data, null, 2);
  await loadUsers();
}

async function loadAudits() {
  const limit = document.getElementById("audit-limit").value || "200";
  const username = document.getElementById("audit-username").value;
  const action = document.getElementById("audit-action").value;
  const since = getEpochFromInput("audit-since-date");
  const until = getEpochFromInput("audit-until-date");
  if (!validateRange(since, until)) return;
  const params = new URLSearchParams({ limit });
  if (username) params.set("username", username);
  if (action) params.set("action", action);
  if (since) params.set("since", String(since));
  if (until) params.set("until", String(until));
  const res = await api("/admin/audits?" + params.toString());
  const data = await res.json();
  document.getElementById("audit-list").textContent = JSON.stringify(data, null, 2);
  renderAuditTable(data);
}

function formatAuditTs(ts) {
  if (!ts) return "";
  const date = new Date(ts * 1000);
  return date.toISOString().replace("T", " ").replace("Z", "");
}

function renderAuditTable(items) {
  const container = document.getElementById("audit-table");
  if (!container) return;
  if (!Array.isArray(items) || items.length === 0) {
    container.textContent = "";
    return;
  }
  const header = ["时间", "用户", "角色", "动作", "结果", "认证", "API端点", "IP", "UserAgent", "方法", "路径", "Referer", "Query", "目标", "API"];
  const rows = items.map(item => [
    formatAuditTs(item.ts),
    item.username || "",
    item.role || "",
    item.action || "",
    item.result || "",
    item.auth_type || "",
    item.api_endpoint_id || "",
    item.ip || "",
    item.user_agent || "",
    item.method || "",
    item.path || "",
    item.referer || "",
    item.query || "",
    item.target || "",
    item.via_api ? "1" : "0",
  ]);
  container.textContent = "";
  const table = document.createElement("table");
  table.style.width = "100%";
  table.style.borderCollapse = "collapse";
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  header.forEach(text => {
    const th = document.createElement("th");
    th.style.border = "1px solid #334155";
    th.style.padding = "6px";
    th.style.textAlign = "left";
    th.textContent = text;
    headRow.appendChild(th);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  rows.forEach(cols => {
    const tr = document.createElement("tr");
    cols.forEach(text => {
      const td = document.createElement("td");
      td.style.border = "1px solid #334155";
      td.style.padding = "6px";
      td.style.verticalAlign = "top";
      td.textContent = String(text);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
}

async function loadAuditCharts() {
  const username = document.getElementById("audit-username").value;
  const action = document.getElementById("audit-action").value;
  const since = getEpochFromInput("audit-since-date");
  const until = getEpochFromInput("audit-until-date");
  if (!validateRange(since, until)) return;
  const bucket = document.getElementById("audit-bucket").value;
  const params = new URLSearchParams({ bucket });
  if (username) params.set("username", username);
  if (action) params.set("action", action);
  if (since) params.set("since", String(since));
  if (until) params.set("until", String(until));
  const res = await api("/admin/audits/stats?" + params.toString());
  const data = await res.json();
  drawBarChart("audit-actions", "tooltip-actions", data.actions.map(item => item.action), data.actions.map(item => item.count));
  drawLineChart("audit-series", "tooltip-series", data.series.map(item => item.bucket), data.series.map(item => item.count));
}

let rulesCache = [];
let ruleVersionsCache = [];
async function loadRules() {
  const res = await api("/admin/rules");
  const data = await res.json();
  rulesCache = data || [];
  const select = document.getElementById("rule-list");
  select.innerHTML = "";
  rulesCache.forEach(item => {
    const opt = document.createElement("option");
    opt.value = item.name;
    opt.textContent = item.name;
    select.appendChild(opt);
  });
  if (rulesCache.length > 0) {
    select.value = rulesCache[0].name;
    await selectRule();
  }
}

async function selectRule() {
  const name = document.getElementById("rule-list").value;
  const rule = rulesCache.find(r => r.name === name);
  if (rule) {
    document.getElementById("rule-name").value = rule.name;
    document.getElementById("rule-content").value = rule.content;
  }
  const res = await api("/admin/rules/" + encodeURIComponent(name) + "/versions");
  const versions = await res.json();
  ruleVersionsCache = versions || [];
  const left = document.getElementById("rule-versions-left");
  const right = document.getElementById("rule-versions-right");
  left.innerHTML = "";
  right.innerHTML = "";
  const currentOptLeft = document.createElement("option");
  currentOptLeft.value = "current";
  currentOptLeft.textContent = "current";
  left.appendChild(currentOptLeft);
  const currentOptRight = document.createElement("option");
  currentOptRight.value = "current";
  currentOptRight.textContent = "current";
  right.appendChild(currentOptRight);
  ruleVersionsCache.forEach(item => {
    const optLeft = document.createElement("option");
    optLeft.value = item.version;
    optLeft.textContent = item.version;
    left.appendChild(optLeft);
    const optRight = document.createElement("option");
    optRight.value = item.version;
    optRight.textContent = item.version;
    right.appendChild(optRight);
  });
}

async function saveRule() {
  const name = document.getElementById("rule-name").value;
  const content = document.getElementById("rule-content").value;
  const res = await api("/admin/rules", { method: "POST", body: JSON.stringify({ name, content }) });
  const data = await res.json();
  document.getElementById("rule-status").textContent = JSON.stringify(data, null, 2);
  await loadRules();
}

async function exportRules() {
  const names = document.getElementById("rule-export-filter")?.value || "";
  const params = names ? "?names=" + encodeURIComponent(names) : "";
  const res = await api("/admin/rules/export" + params);
  if (!res.ok) {
    const text = await readError(res);
    document.getElementById("rule-status").textContent = text;
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "windsentinel-rules.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function importRules() {
  const fileInput = document.getElementById("rule-import-file");
  const file = fileInput?.files?.[0];
  if (!file) return;
  const text = await file.text();
  let payload = null;
  try {
    payload = JSON.parse(text);
  } catch (err) {
    document.getElementById("rule-status").textContent = String(err);
    return;
  }
  const mode = document.getElementById("rule-import-mode")?.value || "overwrite";
  const res = await api("/admin/rules/import?mode=" + encodeURIComponent(mode), { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) {
    const errText = await readError(res);
    document.getElementById("rule-status").textContent = errText;
    return;
  }
  const data = await res.json();
  document.getElementById("rule-status").textContent = JSON.stringify(data, null, 2);
  await loadRules();
}

async function previewImportRules() {
  const fileInput = document.getElementById("rule-import-file");
  const file = fileInput?.files?.[0];
  if (!file) return;
  const text = await file.text();
  let payload = null;
  try {
    payload = JSON.parse(text);
  } catch (err) {
    document.getElementById("rule-status").textContent = String(err);
    return;
  }
  const res = await api("/admin/rules/import/preview", { method: "POST", body: JSON.stringify(payload) });
  if (!res.ok) {
    const errText = await readError(res);
    document.getElementById("rule-status").textContent = errText;
    return;
  }
  const data = await res.json();
  document.getElementById("rule-status").textContent = JSON.stringify(data, null, 2);
}

async function restoreRule() {
  const name = document.getElementById("rule-list").value;
  const version = document.getElementById("rule-versions-left").value;
  if (!name || !version || version === "current") return;
  const res = await api("/admin/rules/" + encodeURIComponent(name) + "/restore?version=" + encodeURIComponent(version), { method: "POST" });
  const data = await res.json();
  document.getElementById("rule-status").textContent = JSON.stringify(data, null, 2);
  await loadRules();
}

async function diffRule() {
  const name = document.getElementById("rule-list").value;
  const left = document.getElementById("rule-versions-left").value || "current";
  const right = document.getElementById("rule-versions-right").value || "current";
  if (!name) return;
  const res = await api("/admin/rules/" + encodeURIComponent(name) + "/diff?left=" + encodeURIComponent(left) + "&right=" + encodeURIComponent(right));
  const data = await res.json();
  renderDiff(document.getElementById("rule-diff"), data.diff || "");
}

function drawBarChart(canvasId, tooltipId, labels, values) {
  const canvas = document.getElementById(canvasId);
  const tooltip = document.getElementById(tooltipId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!values.length) return;
  const max = Math.max(...values);
  const padding = 30;
  const innerW = canvas.width - padding * 2;
  const innerH = canvas.height - padding * 2;
  const barWidth = innerW / values.length;
  ctx.strokeStyle = "#1f2937";
  ctx.beginPath();
  ctx.moveTo(padding, padding);
  ctx.lineTo(padding, canvas.height - padding);
  ctx.lineTo(canvas.width - padding, canvas.height - padding);
  ctx.stroke();
  ctx.fillStyle = "#94a3b8";
  ctx.font = "10px Arial";
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const y = canvas.height - padding - (innerH * i) / ticks;
    const val = Math.round((max * i) / ticks);
    ctx.fillText(formatNumber(val), 4, y + 3);
    ctx.strokeStyle = "#1e293b";
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(canvas.width - padding, y);
    ctx.stroke();
  }
  values.forEach((v, i) => {
    const h = (v / max) * innerH;
    ctx.fillStyle = "#38bdf8";
    const x = padding + i * barWidth + 4;
    const y = canvas.height - padding - h;
    const w = Math.max(2, barWidth - 8);
    ctx.fillRect(x, y, w, h);
  });
  const labelEvery = Math.max(1, Math.floor(values.length / 6));
  labels.forEach((label, i) => {
    if (i % labelEvery !== 0) return;
    const x = padding + i * barWidth + 4;
    ctx.fillStyle = "#94a3b8";
    ctx.save();
    ctx.translate(x, canvas.height - 10);
    ctx.rotate(-0.35);
    ctx.fillText(formatBucketLabel(label), 0, 0);
    ctx.restore();
  });
  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left - padding;
    const idx = Math.floor(x / barWidth);
    if (idx >= 0 && idx < labels.length) {
      tooltip.style.display = "block";
      tooltip.style.left = Math.min(rect.width - 120, Math.max(10, e.clientX - rect.left + 10)) + "px";
      tooltip.style.top = Math.max(10, e.clientY - rect.top - 30) + "px";
      tooltip.textContent = formatBucketLabel(labels[idx]) + ": " + formatNumber(values[idx]);
    } else {
      tooltip.style.display = "none";
    }
  };
  canvas.onmouseleave = () => { tooltip.style.display = "none"; };
}

function drawLineChart(canvasId, tooltipId, labels, values) {
  const canvas = document.getElementById(canvasId);
  const tooltip = document.getElementById(tooltipId);
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (values.length < 2) return;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = Math.max(1, max - min);
  const padding = 30;
  const innerW = canvas.width - padding * 2;
  const innerH = canvas.height - padding * 2;
  const step = innerW / (values.length - 1);
  ctx.strokeStyle = "#1f2937";
  ctx.beginPath();
  ctx.moveTo(padding, padding);
  ctx.lineTo(padding, canvas.height - padding);
  ctx.lineTo(canvas.width - padding, canvas.height - padding);
  ctx.stroke();
  ctx.fillStyle = "#94a3b8";
  ctx.font = "10px Arial";
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const y = canvas.height - padding - (innerH * i) / ticks;
    const val = Math.round(min + (range * i) / ticks);
    ctx.fillText(formatNumber(val), 4, y + 3);
    ctx.strokeStyle = "#1e293b";
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(canvas.width - padding, y);
    ctx.stroke();
  }
  ctx.strokeStyle = "#22c55e";
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = padding + i * step;
    const y = canvas.height - padding - ((v - min) / range) * innerH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  const labelEvery = Math.max(1, Math.floor(values.length / 6));
  labels.forEach((label, i) => {
    if (i % labelEvery !== 0) return;
    const x = padding + i * step;
    ctx.fillStyle = "#94a3b8";
    ctx.save();
    ctx.translate(x, canvas.height - 10);
    ctx.rotate(-0.35);
    ctx.fillText(formatBucketLabel(label), 0, 0);
    ctx.restore();
  });
  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left - padding;
    const idx = Math.round(x / step);
    if (idx >= 0 && idx < labels.length) {
      const y = values[idx];
      tooltip.style.display = "block";
      tooltip.style.left = Math.min(rect.width - 120, Math.max(10, e.clientX - rect.left + 10)) + "px";
      tooltip.style.top = Math.max(10, e.clientY - rect.top - 30) + "px";
      tooltip.textContent = formatBucketLabel(labels[idx]) + ": " + formatNumber(y);
    } else {
      tooltip.style.display = "none";
    }
  };
  canvas.onmouseleave = () => { tooltip.style.display = "none"; };
}

function renderDiff(container, diffText) {
  container.innerHTML = "";
  const lines = diffText.split("\n");
  lines.forEach(line => {
    const div = document.createElement("div");
    div.className = "diff-line";
    if (line.startsWith("+") && !line.startsWith("+++")) div.classList.add("diff-added");
    else if (line.startsWith("-") && !line.startsWith("---")) div.classList.add("diff-removed");
    else if (line.startsWith("@@") || line.startsWith("+++ ") || line.startsWith("--- ")) div.classList.add("diff-meta");
    div.textContent = line;
    div.addEventListener("click", async () => {
      await copyText(line);
      div.classList.add("diff-copied");
      setTimeout(() => div.classList.remove("diff-copied"), 600);
    });
    container.appendChild(div);
  });
}

function formatBucketLabel(label) {
  const text = String(label);
  if (text.includes(" ")) {
    const parts = text.split(" ");
    return parts[0].slice(5) + " " + parts[1];
  }
  return text.slice(5);
}

async function copyDiff() {
  const diff = document.getElementById("rule-diff");
  if (!diff) return;
  await copyText(diff.innerText || "");
  const btn = document.getElementById("btn-copy-diff");
  if (btn) {
    const prev = btn.textContent;
    btn.textContent = "已复制";
    btn.classList.add("btn-pulse");
    setTimeout(() => {
      btn.classList.remove("btn-pulse");
      btn.textContent = prev;
    }, 800);
  }
  showToast("diff-toast");
}

function formatNumber(value) {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + "M";
  if (value >= 1000) return (value / 1000).toFixed(1) + "K";
  return String(value);
}

function toLocalInput(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return (
    date.getFullYear() +
    "-" +
    pad(date.getMonth() + 1) +
    "-" +
    pad(date.getDate()) +
    "T" +
    pad(date.getHours()) +
    ":" +
    pad(date.getMinutes())
  );
}

function getEpochFromInput(id) {
  const value = document.getElementById(id)?.value;
  if (!value) return null;
  const ms = new Date(value).getTime();
  if (Number.isNaN(ms)) return null;
  return Math.floor(ms / 1000);
}

function validateRange(since, until) {
  if (since && until && since > until) {
    alert("时间范围不合法");
    return false;
  }
  return true;
}

function showToast(id) {
  const toast = document.getElementById(id);
  if (!toast) return;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 1200);
}

async function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  document.body.removeChild(area);
}

async function loadApiEndpoints() {
  const res = await api("/admin/api-endpoints");
  const data = await res.json();
  const el = document.getElementById("api-endpoint-list");
  if (el) el.textContent = JSON.stringify(data, null, 2);
}

async function createApiEndpoint() {
  const name = document.getElementById("api-endpoint-name").value;
  const alias = document.getElementById("api-endpoint-alias").value;
  const role = document.getElementById("api-endpoint-role").value;
  const functionsText = document.getElementById("api-endpoint-functions").value;
  const functions = functionsText.split(",").map(v => v.trim()).filter(Boolean);
  const res = await api("/admin/api-endpoints", {
    method: "POST",
    body: JSON.stringify({ name, alias: alias || null, role, functions })
  });
  const data = await res.json();
  const el = document.getElementById("api-endpoint-key");
  if (el) el.textContent = JSON.stringify(data, null, 2);
  await loadApiEndpoints();
}

async function deleteApiEndpoint() {
  const id = document.getElementById("api-endpoint-delete-id").value;
  if (!id) return;
  const res = await api("/admin/api-endpoints/" + encodeURIComponent(id), { method: "DELETE" });
  const data = await res.json();
  const el = document.getElementById("api-endpoint-list");
  if (el) el.textContent = JSON.stringify(data, null, 2);
  await loadApiEndpoints();
}
