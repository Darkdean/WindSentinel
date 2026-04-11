window.pageInits["audits"] = async function () {
  bind("btn-load-audits", "click", loadAudits);
  initDefaults();
  await loadAudits();
};
