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
- Remote shell

## Additional V1 security requirements
- Agent systemd residency on Linux
- stop/uninstall authorization via unique offline client code
- server-issued uninstall task with self-uninstall and cleanup
- RBAC + MFA + audit coverage for admin-issued stop/uninstall actions

## Tracked design reference
- See `docs/adr/ADR-0001-stop-uninstall-authorization.md` for the accepted V1 authorization design baseline.
