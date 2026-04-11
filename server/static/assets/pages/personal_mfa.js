window.pageInits["personal_mfa"] = async function () {
  bind("btn-bind-mfa", "click", bindMfa);
  bind("btn-verify-mfa", "click", verifyMfa);
};
