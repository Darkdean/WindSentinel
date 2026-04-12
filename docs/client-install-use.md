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
