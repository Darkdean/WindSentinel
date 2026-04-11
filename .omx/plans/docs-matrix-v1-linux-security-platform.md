# Documentation Matrix — V1 Linux Security Platform

## Rule
Any change to code, architecture, deployment, configuration, or operational behavior must update all affected docs in the same change set.

## Required documents
| Document | Purpose | Must update when |
|---|---|---|
| `docs/client-install-use.md` | Client install, service control, upgrade, uninstall, troubleshooting | Agent binary/service/install/uninstall/config/runtime behavior changes |
| `docs/server-install-use.md` | Server install/start/upgrade/backup/restore/troubleshooting | Server runtime, config, DB path, process model, dependencies change |
| `docs/admin-install-use.md` | Admin UI access/login/operation guide | UI routes, auth flows, admin workflows change |
| `docs/architecture-overview.md` | End-to-end system/component overview | Cross-component behavior or boundaries change |
| `docs/network-architecture.md` | Ports, protocols, data flow, trust boundaries | API endpoints, service topology, agent-server communication change |
| `docs/database-architecture.md` | SQLite schema, retention, backup, migration notes | Storage schema/retention/export/audit structures change |
| `docs/design-patterns.md` | Important design rules and module boundaries | Architecture or implementation conventions change |
| `docs/feature-matrix.md` | V1 feature scope, exclusions, platform matrix | Scope, feature completeness, or platform support changes |
| `docs/code-map.md` | Code structure and module explanation | File/module boundaries materially change |
| `docs/release-checklist.md` | Release validation, versioning, tag/push checklist | Release process or validation gates change |
| `docs/docker-compose-deploy.md` | Compose deployment steps and caveats | `docker-compose.yml` or service layout changes |

## Planning-created artifacts
- `.omx/specs/deep-interview-v1-linux-security-platform.md`
- `.omx/plans/prd-v1-linux-security-platform.md`
- `.omx/plans/test-spec-v1-linux-security-platform.md`
- `.omx/plans/docs-matrix-v1-linux-security-platform.md`

## Release documentation gates
A candidate version is not releasable unless:
1. affected docs are updated
2. deployment docs were re-walked for changed surfaces
3. release notes summarize scope, exclusions, known limitations, and verification evidence
4. version/tag metadata aligns with the actual delivered artifact set
