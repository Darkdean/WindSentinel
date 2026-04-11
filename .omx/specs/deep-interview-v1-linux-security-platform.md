# Execution-Ready Spec — V1 Linux Security Platform

## Metadata
- Slug: v1-linux-security-platform
- Profile: standard
- Rounds: 9
- Final ambiguity: 0.10
- Threshold: 0.20
- Context type: brownfield
- Context snapshot: `.omx/context/repo-understanding-20260411T075638Z.md`
- Transcript summary: `.omx/interviews/v1-linux-security-platform-20260411T110118Z.md`

## Clarity Breakdown
| Dimension | Score |
|---|---:|
| Intent | 0.82 |
| Outcome | 0.97 |
| Scope | 1.00 |
| Constraints | 1.00 |
| Success Criteria | 0.92 |
| Context | 0.92 |

Readiness gates:
- Non-goals: resolved
- Decision Boundaries: resolved
- Pressure pass: complete

## Intent (Why)
Build a first release of the existing security product so it is actually usable on Linux for the user's management workflow, with release discipline, synchronized documentation, and versioned delivery through git/GitHub.

## Desired Outcome
Deliver a V1 Linux-capable release in which:
- the Agent runs on Linux as a persistent systemd service,
- the Server and Admin UI can be deployed on Linux bare metal,
- the full required management surface works end-to-end,
- documentation is complete and synchronized with implementation,
- the release is versioned, tagged, and ready to push/manage in git/GitHub.

## In Scope
### Platforms
- Linux Agent support for CentOS 7/8/9+ and Ubuntu 20/22/24
- Linux architectures: x86_64 and ARM (`aarch64`)
- Server/Admin bare-metal deployment on Linux
- Docker Compose deployment artifact produced after bare-metal path is complete

### Product areas required in V1
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

### Core delivery expectations
- Agent + Server + Admin UI all usable
- Design, implementation, debugging, synchronized documentation, versioning, and tagging
- Release-oriented git workflow

## Out-of-Scope / Non-goals
- Remote shell is explicitly deferred from V1
- Absolute root-proof anti-tamper is **not** promised for V1

## Decision Boundaries (What OMX may decide without confirmation)
OMX may not start substantive next-step work without explicit user confirmation.
OMX should, when unclear, bring referenceable implementable solutions for discussion before implementation.
OMX must keep related docs updated whenever files/architecture/code change.
OMX may treat the following as fixed unless the user later changes them: GitHub remote `https://github.com/Darkdean/WindSentinel.git`, ARM target `aarch64`, and the user-defined versioning policy.

## Constraints
- Use git for release/version management
- Manage each release-ready version and push to remote GitHub (`https://github.com/Darkdean/WindSentinel.git`)
- Versioning policy: initialize at `v1.0`; without overall architecture changes, every 2 new requirements increments one minor version (example: `v1.1`)
- Maintain and sync all related documentation, including:
  - client installation/use docs
  - server installation/use docs
  - admin UI installation/use docs
  - architecture docs (network architecture, database architecture, design patterns, etc.)
  - feature docs
  - code explanation docs
- Include documentation changes in git
- Do not proceed to substantive next work without explicit user confirmation unless that step category is explicitly waived
- If a requirement is unclear, research current implementable solutions and discuss before implementation
- Agent anti-tamper goal for V1: raise the cost of root-level disable/uninstall as much as practical, then iterate later
- Agent stop/uninstall authorization must support a unique per-client offline authorization code entered locally at the client prompt
- Agent stop/uninstall authorization must also support server-issued uninstall instructions fetched by the agent, triggering self-uninstall and cleanup of client-related data
- Admin-side stop/uninstall actions must enforce role permissions and MFA validation: auditors cannot operate client behavior; wrong MFA must fail explicitly; successful or attempted command issuance must be auditable in web log/audit views

## Testable Acceptance Criteria
A release is acceptable when all of the following hold:
1. The client can be used normally and fulfills current-version feature requirements.
2. The server can be used normally and fulfills current-version feature requirements.
3. The admin UI can be used normally and fulfills current-version feature requirements.
4. The required core scope has been designed, implemented, debugged, documented, versioned, and tagged.
5. Bare-metal deployment steps exist and are complete for server/admin.
6. A Docker Compose YAML file exists after bare-metal delivery, with valid YAML syntax and complete deployment steps documented.
7. Agent stop/uninstall supports both local offline authorization-code flow and server-issued uninstall flow.
8. Admin-issued stop/uninstall operations enforce role permissions and bound-user MFA, and corresponding operation logs are visible in web audit/log views.
9. Release docs and architecture/code/feature docs stay synchronized with any implementation changes.

## Assumptions Exposed + Resolutions
- Assumption: Linux “cannot be forcibly stopped” might mean absolute root-proof protection.
  - Resolution: user accepted a more realistic V1 boundary — maximize resistance / raise root tampering cost, but iterate later for stronger protection.
- Assumption: some management modules might be deferrable.
  - Resolution: user confirmed all 10 management areas are required in full for V1.

## Pressure-Pass Findings
- Revisited earlier “Linux client should run perfectly” requirement with a feasibility challenge around anti-tamper.
- Brownfield + official-doc evidence showed a pure user-space Linux agent cannot guarantee absolute root-proof anti-tamper.
- Requirement was refined from an absolute claim to a V1-realistic target: strengthen resistance and raise attack cost against root-level tampering.

## Brownfield Evidence vs Inference Notes
### Evidence from repository
- Rust Agent entrypoint and loops: `src/main.rs`
- Policy fetch/apply and local action hooks: `src/policy.rs`
- Remote shell path exists today but is deferrable: `src/remote_shell.rs`, `server/main.py`
- Server API/admin logic concentrated in `server/main.py`
- Persistence primarily via SQLite: `server/storage.py`
- Admin UI static assets/pages in `server/static/`

### External evidence used for feasibility boundary
- systemd unit/service controls can resist common manual stop/disable patterns but do not create absolute root-proof guarantees in user space.
- Linux capability and privilege model means a sufficiently privileged actor can still bypass many user-space protections.

References:
- https://www.freedesktop.org/software/systemd/man/latest/systemd.unit.html
- https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html
- https://man7.org/linux/man-pages/man7/capabilities.7.html

## Technical Context Findings
- Current codebase is already a brownfield prototype with:
  - Rust telemetry/agent loops
  - Python FastAPI management server
  - static admin UI
  - policy-driven control flow
  - SQLite-backed admin/state storage
- Existing remote shell feature exists in code but should be excluded from V1 implementation scope.
- Existing code appears cross-platform-biased in places, but Linux systemd residency and anti-tamper hardening will likely require platform-specific work across installer/service/unit/uninstall flows.

## Delivery Ordering
Implement/verify the ten management areas in this order:
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

## Full/Condensed Transcript
See: `.omx/interviews/v1-linux-security-platform-20260411T110118Z.md`

## Additional clarified requirements
- GitHub remote repository: `https://github.com/Darkdean/WindSentinel.git`
- Versioning: start at `v1.0`; if overall architecture is unchanged, every 2 new requirements increments the minor version
- Linux support matrix: CentOS 7/8/9+ and Ubuntu 20/22/24
- ARM target: `aarch64`
- Agent authorization requirements:
  - local offline authorization code flow, unique per client
  - server-issued uninstall task that causes agent self-uninstall and client-data cleanup
- Admin authorization requirements for client stop/uninstall:
  - auditors cannot perform client-behavior operations
  - bound MFA challenge required
  - insufficient role => permission error
  - wrong MFA => verification error
  - task issuance and related actions must be recorded in audit/log views
