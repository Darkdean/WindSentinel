# Linux Gap Inventory — V1 Linux Security Platform

## Scope
M1 artifact only. No implementation changes are included here.

## Source of truth
- Requirements spec: `.omx/specs/deep-interview-v1-linux-security-platform.md`
- PRD: `.omx/plans/prd-v1-linux-security-platform.md`
- Test spec: `.omx/plans/test-spec-v1-linux-security-platform.md`

## Current factual baseline
- Rust agent builds locally (`cargo check` passes)
- Python server files compile locally (`python3 -m py_compile ...` passes)
- Remote shell is currently implemented across agent, server, API, and admin UI
- Linux service/install/uninstall/authorization flows are not yet implemented

## Executive summary
There are four M1-critical gaps before Linux V1 feature completion can safely begin:

1. **Remote shell is still wired end-to-end** and must be removed or hidden from V1 runtime, API, policy defaults, and UI.
2. **Agent Linux compatibility is incomplete** because some current logic is macOS/BSD-oriented or prototype-oriented.
3. **Server/admin authorization does not yet satisfy the new stop/uninstall requirement** (RBAC + MFA + audit + uninstall task flow).
4. **Release-grade Linux operational packaging is absent** (systemd units, install/uninstall paths, upgrade flow, bare-metal runbooks).

## Severity legend
- **P0** — must be resolved before V1 implementation can proceed safely
- **P1** — must be resolved during V1 execution before release
- **P2** — should be cleaned up during V1 hardening or documented as a bounded limitation

---

## A. Agent-side Linux compatibility gaps

### A1. Firewall blocking uses `pfctl`, which is not the Linux firewall path
- **Severity:** P0
- **Evidence:** `src/policy.rs:128`
- **Current behavior:** `apply_block_all` shells out to `pfctl`, which is macOS/BSD-specific.
- **Linux risk:** cannot implement network block-all on CentOS/Ubuntu with current code path.
- **Required disposition:** redesign for Linux (`nftables`/`iptables` or explicit V1 limitation with alternative enforcement strategy).

### A2. Network connection collection depends on fragile `netstat` parsing
- **Severity:** P0
- **Evidence:** `src/network.rs:22`
- **Current behavior:** calls `netstat -anv -p tcp` and parses output heuristically.
- **Linux risk:** flags/output shape differ across Linux distributions; output is not stable for CentOS/Ubuntu release support.
- **Required disposition:** replace with Linux-stable source (`ss`, `/proc/net`, or another deterministic collection method).

### A3. Agent runtime persistence paths are prototype-level
- **Severity:** P1
- **Evidence:** `src/main.rs:26` (`/tmp/log.dat`), `src/config.rs:29-44`
- **Current behavior:** local log store uses `/tmp/log.dat`; config path exists but install/runtime layout is not release-defined.
- **Linux risk:** `/tmp` is unsuitable for release persistence and can be cleaned unexpectedly; service-owned paths are undefined.
- **Required disposition:** define Linux runtime layout for binary/config/data/log directories.

### A4. No systemd unit/install/uninstall/upgrade flow exists
- **Severity:** P0
- **Evidence:** repository-wide absence of service/install artifacts; no systemd unit files or scripts exist.
- **Current behavior:** agent is just a binary.
- **Linux risk:** cannot satisfy “systemd 常驻” requirement or release/install docs.
- **Required disposition:** design/install service unit, package layout, upgrade path, uninstall path.

### A5. Stop/uninstall authorization model is absent
- **Severity:** P0
- **Evidence:** no offline authorization-code or uninstall-task implementation in `src/` or `server/`.
- **Current behavior:** no client-side prompt/validation flow; no uninstall task model.
- **Linux risk:** user-required stop/uninstall control cannot be met.
- **Required disposition:** add two paths:
  1. local unique per-client offline authorization code entry
  2. server-issued uninstall task consumed by agent, with self-uninstall and client-data cleanup

### A6. Current lock/unlock feature is not the same as required stop/uninstall control
- **Severity:** P1
- **Evidence:** `src/lock.rs`, `server/main.py:1385-1431`
- **Current behavior:** current policy actions support lock/unlock of home-directory files via RSA/AES flow.
- **Linux risk:** this may be useful later, but it does not satisfy the explicit V1 stop/uninstall requirement.
- **Required disposition:** treat lock/unlock as separate from stop/uninstall authorization; do not confuse the two in design or docs.

### A7. Agent still links remote-shell module in main loop
- **Severity:** P0
- **Evidence:** `src/main.rs:14`, `src/main.rs:79-80`
- **Current behavior:** `remote_shell::ensure_shell(...)` runs in the spawned loop.
- **Linux/V1 risk:** out-of-scope feature remains live in runtime.
- **Required disposition:** remove from main loop for V1 or compile/runtime-gate it off completely.

---

## B. Server-side Linux / release gaps

### B1. Server starts remote-shell TCP service on startup
- **Severity:** P0
- **Evidence:** `server/main.py:572`, `server/main.py:1713-1746`
- **Current behavior:** `startup()` launches `shell_server()`, which binds TCP port `9001` and accepts shell sessions.
- **V1 risk:** deferred feature remains active even if UI is hidden.
- **Required disposition:** disable startup of shell service for V1.

### B2. Policy/API model still includes shell activation path
- **Severity:** P0
- **Evidence:** `server/models.py:16-24`, `server/main.py:605-610`, `server/main.py:1365-1381`
- **Current behavior:** policy model includes `start_shell`; API can issue shell-start tasks.
- **V1 risk:** remote shell remains part of active server contract.
- **Required disposition:** remove or hard-disable shell-start path from V1 policy defaults and admin actions.

### B3. Admin-issued client-behavior operations do not enforce MFA today
- **Severity:** P0
- **Evidence:** `server/main.py:1385-1431` for lock/unlock; no MFA re-check in those handlers
- **Current behavior:** authenticated admin can call client behavior endpoints without an operation-time MFA challenge.
- **Requirement gap:** new stop/uninstall operations must validate role + bound MFA.
- **Required disposition:** add operation-level MFA check for sensitive client behavior actions.

### B4. Stop/uninstall-specific RBAC is not modeled yet
- **Severity:** P0
- **Evidence:** current role model exists (`server/main.py:147-180`) but no dedicated stop/uninstall feature flag or endpoint contract exists.
- **Current behavior:** shell uses `shell_manage`; lock/unlock use `policy_manage`.
- **Requirement gap:** auditors must be unable to operate client behavior, and permission failures must be explicit.
- **Required disposition:** define V1 permission model for stop/uninstall separately and audit it.

### B5. Uninstall task flow is absent from server models/storage
- **Severity:** P0
- **Evidence:** no uninstall fields in `server/models.py`; no uninstall task persistence model in `server/storage.py`.
- **Current behavior:** server can store policy payloads but has no uninstall instruction contract.
- **Requirement gap:** cannot issue background uninstall tasks for agents.
- **Required disposition:** extend task/policy model or add dedicated task table/contract for uninstall authorization and execution tracking.

### B6. Audit coverage exists generically but not yet for the new stop/uninstall semantics
- **Severity:** P1
- **Evidence:** audit framework exists in `server/main.py` and `server/storage.py`, but no stop/uninstall action names yet.
- **Current behavior:** generic actions are logged for existing endpoints.
- **Requirement gap:** must log permission failures, MFA failures, and successful task issuance for client stop/uninstall.
- **Required disposition:** define explicit audit events and log schema usage for this workflow.

### B7. Default cryptographic/runtime configuration is still prototype-grade
- **Severity:** P1
- **Evidence:** `server/main.py:128-129` default shared key falls back to zero bytes when env var absent.
- **Linux/release risk:** insecure default is unacceptable for release docs and production runtime.
- **Required disposition:** require non-default key material and document secure deployment prerequisites.

### B8. Server bare-metal service model is undocumented/unimplemented
- **Severity:** P0
- **Evidence:** no systemd unit, no packaged service wrapper, no deployment scripts.
- **Current behavior:** FastAPI app exists, but release-grade server service lifecycle is undefined.
- **Required disposition:** define process supervision, filesystem layout, environment handling, log handling, and service unit/runbook.

---

## C. Admin UI / UX gaps

### C1. Shell navigation entry is still exposed
- **Severity:** P0
- **Evidence:** `server/static/admin.html:27`, `server/static/assets/admin.js:47`
- **Current behavior:** “远程 Shell” appears as a navigation item for admin.
- **V1 risk:** user-facing scope leakage.
- **Required disposition:** remove or hide shell page from navigation and role visibility map.

### C2. Dedicated shell page is still shipped
- **Severity:** P0
- **Evidence:** `server/static/pages/shell.html`, `server/static/assets/pages/shell.js`
- **Current behavior:** complete shell UI and page init exist.
- **V1 risk:** deferred feature remains discoverable.
- **Required disposition:** remove page from V1 surface or stop serving it entirely.

### C3. Legacy single-page UI still exposes shell controls
- **Severity:** P0
- **Evidence:** `server/static/index.html:141,239-265`
- **Current behavior:** legacy admin page includes shell start/history/search/send/export UI.
- **V1 risk:** even if new nav hides shell, legacy page still leaks it.
- **Required disposition:** remove/hide shell controls from legacy page or deprecate legacy page for V1.

### C4. Shared JS still binds shell workflows and polling
- **Severity:** P0
- **Evidence:** `server/static/app.js:3,32,50-57,779-1172,1415-1422`
- **Current behavior:** shell timers, APIs, search/export/history/send, and start polling are active in shared JS.
- **V1 risk:** shell remains functionally wired.
- **Required disposition:** strip shell bindings and logic from V1 shared JS or feature-gate them off.

### C5. Config UI still exposes `shell_host` / `shell_port`
- **Severity:** P1
- **Evidence:** `server/static/pages/config.html:8-9`, `server/static/index.html:93-94`, `server/static/app.js:123-130,147-148,257-258`
- **Current behavior:** config generation/template UI still asks for shell host/port.
- **V1 risk:** remote shell stays embedded in the product contract despite being deferred.
- **Required disposition:** remove from V1 config UI and download/template flow, or clearly mark as internal/deferred and not required.

### C6. Policy UI default payload still includes shell module
- **Severity:** P0
- **Evidence:** `server/static/app.js:499-504`
- **Current behavior:** default enabled modules include `shell` and `start_shell: false`.
- **V1 risk:** shell remains normalized as a supported module.
- **Required disposition:** remove shell from default enabled modules and policy editor defaults.

### C7. New admin stop/uninstall UX does not exist yet
- **Severity:** P0
- **Evidence:** no UI exists for offline authorization or admin-issued uninstall with MFA challenge.
- **Required disposition:** design separate secure UX for:
  - client-side offline code entry
  - admin-issued stop/uninstall action with explicit permission + MFA prompt + audit result feedback

---

## D. Remote shell touchpoint inventory (must remove/hide/disable for V1)

| Layer | File / Evidence | Current role | V1 disposition |
|---|---|---|---|
| Agent runtime | `src/main.rs:14,79-80` | calls remote shell loop | remove/gate off from main runtime |
| Agent module | `src/remote_shell.rs` | full remote shell implementation | exclude from V1 build/runtime path |
| Agent config | `src/config.rs:15-16,38-39` | `shell_host`, `shell_port` | remove from V1-visible config contract or mark internal/deferred |
| Server startup | `server/main.py:572,1713-1746` | starts shell TCP server | disable in V1 |
| Server policy model | `server/models.py:21` | `start_shell` field | remove/hard-disable for V1 |
| Server admin endpoint | `server/main.py:1365-1381` | start shell task issuance | remove/disable |
| Server shell APIs | `server/main.py:1436-1509` | send/recv/history/export | remove/disable |
| Server role model | `server/main.py:156,179` | `shell_manage` permission/page | remove from V1 role/page map |
| Server admin nav | `server/static/admin.html:27` | shell nav item | hide/remove |
| Server role-based nav JS | `server/static/assets/admin.js:47` | shell page visibility | hide/remove |
| Legacy admin page | `server/static/index.html:141,239-265` | shell controls | remove/hide |
| Dedicated page | `server/static/pages/shell.html` | shell page markup | remove from V1 routes/nav |
| Dedicated page init | `server/static/assets/pages/shell.js` | shell page logic | remove from V1 |
| Shared UI JS | `server/static/app.js` shell bindings and APIs | shell client behavior | strip/gate off |
| Config UI | `server/static/pages/config.html`, `server/static/app.js` | shell host/port fields | remove from V1-facing config flow |
| Default policy UI | `server/static/app.js:499-504` | `shell` enabled module | remove shell from defaults |

---

## E. New requirement gaps for stop/uninstall authorization

### E1. Unique per-client offline authorization code model is absent
- **Severity:** P0
- **Gap:** no code generation, binding, storage, rotation, expiry, or entry UX exists.
- **Design questions for next milestone:**
  - where code is generated and stored
  - whether code is one-time, rotating, time-bound, or revocable
  - how client identity binds to code
  - whether code verification is purely offline or derived from server-provisioned material

### E2. Server-issued uninstall task flow is absent
- **Severity:** P0
- **Gap:** no explicit uninstall task contract, no self-uninstall behavior, no cleanup semantics.
- **Design questions:**
  - task delivery via existing policy loop vs dedicated task queue
  - exact cleanup scope (“all client-related data”) definition
  - idempotency and failure recovery
  - post-uninstall audit visibility

### E3. Operation-time MFA challenge for admin-issued client behavior is absent
- **Severity:** P0
- **Gap:** login MFA exists, but not re-auth for sensitive actions.
- **Design questions:**
  - per-action MFA prompt payload shape
  - TOTP verification timing/window
  - audit event taxonomy for success/failure

### E4. Permission model for client-behavior actions is not explicit enough
- **Severity:** P0
- **Gap:** user requirement says auditors cannot operate client behavior, but stop/uninstall-specific permission semantics are not modeled.
- **Required direction:** define explicit feature/permission mapping for stop/uninstall and document user-visible errors.

---

## F. Recommended execution order after M1
1. **M2-A:** finalize stop/uninstall authorization architecture decision
2. **M2-B:** disable remote shell end-to-end in agent/server/UI/config surfaces
3. **M2-C:** implement Linux service/install/runtime baseline for agent
4. **M2-D:** implement server bare-metal runtime model
5. continue with feature-order milestones already approved in PRD

## Suggested first implementation slices for next milestone
1. Create ADR for stop/uninstall authorization design
2. Create remote-shell removal plan with exact file edits
3. Create Linux service/install layout plan (agent + server)
4. Create test checklist for new RBAC + MFA stop/uninstall flow

## Verification targets for M1 completion
- Linux gap inventory written and versioned
- remote shell touchpoint list explicit enough to drive removal
- authorization gaps explicit enough to support an ADR in next milestone
- no code changes required for M1 completion
