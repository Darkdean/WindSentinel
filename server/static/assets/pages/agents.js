window.pageInits["agents"] = async function () {
  bind("btn-load-agents", "click", loadAgents);
  bind("agent-list", "change", selectAgent);
  bind("btn-agent-filter", "click", applyAgentFilter);
  bind("btn-agent-filter-reset", "click", resetAgentFilter);
  bind("btn-agent-prev", "click", () => pageAgents(-1));
  bind("btn-agent-next", "click", () => pageAgents(1));
  await loadGroups();
  await loadTags();
  await loadAgents();
};
