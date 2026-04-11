# Test Specification — V1 Linux Security Platform

## Source of truth
- Requirements spec: `.omx/specs/deep-interview-v1-linux-security-platform.md`
- PRD: `.omx/plans/prd-v1-linux-security-platform.md`

## Testing principles
1. No release claim without evidence for client, server, and admin UI.
2. Linux service/deployment behavior is part of the feature scope, not a postscript.
3. Deferred remote shell must be tested as **disabled / inaccessible** in V1.
4. Documentation validation is a release gate.

## Baseline checks
- Rust build: `cargo check`, release build, target-arch checks as applicable
- Python syntax/import sanity: `python3 -m py_compile ...`
- UI asset sanity: route/page availability and basic browser smoke path
- Git/release baseline: repo initialized, release/tag checklist present

## Platform matrix
### Server/Admin
- Ubuntu 20/22/24 bare-metal
- CentOS 7/8/9+ bare-metal

### Agent
- Ubuntu 20/22/24 x86_64
- Ubuntu 20/22/24 ARM (`aarch64`)
- CentOS 7/8/9+ x86_64
- CentOS 7/8/9+ ARM (`aarch64`)

## Milestone test groups
### T0 — Planning and repo baseline
- planning artifacts exist under `.omx/plans/`
- docs matrix exists
- release checklist exists
- git bootstrap step is ready but not executed without explicit confirmation

### T1 — Linux compatibility gap inventory
- file-level Linux incompatibilities are enumerated
- remote-shell backend/UI touchpoints are enumerated
- each gap has a planned disposition

### T2 — Agent Linux runtime baseline
- Agent builds on target toolchain(s)
- config, data, and log paths are valid on Linux
- systemd unit installs cleanly
- service enables, starts, restarts on failure, and survives reboot
- unauthorized stop/disable/uninstall attempts fail or are blocked per V1 design
- authorized local offline-code stop/uninstall path succeeds
- server-issued uninstall task path succeeds, including self-uninstall and cleanup of client-related data
- Linux-specific replacements for incompatible behaviors are verified
- remote shell feature is disabled / inaccessible in V1

### T3 — Server/Admin bare-metal baseline
- Python dependencies install cleanly on target Linux
- server starts cleanly under documented run method
- admin UI loads via server deployment
- SQLite DB initializes correctly
- startup background workers do not crash
- retention/export baseline behaves as documented
- remote shell UI/backend path is hidden or disabled in V1

### T4 — Core management features 1–5
1. Agent list/detail
   - agent appears after registration/reporting
   - detail view returns expected latest state
2. Policy delivery
   - policy save and retrieval work
   - agent polling receives expected policy
3. Rule management
   - create/update/list/version/restore/export/import flow works
4. Log query
   - logs ingest and query work with expected filters/results
5. Audit logs
   - admin actions create audit entries
   - audit filters/stats behave correctly

### T5 — Remaining features 6–10
6. User/MFA
   - login, MFA bind/verify, password change, role-based access
   - MFA challenge on admin-issued client stop/uninstall actions
7. Config generation/templates
   - generate, save, load, version, export/import, rollback templates
8. Groups/tags
   - create/list/delete groups and tags; assign tags/profile associations
9. Black/white lists
   - login allow/deny behavior matches configured lists
10. Log export/retention
   - retention settings persist
   - export targets save and dispatch attempts execute as designed

### T6 — Documentation / deployment / release
- Client install/use doc can be followed on Linux end to end
- Server install/use doc can be followed on Linux bare metal end to end
- Admin UI install/use doc is complete
- Architecture docs reflect delivered design
- Feature docs reflect delivered V1 behavior and exclusions
- Code docs reflect actual modules/layout
- Docker Compose YAML parses
- Docker Compose deployment steps are complete for user validation
- Tagging/versioning/release note steps are documented

## Regression priorities
### High
- agent service lifecycle
- policy fetch/apply loop
- server startup and auth
- admin login and core management actions
- log ingest/query/audit persistence
- remote-shell exclusion

### Medium
- config templates
- groups/tags
- black/white lists
- export/retention
- documentation walk-throughs

## Evidence to collect
- build outputs/logs
- systemd status outputs
- API smoke results
- screenshots or terminal captures for admin flows
- deployment transcript notes
- doc validation checklist
- release checklist with timestamps and environments

## Exit gates
A version is releasable only when:
1. Client, server, and admin UI each complete current-version functional requirements.
2. Required modules 1–10 pass release smoke tests.
3. Linux deployment/docs are complete and usable.
4. Documentation is updated with the actual code/config/architecture state.
5. Deferred remote shell is verified absent or inaccessible in V1 user/admin/runtime paths.
6. Release is versioned and tag-ready.


## Versioning verification
- Confirm release baseline starts at `v1.0`
- Confirm minor-version increments follow the user rule when architecture remains unchanged


## Additional authorization checks
- Auditor role cannot issue client stop/uninstall operations
- Authorized role without valid MFA receives explicit MFA verification error
- Authorized role with valid MFA can issue the task successfully
- Client-behavior task issuance is visible in audit/log views with actor, time, target, and result
