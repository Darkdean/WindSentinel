window.pageInits["login_whitelist"] = async function () {
  bind("btn-login-whitelist-refresh", "click", loadLoginWhitelist);
  bind("btn-login-whitelist-save", "click", saveLoginWhitelist);
  await loadLoginWhitelist();
};

async function loadLoginWhitelist() {
  const res = await api("/admin/login-whitelist");
  const data = await res.json();
  const ips = document.getElementById("login-whitelist-ips");
  if (ips) ips.value = (data.ip_list || []).join("\n");
  const status = document.getElementById("login-whitelist-status");
  if (status) status.textContent = JSON.stringify(data, null, 2);
}

async function saveLoginWhitelist() {
  const ips = (document.getElementById("login-whitelist-ips")?.value || "")
    .split("\n")
    .map(item => item.trim())
    .filter(Boolean);
  const res = await api("/admin/login-whitelist", {
    method: "POST",
    body: JSON.stringify({ ip_list: ips })
  });
  const data = await res.json();
  const status = document.getElementById("login-whitelist-status");
  if (status) status.textContent = JSON.stringify(data, null, 2);
}
