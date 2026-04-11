# PRD — V1 Linux Security Platform

## Source of truth
- Requirements spec: `.omx/specs/deep-interview-v1-linux-security-platform.md`
- Context snapshot: `.omx/context/repo-understanding-20260411T075638Z.md`
- Planning note: this PRD is a planning artifact only; no implementation has started.

## Current factual baseline
- Repo shape: Rust agent (`src/`), Python FastAPI server (`server/`), static admin UI (`server/static/`)
- Deferred feature: remote shell already exists in code paths but is out of scope for V1
- Build health: `cargo check` passes; `python3 -m py_compile server/main.py server/storage.py server/models.py server/config.py` passes
- Gap: current directory is **not** a git repository (`.git` missing)
- Gap: no automated test suite was discovered in the current repo
- Linux-compatibility hotspots already visible in code:
  - `pfctl` in `src/policy.rs` is not a Linux firewall mechanism
  - `netstat` parsing in `src/network.rs` is likely platform-fragile
  - service/install/uninstall flows do not yet exist for Linux release delivery

## Principles
1. Linux-first delivery over feature invention.
2. End-to-end operability beats partial feature breadth.
3. Documentation ships with implementation, not after it.
4. V1 hardens against tampering pragmatically, without claiming absolute root-proof security.
5. No implementation step proceeds without the user’s confirmation.

## Decision drivers
1. User-defined V1 scope requires all 10 management capabilities in full.
2. Agent must become a Linux-native, systemd-managed resident service.
3. The current codebase is a prototype; release readiness requires packaging, deployment, verification, docs, and git discipline in addition to feature fixes.

## Viable options considered
### Option A — Minimal patching of current codebase
- Pros: fastest path to visible progress
- Cons: likely accumulates release debt; weak Linux packaging/service behavior; docs and testability remain fragile

### Option B — Release-hardening pass around the existing architecture (**chosen**)
- Pros: preserves current Rust/FastAPI/static-UI architecture while addressing Linux service, deployment, documentation, verification, and V1 gaps
- Cons: requires disciplined sequencing and some non-feature infrastructure work first

### Option C — Broader architecture rewrite before V1
- Pros: cleaner long-term design
- Cons: too risky and too slow for the requested first releasable version

## Strongest antithesis (architectural challenge)
The strongest argument against the chosen path is that trying to make **all 10 management areas**, plus Linux service hardening, plus cross-distro/x86_64+ARM support, plus release/documentation discipline in one V1 may overload a brownfield prototype and hide architectural debt until late verification.

## Why the chosen path still stands
A rewrite-first approach would miss the user’s release goal. The lower-risk way to manage this tension is not to reduce scope arbitrarily, but to front-load:
- repository/release discipline
- Linux compatibility gap analysis
- deployment/runtime foundations
- explicit remote-shell exclusion
- milestone-level verification gates

## Selected approach
Use the current architecture as the V1 base and run a release-hardening program in ordered milestones: repository/bootstrap hygiene, Linux compatibility gap inventory, agent Linux residency and packaging, server deployment hardening, admin/UI verification, management module completion, documentation, release tagging.

## Scope
### In scope
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
11. Linux bare-metal deployment for server/admin
12. Docker Compose deployment artifact and deployment instructions after bare-metal path
13. Git-managed release/version flow and synchronized documentation set

### Out of scope
- Remote shell
- Claiming absolute root-proof anti-tamper

## Key tradeoff tensions
1. **Scope completeness vs release speed** — all 10 areas are mandatory, so speed must come from sequencing and verification, not scope cuts.
2. **Brownfield reuse vs refactor cleanliness** — reuse is faster, but targeted refactors may still be required where Linux compatibility is impossible otherwise.
3. **Anti-tamper ambition vs Linux reality** — V1 should materially raise tamper cost without promising impossible guarantees.
4. **Cross-distro/arch support vs verification cost** — CentOS/Ubuntu and x86_64/ARM multiplies packaging and test effort.
5. **Bare-metal first vs Compose follow-up** — Compose comes second, but its artifact still needs to reflect the bare-metal runtime accurately.

## Major workstreams
### WS0 — Release foundation and confirmation gate
- Obtain user confirmation before each substantive milestone begins
- Initialize git repository only after explicit go-ahead
- Define release/versioning convention
- Create release checklist and document inventory
- Record known execution prerequisites (remote URL, supported distro versions, arch naming, auth model)

### WS1 — Linux compatibility gap inventory
- Audit the Rust agent for Linux-incompatible commands, paths, permissions, and lifecycle assumptions
- Audit the Python server and static UI for Linux deployment/runtime assumptions
- Produce a tracked gap list with file-level touchpoints and recommended dispositions
- Explicitly inventory every current remote-shell backend/UI surface that must be disabled for V1

### WS2 — Agent Linux hardening
- Design Linux runtime layout (binary/config/data/log locations)
- Add systemd unit/service lifecycle behavior
- Define install/uninstall/upgrade model
- Implement authorization-based stop/uninstall flow
- Implement V1 anti-tamper cost-raising controls
- Replace or rework Linux-incompatible logic (network collection, firewall/blocking strategy, service behavior)

### WS3 — Server bare-metal readiness
- Normalize runtime/config paths and secrets handling
- Add documented production startup method and service supervision model
- Validate SQLite usage, retention, backup/restore, and export behavior on Linux
- Remove or hide deferred remote-shell server paths from V1 runtime/admin surface where needed

### WS4 — Admin UI functional completion
- Verify each of the 10 management modules against server behavior
- Remove or hide remote-shell UI paths
- Align copy/workflows/docs with Linux V1 behavior

### WS5 — Feature completion in required order
Implement/finish and verify in this order:
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

### WS6 — Documentation and deployment packaging
- Client install/use guide
- Server install/use guide
- Admin UI install/use guide
- Architecture docs: network, database, component design, service/deployment topology, anti-tamper boundary
- Feature docs and code-explanation docs
- Bare-metal deployment runbook
- Docker Compose deployment guide
- Release notes + tag checklist

## Milestone plan
### M0 — Planning closure and repository bootstrap prep
Deliverables:
- `.omx/plans/` artifacts finalized
- documentation matrix finalized
- execution prerequisites list finalized
- no code changes yet

### M1 — Gap inventory and repo baseline
Deliverables:
- git bootstrap plan approved (and executed only with user confirmation)
- Linux compatibility gap report
- remote-shell exclusion inventory
- doc skeleton created

### M2 — Agent Linux residency baseline
Deliverables:
- Agent runs under systemd
- install/start/restart path documented
- first anti-tamper controls implemented and bounded
- Linux-incompatible agent behaviors dispositioned

### M3 — Core server/admin deployability
Deliverables:
- bare-metal server deployment on Ubuntu/CentOS documented and repeatable
- admin UI reachable and authenticated
- config, storage, startup, retention baseline validated on Linux
- deferred remote shell removed or hidden from V1 server/UI path

### M4 — Core management path complete (1-5)
Deliverables:
- Agent list/detail
- policy delivery
- rule management
- log query
- audit logs
- end-to-end smoke verification

### M5 — Remaining management path complete (6-10)
Deliverables:
- user/MFA
- config templates
- groups/tags
- black/white lists
- log export/retention

### M6 — Release hardening and packaging
Deliverables:
- full docs synchronized
- Docker Compose artifact and guide
- release notes
- version/tag candidate starting from `v1.0`

## Dependency order
1. M0 before everything else.
2. M1 before implementation, because Linux compatibility and remote-shell exclusion must be explicit before edits.
3. M2 before feature-level verification, because Linux-resident agent behavior is foundational.
4. M3 before M4/M5, because management functions need a reproducible server/admin runtime.
5. M4 before M5, matching the user’s requested delivery order.
6. M6 only after feature and deployment verification.

## Sequencing risks to watch
1. Starting feature fixes before the Linux gap inventory may cause duplicate rework.
2. Leaving remote-shell code/UI visible too long risks accidental scope leakage into V1.
3. Defining anti-tamper too late may force installer/service redesign.
4. Waiting too long to establish git/doc structure violates the user’s release-management rules.
5. Attempting ARM support only at the end would create late packaging surprises.

## Verification strategy summary
- Build/static checks per stack on every milestone
- Linux smoke tests on CentOS + Ubuntu and x86_64 + ARM where feasible
- End-to-end functional checks for each management module
- Service lifecycle tests for install/start/restart/authorized stop/uninstall
- Documentation walk-through validation
- Release checklist evidence capture before any tag candidate

## Risk register
1. **No git repo exists yet** — blocks release history/tagging until fixed.
2. **Agent anti-tamper goal may exceed user-space guarantees** — must document exact V1 boundary and test realistic controls only.
3. **Cross-distro and cross-arch support** — packaging/service scripts may diverge between CentOS and Ubuntu, and between x86_64 and ARM.
4. **Prototype code concentration in `server/main.py`** — large-file changes increase regression risk.
5. **No automated tests currently exist** — raises verification cost and release risk until coverage is added.
6. **Remote shell is currently implemented in code** — needs explicit exclusion from runtime/UI/doc paths to avoid scope leakage.
7. **Linux incompatibilities already visible in agent code** — firewall/network/process handling require redesign, not just packaging.

## Required plan changes before execution approval
1. Create a dedicated Linux compatibility gap artifact before touching code.
2. Create a documentation matrix artifact so each implementation slice has explicit doc obligations.
3. Treat git bootstrap as an explicit first execution step, not an assumed background task.
4. Add an architecture decision for the anti-tamper authorization mechanism before service/uninstall implementation.
5. Add an early checkpoint for ARM target validation, not only final release validation.

## Recommended planning artifacts under `.omx/plans/`
- `prd-v1-linux-security-platform.md`
- `test-spec-v1-linux-security-platform.md`
- `docs-matrix-v1-linux-security-platform.md`
- `linux-gap-inventory-v1-linux-security-platform.md` (to be created in execution M1)

## Available agent types / suggested staffing for later execution
- `executor`: core implementation across Rust/Python/UI
- `architect`: Linux runtime/deployment/service boundary reviews
- `test-engineer`: matrix and acceptance verification strategy
- `security-reviewer`: anti-tamper/auth/rule handling review
- `writer`: documentation and release note drafting
- `verifier`: release evidence validation
- `code-reviewer`: pre-release code review

## Team / Ralph handoff guidance
- Prefer **`$ralph`** for sequential milestone execution with explicit stop points for user confirmation.
- Prefer **`$team`** only after M1/M2 foundations are complete and workstreams can be split safely.
- In either mode, keep remote shell disabled and require doc updates in the definition of done for every milestone.

## Inputs still needed before implementation
1. Whether git should be initialized in this directory and connected to `https://github.com/Darkdean/WindSentinel.git` as the release repository.
2. Detailed protocol design for the selected anti-tamper authorization model (unique per-client offline code + server-issued uninstall task).


## Architectural review adjustments
### Strongest antithesis
The user-selected V1 scope is very large for a first release: full agent/server/admin coverage, 10 management capabilities, Linux distro+arch matrix, anti-tamper work, deployment packaging, synchronized documentation, and release/version discipline. The biggest risk is treating feature completion as the only work, while release foundations (git bootstrap, docs, packaging, service/install model, deployment repeatability) remain unfinished.

### Key tradeoff tensions
1. **Feature breadth vs release reliability** — delivering all 10 modules without first stabilizing install/deploy/service flows risks a non-releasable product.
2. **Anti-tamper ambition vs Linux reality** — cost-raising controls are feasible; absolute guarantees are not.
3. **Brownfield speed vs code health** — avoid broad rewrites, but isolate Linux/deployment-critical changes carefully to reduce regression risk.

### Required pre-execution decisions
These are the main inputs still needed before implementation begins:
1. GitHub remote URL and whether this directory should be initialized as the release repo here.
2. Versioning format for the first release tag.
3. Exact CentOS target family/version (for example 7 vs Stream 8/9 or RHEL-compatible scope).
4. Whether ARM support specifically means `aarch64`.
5. Preferred authorization mechanism for agent stop/uninstall approval.


## Newly clarified inputs
1. GitHub remote repository: `https://github.com/Darkdean/WindSentinel.git`
2. Versioning rule: start at `v1.0`; if overall architecture remains unchanged, every 2 new requirements increments the minor version
3. CentOS targets: 7, 8, 9 and newer; Ubuntu targets: 20, 22, 24
4. ARM target: `aarch64`
5. Agent authorization requires both a unique per-client offline code entered locally and a server-issued uninstall task flow with self-uninstall + client-data cleanup
6. Admin-issued client stop/uninstall operations must enforce RBAC + MFA; auditors cannot operate client behavior; invalid MFA must fail explicitly; command issuance must be auditable in web log/audit views
2. Versioning rule: start at `v1.0`; if the overall architecture is unchanged, every 2 new requirements increments the minor version
3. CentOS targets: 7, 8, 9 and newer; Ubuntu targets: 20, 22, 24
4. ARM target: `aarch64`
5. Client stop/uninstall requires authorization with two paths:
   - unique per-client offline authorization code entered locally
   - web-admin-issued uninstall task written server-side and executed by the agent, including client-data cleanup
6. Admin-issued stop/uninstall must enforce role permissions and bound MFA; auditors cannot trigger client-behavior operations; wrong MFA must produce an explicit verification error; command issuance must appear in audit/log views
