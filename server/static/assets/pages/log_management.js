window.pageInits["log_management"] = async function () {
  bind("btn-log-export-create", "click", async () => {
    const targetType = document.getElementById("log-export-type").value;
    const configText = document.getElementById("log-export-config").value || "{}";
    const enabled = document.getElementById("log-export-enabled").checked;
    const logTypes = [];
    if (document.getElementById("log-export-type-health").checked) logTypes.push("health");
    if (document.getElementById("log-export-type-client").checked) logTypes.push("client_logs");
    if (document.getElementById("log-export-type-audit").checked) logTypes.push("audit");
    let config = {};
    try { config = JSON.parse(configText); } catch (err) { config = {}; }
    const res = await api("/admin/log-exports", { method: "POST", body: JSON.stringify({ target_type: targetType, config, enabled, log_types: logTypes }) });
    const data = await res.json();
    document.getElementById("log-export-list").textContent = JSON.stringify(data, null, 2);
    await loadLogExports();
  });
  bind("btn-log-export-refresh", "click", loadLogExports);
  bind("btn-log-export-delete", "click", async () => {
    const id = document.getElementById("log-export-delete-id").value;
    if (!id) return;
    const res = await api("/admin/log-exports/" + encodeURIComponent(id), { method: "DELETE" });
    const data = await res.json();
    document.getElementById("log-export-list").textContent = JSON.stringify(data, null, 2);
    await loadLogExports();
  });
  bind("btn-log-retention-save", "click", async () => {
    const maxDays = document.getElementById("log-retention-days").value;
    const maxBytes = document.getElementById("log-retention-bytes").value;
    const payload = { max_days: maxDays ? parseInt(maxDays, 10) : null, max_bytes: maxBytes ? parseInt(maxBytes, 10) : null };
    const res = await api("/admin/log-retention", { method: "POST", body: JSON.stringify(payload) });
    const data = await res.json();
    document.getElementById("log-retention-status").textContent = JSON.stringify(data, null, 2);
  });
  await loadLogExports();
  await loadLogRetention();
};

async function loadLogExports() {
  const res = await api("/admin/log-exports");
  const data = await res.json();
  document.getElementById("log-export-list").textContent = JSON.stringify(data, null, 2);
}

async function loadLogRetention() {
  const res = await api("/admin/log-retention");
  const data = await res.json();
  document.getElementById("log-retention-status").textContent = JSON.stringify(data, null, 2);
  if (data.max_days !== null && data.max_days !== undefined) document.getElementById("log-retention-days").value = data.max_days;
  if (data.max_bytes !== null && data.max_bytes !== undefined) document.getElementById("log-retention-bytes").value = data.max_bytes;
}
