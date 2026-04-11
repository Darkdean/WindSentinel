const tokenKey = "windsentinel_token";

function getToken() {
  return localStorage.getItem(tokenKey);
}

async function apiFetch(path, options = {}) {
  const headers = options.headers || {};
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  if (!headers["Content-Type"] && options.body) headers["Content-Type"] = "application/json";
  return fetch(path, { ...options, headers });
}

const pageScripts = new Set();

async function loadPageScript(page) {
  if (pageScripts.has(page)) return;
  await new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/admin/ui/assets/pages/" + page + ".js";
    script.onload = () => resolve(true);
    script.onerror = () => reject(new Error("load page script failed"));
    document.body.appendChild(script);
  });
  pageScripts.add(page);
}

async function loadPage(page) {
  await window.commonReady;
  const res = await apiFetch("/admin/ui/pages/" + page);
  const container = document.getElementById("page-container");
  if (!res.ok) {
    container.textContent = "404";
    return;
  }
  const html = await res.text();
  container.innerHTML = html;
  await loadPageScript(page);
  if (window.pageInits && window.pageInits[page]) {
    await window.pageInits[page]();
  }
}

function setNavVisibility(role) {
  const map = {
    admin: ["agents","agent_manage","config","policy","rules","logs","audits","users","log_management","login_blacklist","login_whitelist","api_keys"],
    auditor: ["agents","logs","audits"],
    operator: ["agents","agent_manage","config","policy","rules","login_blacklist","login_whitelist"]
  };
  const allowed = new Set(map[role] || []);
  document.querySelectorAll("[data-page]").forEach(item => {
    const page = item.getAttribute("data-page");
    if (page && !allowed.has(page) && !page.startsWith("personal_")) {
      item.classList.add("nav-hidden");
    } else {
      item.classList.remove("nav-hidden");
    }
  });
}

async function initAdmin() {
  const token = getToken();
  if (!token) {
    window.location.href = "/admin/ui/login";
    return;
  }
  const res = await apiFetch("/admin/me");
  if (!res.ok) {
    window.location.href = "/admin/ui/login";
    return;
  }
  const data = await res.json();
  document.getElementById("user-info").textContent = data.username + " (" + data.role + ")";
  setNavVisibility(data.role);
  document.querySelectorAll("[data-page]").forEach(item => {
    item.addEventListener("click", () => loadPage(item.getAttribute("data-page")));
  });
  document.querySelectorAll("[data-toggle]").forEach(item => {
    item.addEventListener("click", () => {
      const key = item.getAttribute("data-toggle");
      const children = document.querySelector('[data-parent="' + key + '"]');
      if (children) children.classList.toggle("nav-hidden");
    });
  });
  document.getElementById("btn-logout").addEventListener("click", async () => {
    await apiFetch("/admin/logout", { method: "POST" });
    localStorage.removeItem(tokenKey);
    window.location.href = "/admin/ui/login";
  });
  const mustChange = localStorage.getItem("windsentinel_must_change") === "1";
  const mfaBound = localStorage.getItem("windsentinel_mfa_bound") === "1";
  if (!mfaBound) {
    await loadPage("personal_mfa");
    return;
  }
  if (mustChange) {
    await loadPage("personal_password");
    return;
  }
  await loadPage("agents");
}

window.pageInits = window.pageInits || {};
initAdmin();
