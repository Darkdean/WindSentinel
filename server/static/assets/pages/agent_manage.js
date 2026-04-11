window.pageInits["agent_manage"] = async function () {
  bind("btn-agent-load", "click", loadAgentProfile);
  bind("btn-agent-save", "click", saveAgentProfile);
  bind("btn-group-create", "click", createGroup);
  bind("btn-group-delete", "click", deleteGroup);
  bind("btn-tag-create", "click", createTag);
  bind("btn-tag-delete", "click", deleteTag);
  bind("btn-control-meta-load", "click", loadClientControlState);
  bind("btn-control-task-refresh", "click", loadClientControlTasks);
  bind("btn-control-code-rotate", "click", rotateOfflineAuthorizationCode);
  bind("btn-control-stop", "click", () => createClientControlTask("stop"));
  bind("btn-control-uninstall", "click", () => createClientControlTask("uninstall"));
  await loadGroups();
  await loadTags();
  await loadAgentProfile();
  await loadClientControlState();
  await loadClientControlTasks();
};
