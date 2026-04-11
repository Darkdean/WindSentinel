window.pageInits["policy"] = async function () {
  bind("btn-send-policy", "click", sendPolicy);
  bind("btn-policy-group", "click", sendPolicyToGroup);
  bind("btn-policy-tag", "click", sendPolicyToTag);
  bind("btn-policy-retry", "click", retryPolicyBatch);
  await loadGroups();
  await loadTags();
};
