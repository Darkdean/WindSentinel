# WindSentinel Client Install and Use Guide

## Status
M0 baseline skeleton. This document must be completed and kept in sync during implementation.

## Planned scope
- current delivery target: macOS 26 on aarch64
- later delivery target: Linux distributions and architectures documented in the roadmap
- package / binary installation path
- configuration file path and format
- launchd / service installation and runtime status for the current macOS target
- upgrade flow
- authorized stop flow
- authorized uninstall flow
- offline authorization-code prompt flow
- troubleshooting and log collection

## Current known gaps
- macOS service installation/runbook is not yet finished
- local stop/uninstall command path is implemented in the agent binary, but full install/runbook documentation is still pending
- server-issued control-task consumption and helper-based uninstall are implemented in code, but still need end-to-end deployment validation
- remote shell is out of scope for V1 and removed from the V1-visible client config/runtime surface


## Current macOS 26 / aarch64 install path
### Files created for packaging
- `packaging/macos/com.windsentinel.agent.plist`
- `packaging/macos/install_agent.sh`
- `packaging/macos/uninstall_agent.sh`

### Intended install layout
- binary: `/Library/WindSentinel/bin/windsentinel_agent`
- config: `/Library/WindSentinel/config/config.json`
- logs: `/Library/WindSentinel/logs/`
- state: `/Library/WindSentinel/state/`
- launchd plist: `/Library/LaunchDaemons/com.windsentinel.agent.plist`

### launchd environment wiring
The macOS install path now injects:
- `WINDSENTINEL_AGENT_CONFIG_PATH=/Library/WindSentinel/config/config.json`
- `WINDSENTINEL_AGENT_STATE_DIR=/Library/WindSentinel/state`
- `WINDSENTINEL_CONFIG_VERIFY_KEY_B64=<derived from signed config>`

This is required so the formally installed launchd service reads the installed signed config instead of falling back to the per-user debug path.

### Basic install flow
```bash
sudo packaging/macos/install_agent.sh <agent-binary> <signed-config.json>
```

### Basic uninstall flow
```bash
sudo packaging/macos/uninstall_agent.sh
```

### Notes
- current formalization target is macOS 26 on aarch64
- launchd packaging is now scaffolded, but a full installer-package workflow is still future work
- local control commands and server-issued control tasks still rely on the configured control metadata in the signed config
