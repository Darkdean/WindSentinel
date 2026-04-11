async function login() {
  const username = document.getElementById("login-user").value;
  const password = document.getElementById("login-pass").value;
  const mfa = document.getElementById("login-mfa").value;
  const res = await fetch("/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password, mfa: mfa || null })
  });
  const statusEl = document.getElementById("login-status");
  if (!res.ok) {
    statusEl.textContent = await readError(res);
    return;
  }
  const data = await res.json();
  localStorage.setItem("windsentinel_token", data.token);
  localStorage.setItem("windsentinel_role", data.role);
  localStorage.setItem("windsentinel_mfa_bound", data.mfa_bound ? "1" : "0");
  localStorage.setItem("windsentinel_must_change", data.must_change ? "1" : "0");
  window.location.href = "/admin/ui/app";
}

async function readError(res) {
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const data = await res.json();
    return JSON.stringify(data, null, 2);
  }
  return await res.text();
}

document.getElementById("btn-login").addEventListener("click", login);
