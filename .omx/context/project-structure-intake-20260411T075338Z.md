# Context Snapshot — project-structure-intake

- Task statement: Understand the current repository's overall structure and code before the user provides a concrete requirement.
- Desired outcome: Build an evidence-backed brownfield mental model of the client/server security product so future requirement clarification starts from repo facts instead of guesses.
- Stated solution: Inspect the current codebase only; do not implement anything yet.
- Probable intent hypothesis: The user wants the agent to first internalize the product architecture, boundaries, and major capabilities of a SentinelOne-like endpoint security system before discussing changes.

## Known facts / evidence
- The repository is a two-part product: a Rust endpoint agent under `src/` and a Python FastAPI admin/control server under `server/` (`README.md`, `Cargo.toml`, `server/main.py`).
- Rust agent package name is `windsentinel_agent`; it uses async Tokio, reqwest, sysinfo, AES-GCM, RSA, HMAC, and local filesystem/process/network primitives (`Cargo.toml`).
- Agent main loop initializes signed config, session crypto, encrypted local log store, and policy state, then runs three recurring loops every 5s: telemetry collection, upload/policy pull/health push, and remote shell enablement (`src/main.rs`).
- Agent collects process snapshots, network connection data, and host health, appending compressed+encrypted records to `/tmp/log.dat` before incremental upload (`src/process.rs`, `src/network.rs`, `src/health.rs`, `src/log_store.rs`).
- Agent policy can kill processes, block network via `pfctl`, start remote shell, and lock/unlock the user's home files using RSA-wrapped AES keys (`src/policy.rs`, `src/remote_shell.rs`, `src/lock.rs`).
- Agent config supports signed config bundles verified with HMAC via `WINDSENTINEL_CONFIG_VERIFY_KEY_B64`; default config is written under the OS config directory if missing (`src/config.rs`).
- Python server exposes ingestion endpoints (`/api/v1/health`, `/api/v1/logs`, `/api/v1/policy`) plus many `/admin/*` endpoints for login, MFA, users, agents, policies, rules, shell, config templates, audits, API keys, and log management (`server/main.py`).
- Server persists to SQLite and includes tables for users, health reports, client logs, policies, audits, agent groups/tags/profiles, config templates, API endpoints, log exports, and login allow/deny lists (`server/storage.py`).
- Server applies YARA rules to uploaded records and can set follow-up agent policy based on matches (`server/main.py`).
- Server includes RBAC, MFA, audit logging, API key endpoints, configurable log export backends (Kafka/RabbitMQ/Elasticsearch), and a static admin UI (`server/main.py`, `server/models.py`, `server/static/app.js`, `server/requirements.txt`).

## Constraints
- Current task is understanding only; no direct implementation in deep-interview mode.
- Future requirements may span client, server, or end-to-end interactions; current scope is codebase comprehension.
- Repository appears Unix/macOS-oriented in places (`/bin/zsh`, `pfctl`, `netstat -anv -p tcp`, home directory file walking), so platform assumptions should be treated carefully.

## Unknowns / open questions
- Which future change area the user cares about most: agent, server, admin UI, detection logic, policy pipeline, or architecture/security hardening.
- Whether upcoming work should preserve current product scope or intentionally redesign certain subsystems.
- Which parts of the existing behavior are considered acceptable vs temporary/demo-grade.

## Decision-boundary unknowns
- When a future requirement arrives, can OMX choose whether changes land in client, server, or both without confirmation?
- Is refactoring permitted, or should work stay minimal/localized unless explicitly requested?
- Are security-sensitive behaviors (remote shell, file lock, policy enforcement) allowed to change semantically, or only their implementation quality?

## Likely codebase touchpoints
- Agent orchestration: `src/main.rs`, `src/policy.rs`, `src/log_store.rs`
- Agent telemetry: `src/process.rs`, `src/network.rs`, `src/health.rs`
- Sensitive actions: `src/remote_shell.rs`, `src/lock.rs`, `src/config.rs`
- Server API/control plane: `server/main.py`, `server/models.py`, `server/storage.py`
- Admin UX: `server/static/`
