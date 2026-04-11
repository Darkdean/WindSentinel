# WindSentinel Code Map

## Agent (Rust)
- `src/main.rs` — main loops and task scheduling
- `src/config.rs` — config load and signature verification
- `src/control.rs` — offline authorization state, control-task polling/ack, local control CLI, helper-based stop/uninstall flow
- `src/log_store.rs` — local encrypted log store and upload
- `src/policy.rs` — policy fetch/apply
- `src/health.rs` — health collection and upload
- `src/process.rs` — process collection
- `src/network.rs` — network collection
- `src/lock.rs` — file lock/unlock behavior
- Remote shell implementation files are removed from the V1-active code surface and are not part of the shipped runtime/config/API/UI flow

## Server (Python)
- `server/main.py` — API and admin logic
- `server/storage.py` — PostgreSQL storage layer and schema helpers
- `server/models.py` — request/response models
- `server/config.py` — runtime config
- `server/main.py` now also carries the stop/uninstall server-foundation endpoints for offline-code rotation, control-task creation, agent task delivery, and task acknowledgement
- `server/static/pages/agent_manage.html` and `server/static/app.js` now expose the admin UI entry points for control metadata, code rotation, and stop/uninstall task issuance
- `server/storage.py` now also stores offline authorization metadata and agent control task records

## Admin UI
- `server/static/` — static admin pages and JS assets

## M0 note
This document is a baseline map and must be expanded as implementation changes module boundaries.
