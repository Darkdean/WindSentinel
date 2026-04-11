# WindSentinel Server Install and Use Guide

## Status
M0 baseline skeleton. Complete during server deployment implementation.

## Planned scope
- supported Linux distributions
- Python/runtime dependency installation
- configuration and secret environment variables
- PostgreSQL connection, credentials, and backup notes
- service startup and process supervision
- upgrade and rollback steps
- troubleshooting and health checks

## Current known gaps
- production Linux service model not yet finalized
- Docker Compose deployment will be documented only after bare-metal deployment is complete
- PostgreSQL deployment/runbook is not yet documented end-to-end
- stop/uninstall server foundation is now present:
  - offline authorization-code metadata + rotation APIs
  - control-task create/list/ack delivery APIs
  - RBAC + operation-time MFA gate for client control
  - audit correlation for control-task lifecycle


## macOS support
The server/admin stack is now supported for local/runtime use on macOS as well as Linux, provided PostgreSQL is available.

### Recommended macOS run flow
1. Create and activate a Python virtual environment under `server/.venv`
2. Install dependencies from `server/requirements.txt`
3. Copy `server/.env.example` into your local environment or export equivalent variables
4. Ensure PostgreSQL is reachable with the configured credentials
5. Start the server with:
   - `PYTHONPATH=server server/.venv/bin/python server/run_server.py --reload`
   - or `PYTHONPATH=server server/.venv/bin/python -m uvicorn main:app --app-dir server --reload`

### Notes
- macOS support here is for the **server/admin runtime**; the Linux agent remains a separate target
- systemd instructions apply only to Linux deployment, not macOS
- PostgreSQL remains the required database on macOS too
