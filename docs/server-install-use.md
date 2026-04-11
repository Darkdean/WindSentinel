# WindSentinel Server Install and Use Guide

## Status
M0 baseline skeleton. Complete during server deployment implementation.

## Planned scope
- supported Linux distributions
- Python/runtime dependency installation
- configuration and secret environment variables
- database file path and backup notes
- service startup and process supervision
- upgrade and rollback steps
- troubleshooting and health checks

## Current known gaps
- production Linux service model not yet finalized
- Docker Compose deployment will be documented only after bare-metal deployment is complete
- stop/uninstall server foundation is now present:
  - offline authorization-code metadata + rotation APIs
  - control-task create/list/ack delivery APIs
  - RBAC + operation-time MFA gate for client control
  - audit correlation for control-task lifecycle
