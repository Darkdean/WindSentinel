# WindSentinel Architecture Overview

## Current architecture
- Rust agent in `src/`
- Python FastAPI server in `server/`
- static admin UI in `server/static/`
- SQLite persistence in `server/`

## V1 architectural goals
- Linux-first release hardening
- systemd-managed agent residency
- bare-metal server/admin deployment first
- Docker Compose artifact after bare-metal deployment is complete
- remote shell excluded from V1 runtime, API, policy, and UI surfaces

## To be detailed during implementation
- deployment topology
- trust boundaries
- anti-tamper boundary and authorization model
- release packaging flow

## Selected control-plane decision
- Stop / uninstall uses two separate authorization paths in V1:
  - local unique per-client offline authorization code
  - server-issued uninstall control task
- Admin-issued client control requires RBAC + operation-time MFA + audit logging.
- Remote shell is not part of the V1 control plane.
- Server foundation now includes offline-code metadata, control-task lifecycle APIs, and audit correlation support for stop/uninstall actions.
- Agent foundation now includes:
  - local offline-code verification state
  - control-task polling and acknowledgement path
  - helper-based authorized stop/uninstall execution flow
