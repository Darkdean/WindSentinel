# WindSentinel V1 Feature Matrix

## Required in V1
1. Agent list/detail
2. Policy delivery
3. Rule management
4. Log query
5. Audit logs
6. User/MFA
7. Config generation/templates
8. Groups/tags
9. Black/white lists
10. Log export/retention

## Explicitly deferred from V1
- Remote shell (removed/hidden from V1-visible runtime, policy, config, and UI surfaces)

## Additional V1 security requirements
- Agent systemd residency on Linux
- stop/uninstall authorization via unique offline client code
- server-issued uninstall task with self-uninstall and cleanup
- RBAC + MFA + audit coverage for admin-issued stop/uninstall actions

## Server foundation progress
- Server-side foundation for stop/uninstall now includes:
  - offline authorization-code metadata + rotation path
  - control-task table and API contract for `stop` / `uninstall`
  - RBAC + operation-time MFA gate for admin-issued client control
  - audit correlation for control-task lifecycle events

## Client foundation progress
- Client-side foundation for stop/uninstall now includes:
  - offline authorization metadata bootstrap + refresh path
  - local `control stop` / `control uninstall` command entry
  - control-task polling from server
  - task acknowledgement lifecycle
  - helper-based stop/uninstall execution path

## Tracked design reference
- See `docs/adr/ADR-0001-stop-uninstall-authorization.md` for the accepted V1 authorization design baseline.
