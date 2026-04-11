window.pageInits["users"] = async function () {
  bind("btn-create-user", "click", createUser);
  bind("btn-delete-user", "click", deleteUser);
  await loadUsers();
};
