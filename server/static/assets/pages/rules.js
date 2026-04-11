window.pageInits["rules"] = async function () {
  bind("btn-load-rules", "click", loadRules);
  bind("rule-list", "change", selectRule);
  bind("btn-save-rule", "click", saveRule);
  bind("btn-restore-rule", "click", restoreRule);
  bind("btn-diff-rule", "click", diffRule);
  bind("btn-copy-diff", "click", copyDiff);
  bind("btn-rule-export", "click", exportRules);
  bind("btn-rule-import", "click", importRules);
  bind("btn-rule-import-preview", "click", previewImportRules);
  await loadRules();
};
