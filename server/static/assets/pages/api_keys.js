window.pageInits["api_keys"] = async function () {
  bind("btn-api-endpoint-create", "click", createApiEndpoint);
  bind("btn-api-endpoint-refresh", "click", loadApiEndpoints);
  bind("btn-api-endpoint-delete", "click", deleteApiEndpoint);
  await loadApiEndpoints();
};
