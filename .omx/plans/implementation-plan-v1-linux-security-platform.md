# Implementation Plan — V1 Linux Security Platform

## ADR Summary
- **Decision:** Deliver V1 by hardening the existing Rust agent + FastAPI server + static admin UI architecture for Linux, rather than rewriting or splitting services before release.
- **Drivers:** full V1 scope, Linux deployability, release discipline, documentation parity, bounded risk.
- **Alternatives considered:** major service split before V1; database replacement before V1; both rejected as scope inflation.
- **Consequences:** faster route to releaseability, but monolithic areas (`server/main.py`) remain a controlled risk for V1.

## Ordered execution lanes (planning only)
### Lane 0 — Foundation
- initialize git/release workflow
- scaffold docs and release checklist
- record versioning/tagging convention

### Lane 1 — Linux agent residency
- systemd service/unit design
- install/uninstall/update flow
- anti-tamper V1 controls
- remote shell disablement

### Lane 2 — Server/Admin deployability
- Linux bare-metal startup/runbook
- service management and config handling
- admin UI routing/static path validation

### Lane 3 — Management capabilities 1–5
- agent list/detail
- policy delivery
- rules
- logs query
- audits

### Lane 4 — Management capabilities 6–10
- user/MFA
- config/templates
- groups/tags
- black/white lists
- export/retention

### Lane 5 — Release hardening
- docs sync pass
- docker compose artifact and guide
- release notes, tag prep, final verification

## Sequencing constraints
1. Do not begin release tagging work before git exists.
2. Do not verify 1–10 capability flows before Linux runtime/deployment baseline exists.
3. Do not publish Docker Compose as the primary path; it follows bare-metal completion.
4. Keep remote shell disabled throughout V1 design, docs, and verification.

## Recommended first executable milestone after approval
- **Milestone 0 only**: initialize git, create docs tree, create release checklist, and formalize version/tag naming.

## Verification hooks by lane
- Lane 0: git status, docs tree present, release checklist present
- Lane 1: systemd install/start/restart/unauthorized stop tests
- Lane 2: bare-metal bring-up on Linux
- Lane 3/4: end-to-end admin/API/agent capability checks
- Lane 5: regression + docs walk-through + tag readiness
