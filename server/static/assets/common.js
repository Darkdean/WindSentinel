window.commonReady = new Promise((resolve, reject) => {
  const script = document.createElement("script");
  script.src = "/admin/ui/legacy/app.js";
  script.onload = () => resolve(true);
  script.onerror = () => reject(new Error("load common failed"));
  document.head.appendChild(script);
});
