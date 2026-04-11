window.pageInits["shell"] = async function () {
  bind("btn-start-shell", "click", startShell);
  bind("btn-shell-history", "click", loadShellHistory);
  bind("btn-shell-send", "click", sendShell);
  bind("btn-shell-clear", "click", clearShellHistory);
  bind("btn-shell-export-json", "click", () => exportShellHistory("json"));
  bind("btn-shell-export-csv", "click", () => exportShellHistory("csv"));
  bind("btn-shell-search", "click", searchShellHistory);
  bind("btn-shell-prev", "click", () => pageShellHistory(-1));
  bind("btn-shell-next", "click", () => pageShellHistory(1));
  await loadShellHistory();
  startShellPoll();
};
