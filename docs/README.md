# WindSentinel Documentation Index

## Release baseline
- Target release line: `v1.0`
- GitHub remote: `https://github.com/Darkdean/WindSentinel.git`
- Supported Linux scope for V1:
  - CentOS 7 / 8 / 9+
  - Ubuntu 20 / 22 / 24
  - x86_64
  - ARM (`aarch64`)
- Additional host runtime support:
  - macOS (server/admin runtime support)

## Core product docs
- [Client install and use](./client-install-use.md)
- [Server install and use](./server-install-use.md)
- [Admin UI install and use](./admin-install-use.md)
- [Feature matrix](./feature-matrix.md)
- [Code map](./code-map.md)

## Architecture docs
- [Architecture overview](./architecture-overview.md)
- [Network architecture](./network-architecture.md)
- [Database architecture](./database-architecture.md)
- [Design patterns and implementation rules](./design-patterns.md)

## Release / operations docs
- [Release checklist](./release-checklist.md)
- [Versioning policy](./versioning-policy.md)
- [Docker Compose deployment](./docker-compose-deploy.md)
- [Release notes draft for v1.0](./releases/v1.0-draft.md)

## Change policy
Any code, architecture, deployment, configuration, or operational change must update all affected documents in the same change set.

## ADRs
- [ADR-0001: Stop / Uninstall Authorization Mechanism](./adr/ADR-0001-stop-uninstall-authorization.md)
