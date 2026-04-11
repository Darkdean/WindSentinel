window.pageInits["login_blacklist"] = async function () {
  bind("btn-login-blacklist-refresh", "click", loadLoginBlacklist);
  bind("btn-login-blacklist-save", "click", saveLoginBlacklist);
  await loadLoginBlacklist();
};

async function loadLoginBlacklist() {
  const res = await api("/admin/login-blacklist");
  const data = await res.json();
  const ips = document.getElementById("login-blacklist-ips");
  const devices = document.getElementById("login-blacklist-devices");
  const ua = document.getElementById("login-blacklist-ua");
  const browsers = document.getElementById("login-blacklist-browsers");
  const os = document.getElementById("login-blacklist-os");
  if (ips) ips.value = (data.ip_list || []).join("\n");
  if (devices) devices.value = (data.device_types || []).join("\n");
  if (ua) ua.value = (data.ua_keywords || []).join("\n");
  if (browsers) browsers.value = (data.browser_list || []).join("\n");
  if (os) os.value = (data.os_list || []).join("\n");
  const status = document.getElementById("login-blacklist-status");
  if (status) status.textContent = JSON.stringify(data, null, 2);
}

async function saveLoginBlacklist() {
  const ips = (document.getElementById("login-blacklist-ips")?.value || "")
    .split("\n")
    .map(item => item.trim())
    .filter(Boolean);
  const devices = (document.getElementById("login-blacklist-devices")?.value || "")
    .split("\n")
    .map(item => item.trim())
    .filter(Boolean);
  const ua = (document.getElementById("login-blacklist-ua")?.value || "")
    .split("\n")
    .map(item => item.trim())
    .filter(Boolean);
  const browsers = (document.getElementById("login-blacklist-browsers")?.value || "")
    .split("\n")
    .map(item => item.trim())
    .filter(Boolean);
  const os = (document.getElementById("login-blacklist-os")?.value || "")
    .split("\n")
    .map(item => item.trim())
    .filter(Boolean);
  const res = await api("/admin/login-blacklist", {
    method: "POST",
    body: JSON.stringify({ ip_list: ips, device_types: devices, ua_keywords: ua, browser_list: browsers, os_list: os })
  });
  const data = await res.json();
  const status = document.getElementById("login-blacklist-status");
  if (status) status.textContent = JSON.stringify(data, null, 2);
}
