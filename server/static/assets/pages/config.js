window.pageInits["config"] = async function () {
  bind("btn-cfg-template", "click", loadConfigTemplate);
  bind("btn-cfg-sign", "click", signConfigPreview);
  bind("btn-cfg-download", "click", downloadConfig);
  bind("btn-cfg-package", "click", () => downloadConfig("zip"));
  bind("btn-cfg-meta", "click", loadPackageMeta);
  bind("btn-cfg-template-save", "click", saveConfigTemplate);
  bind("btn-cfg-template-load", "click", loadSelectedTemplate);
  bind("btn-cfg-template-delete", "click", deleteSelectedTemplate);
  bind("btn-cfg-template-export", "click", exportTemplates);
  bind("btn-cfg-template-import", "click", importTemplates);
  bind("btn-cfg-template-versions", "click", loadTemplateVersions);
  bind("btn-cfg-template-rollback", "click", rollbackTemplateVersion);
  bind("cfg-meta-auto", "change", () => {
    const checked = document.getElementById("cfg-meta-auto").checked;
    if (checked) startMetaAutoRefresh();
    else stopMetaAutoRefresh();
  });
  await loadConfigTemplates();
  await loadPackageMeta();
};
