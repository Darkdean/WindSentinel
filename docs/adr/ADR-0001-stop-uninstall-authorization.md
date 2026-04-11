# ADR-0001: Stop / Uninstall Authorization Mechanism for Linux V1

- Status: Accepted (design baseline for M2-A)
- Date: 2026-04-11
- Scope: Linux V1 agent/server/admin design only
- Related specs:
  - `.omx/specs/deep-interview-v1-linux-security-platform.md` (local workspace reference)
  - `docs/design-patterns.md`
  - `docs/feature-matrix.md`

## Context
WindSentinel V1 must satisfy all of the following at the same time:
1. Agent runs as a Linux `systemd` resident service.
2. Agent should resist unauthorized stop / disable / uninstall attempts as much as practical in V1.
3. Local stop / uninstall must be possible with an **offline authorization code**, and that code must be **different for each client**.
4. The web admin must also be able to issue an **uninstall task** that the agent fetches and executes automatically.
5. Admin-issued client behavior operations must enforce **RBAC + MFA**.
6. Auditors must **not** be able to perform client behavior operations.
7. Permission failures, MFA failures, task issuance, task delivery, and client execution results must be visible in audit/log views.
8. Remote shell is explicitly out of scope for V1 and must not be reused as the control channel.

The current codebase has some relevant pieces already:
- login MFA exists on the server
- audit logging exists on the server
- policy fetch/apply loop exists on the agent
- lock/unlock actions exist but are not equivalent to stop/uninstall control

It does **not** yet have:
- offline authorization-code design
- uninstall task model
- operation-time MFA for client behavior actions
- explicit stop/uninstall RBAC model
- self-uninstall helper flow

## Decision Drivers
1. Must work on CentOS 7/8/9+ and Ubuntu 20/22/24.
2. Must support offline local authorization without needing live server access.
3. Must support server-issued uninstall as a queued admin action.
4. Must leave a strong audit trail.
5. Must fit the current Rust agent + FastAPI server + static UI architecture without a rewrite.
6. Must remain realistic for user-space Linux V1; absolute root-proof guarantees are out of scope.

## Options Considered

### Option A — Reuse policy payload only
Put stop/uninstall inside the existing policy response and let the agent execute it directly.
- Pros: least new API surface
- Cons: poor one-shot semantics, weak auditing granularity, mixes durable policy with destructive control tasks, awkward retries/acknowledgements

### Option B — Separate control-task channel + local offline code (**chosen**)
Use a dedicated control-task model for admin-issued stop/uninstall, while using a separate local offline-code path for interactive client-side authorization.
- Pros: clear semantics, auditable lifecycle, easier retries/acks, clean separation from normal policy, supports both online and offline flows
- Cons: adds new server models/endpoints and agent task-processing logic

### Option C — Web-only authorization, no local offline path
Require all stop/uninstall to come from the server.
- Pros: simpler central control
- Cons: violates the user requirement for offline local authorization

## Decision
Choose **Option B**.

WindSentinel V1 will support **two distinct authorization paths**:
1. **Local offline authorization-code path** for stop/uninstall initiated on the client machine.
2. **Server-issued uninstall-task path** for uninstall initiated from the web admin.

These two paths share the same security principles:
- explicit authorization intent
- narrow allowed actions
- one operation at a time
- auditable result trail
- no reuse of remote shell machinery

## High-Level Architecture

### 1. Local offline authorization-code path
- Each agent gets a **unique offline authorization code**.
- The code is generated at provisioning time and is bound to the agent identity.
- The agent stores only a **slow hash** of the code locally in a protected root-owned file.
- The server stores the hash and metadata, not the plaintext code.
- Local stop/uninstall uses a dedicated client control utility (for example `windsentinelctl`) that prompts for the code.
- On successful verification, the control utility creates a short-lived local authorization receipt that allows either:
  - an authorized stop, or
  - an authorized uninstall helper run.

### 2. Server-issued uninstall-task path
- The server creates a dedicated **control task** of type `uninstall`.
- The task is created only after RBAC and MFA checks pass.
- The agent fetches the task through a dedicated control-task API, not through remote shell.
- The agent acknowledges receipt, begins uninstall, spawns a cleanup helper, and reports success/failure best-effort before final removal.

### 3. Shared control principles
- Stop and uninstall are modeled as **client control actions**, separate from normal policy and separate from lock/unlock.
- Sensitive client control actions must always produce audit records.
- Control actions must be idempotent where possible.
- A queued uninstall task survives temporary agent offline periods until expiry or completion.

## Detailed Design

## A. Offline authorization code

### Format
- Human-enterable recovery-style code
- Recommended format: `WS-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX`
- Character set: uppercase base32-like alphabet without ambiguous characters
- Entropy target: at least 100 bits

### Generation
- Generated server-side when an agent package/config is created for a new agent, or when the code is rotated.
- Generated using secure randomness.
- Displayed/exported to the administrator **once** at provisioning or rotation time.

### Storage
#### Server side
Store:
- `agent_id`
- `code_hash`
- `code_salt`
- `code_version`
- `created_at`
- `rotated_at`
- `rotated_by`
- `status` (`active`, `rotated`, `revoked`)

Do **not** store plaintext code after issuance.

#### Client side
Store in a root-owned protected local file:
- `agent_id`
- `code_hash`
- `code_salt`
- `code_version`
- optional metadata (created_at, rotated_at)

### Verification model
- Local verification is fully offline.
- Entered code is hashed locally with stored salt and compared to the stored hash.
- Because the server is not required, this path continues to work even when the server is unreachable.

### Rotation
- Admin can rotate/regenerate the code from the server/admin workflow later.
- Rotation invalidates the previous version.
- Rotations must be audited.

## B. Local stop/uninstall flow

### Command surface
Introduce a dedicated local control utility, e.g.:
- `windsentinelctl stop`
- `windsentinelctl uninstall`

### Behavior
1. Prompt for offline authorization code.
2. Verify locally against the stored hash.
3. If invalid:
   - deny action
   - log locally
   - if connected, best-effort send an audit event to server later
4. If valid:
   - create a short-lived authorization receipt file with:
     - action (`stop` or `uninstall`)
     - agent_id
     - nonce
     - expiry (short TTL, e.g. 60 seconds)
     - code_version
   - invoke stop/uninstall helper flow

### Why receipt-based flow is chosen
This prevents the service itself or uninstall helper from depending on repeated code prompts and gives a clean one-time authorization boundary.

## C. Agent residency / unauthorized stop protection

### V1 control goals
- make casual `systemctl stop` / `disable` / ordinary uninstall paths fail or auto-recover where practical
- require explicit authorized flow for legitimate stop/uninstall
- raise cost for privileged tampering without claiming impossible guarantees

### Planned Linux controls
- `systemd` unit with restart behavior suitable for tamper resistance
- `RefuseManualStop=yes` where compatible with the chosen service model
- unit hardening and restrictive file ownership/permissions
- helper-based authorized maintenance flow
- explicit maintenance/uninstall receipt with short TTL

### Authorized stop behavior
- stop helper checks valid local authorization receipt
- helper places the service into maintenance/authorized-stop mode
- then it stops/disables service without the normal auto-restart path fighting the action

## D. Server-issued uninstall task design

### Why tasks instead of policy
Uninstall is a one-time destructive control action, not a standing policy preference.
It needs:
- explicit issuer identity
- MFA confirmation state
- lifecycle status
- delivery and completion timestamps
- audit correlation

That makes a dedicated task model more appropriate than overloading the policy payload.

### Proposed server data model
Create a new table, for example `agent_control_tasks`:
- `id`
- `agent_id`
- `task_type` (`uninstall` for V1; `stop` reserved/future)
- `status` (`queued`, `delivered`, `acknowledged`, `running`, `completed`, `failed`, `expired`, `cancelled`)
- `payload_json`
- `created_at`
- `created_by`
- `created_role`
- `mfa_verified_at`
- `expires_at`
- `delivered_at`
- `started_at`
- `finished_at`
- `result_code`
- `result_message`
- `audit_correlation_id`

### Proposed API surface
#### Admin-side
- `POST /admin/agents/{agent_id}/control/uninstall`
  - body includes `mfa_code` and optional `reason`
  - creates queued uninstall task after checks pass

#### Agent-side
- `GET /api/v1/control-tasks/next?agent_id=...`
  - returns next pending task for the agent, if any
- `POST /api/v1/control-tasks/{task_id}/ack`
  - agent posts status transitions / result messages

### Delivery semantics
- uninstall task remains queued until delivered or expired
- agent polls normally and receives the task when online
- task execution is idempotent from the server perspective
- if the agent disappears mid-uninstall, the last ack/result is preserved; missing final ack is still auditable as incomplete/unknown

## E. Admin-side RBAC and MFA

### Permission model
Introduce a dedicated feature permission such as `client_control`.

#### Role mapping for V1
- `admin`: allowed
- `operator`: allowed
- `auditor`: denied

This aligns with the current operator/admin management posture while honoring the explicit user requirement that auditors cannot operate client behavior.

### Enforcement order
When admin requests uninstall:
1. authenticate user
2. verify role/permission (`client_control`)
3. if permission fails: return explicit **no permission** response and audit denial
4. verify user has bound MFA
5. verify submitted TOTP MFA code
6. if MFA fails: return explicit **verification code error** response and audit denial
7. if all checks pass: create control task and audit success

### Why operation-time MFA is required
Login-time MFA alone is not enough for destructive client control. V1 will require re-authentication for the operation itself.

## F. Audit design

### Required audit events
At minimum:
- `client_control_permission_denied`
- `client_control_mfa_missing`
- `client_control_mfa_invalid`
- `client_uninstall_task_created`
- `client_uninstall_task_delivered`
- `client_uninstall_started`
- `client_uninstall_completed`
- `client_uninstall_failed`
- `offline_auth_code_rotated`
- `offline_local_stop_authorized`
- `offline_local_uninstall_authorized`
- `offline_local_authorization_failed`

### Required audit fields
Reuse the existing audit log model where possible, ensuring these are populated:
- actor username
- actor role
- target agent_id
- action
- result
- timestamp
- request path/method
- IP / user-agent where applicable
- correlation id linking request -> task -> agent outcome

### Visibility requirement
These events must be visible in the existing web audit/log views.

## G. Client self-uninstall and cleanup design

### Why a helper is required
A running agent process cannot reliably delete all of its own binaries/unit files while it is still executing.
Therefore V1 uses a separate root-owned helper, for example:
- `windsentinel-uninstall-helper`

### Self-uninstall sequence
1. agent receives uninstall task
2. agent writes local uninstall manifest
3. agent acknowledges task start
4. agent launches uninstall helper
5. helper:
   - stops service in authorized mode
   - disables service
   - removes service unit
   - removes binary/control utility/helper binaries
   - removes config/data/log directories defined as WindSentinel-owned
   - removes temporary manifests/receipts
6. helper performs best-effort final status reporting before removing remaining artifacts, if possible
7. server marks task completed/failed/unknown based on final evidence

### Cleanup scope
The phrase “all client-related data” is defined in V1 as:
- WindSentinel binary directory
- WindSentinel config directory
- WindSentinel data directory
- WindSentinel logs directory
- systemd unit file(s)
- helper manifests / temporary authorization receipts

It does **not** mean deleting unrelated host files.

### Server-side post-uninstall state
Server should retain:
- audit logs
- completed task history
- agent record marked as uninstalled / inactive / last_seen retired

The server should **not** silently erase server-side compliance history.

## H. Error semantics

### Permission failure
- HTTP/UI result: explicit “无权限” / permission denied
- audit: denial event recorded

### MFA failure
- HTTP/UI result: explicit “验证码错误” / invalid MFA code
- audit: MFA failure recorded

### Agent offline when task issued
- HTTP/UI result: task queued successfully
- audit: task created event recorded
- later events: delivered/completed/expired recorded as they occur

### Offline local code failure
- local result: invalid authorization code
- local log entry required
- server audit: best-effort deferred sync if connectivity later exists

## I. Security boundaries for V1
- This design raises the cost of unauthorized stop/uninstall.
- It does not claim absolute root-proof protection.
- Offline code secrecy becomes a critical operational secret and must be documented as such.
- Server-issued uninstall is highly sensitive and therefore requires both RBAC and operation-time MFA.

## J. Consequences
### Positive
- satisfies both required authorization paths
- keeps destructive actions auditable
- fits current architecture without a rewrite
- cleanly separates durable policy from destructive control tasks

### Negative
- introduces new task model and helper binary/service complexity
- requires new UX on both admin and client sides
- requires careful idempotency and cleanup design

## K. Follow-up implementation order
1. Remove/disable remote shell end-to-end for V1
2. Add `client_control` permission model and admin MFA challenge path
3. Add offline-code generation/storage/rotation model
4. Add control-task storage and APIs
5. Add client control utility and helper-based stop/uninstall flow
6. Add audit/log view support for new actions
7. Add docs and tests for both authorization paths

## L. Rejected design details
- Reusing remote shell for uninstall control | rejected because remote shell is out of scope for V1
- Modeling uninstall as ordinary policy state | rejected because destructive tasks need separate lifecycle and audit semantics
- Server-only uninstall authorization | rejected because offline local authorization is a hard requirement
- Plaintext local code storage | rejected because it weakens the offline secret boundary
