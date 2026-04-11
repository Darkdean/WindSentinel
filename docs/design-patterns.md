# WindSentinel Design Patterns and Implementation Rules

## Release rules
- every substantive change must update affected docs in the same change set
- every releasable version must be managed in git and tagged
- no next substantive milestone proceeds without explicit user confirmation

## Product rules
- V1 is Linux-first
- remote shell is excluded from V1
- anti-tamper in V1 raises attacker cost but does not claim absolute root-proof guarantees
- stop/uninstall authorization must support:
  - unique per-client offline authorization code
  - server-issued uninstall task flow
- admin-issued client stop/uninstall requires:
  - correct role permissions
  - MFA verification
  - audit logging

## Brownfield strategy
- prefer incremental hardening over rewrite
- isolate Linux-incompatible code paths early
- keep packaging/deployment/documentation in lockstep with implementation

## Chosen control authorization pattern
- introduce dedicated `client_control` permission for destructive client behavior operations
- allow `admin` and `operator`; deny `auditor`
- require operation-time MFA for admin-issued stop/uninstall
- use a dedicated control-task model for server-issued uninstall instead of overloading policy
- use a helper-based local uninstall flow so the running agent can be removed safely
