# WindSentinel Client Install and Use Guide

## Status
M0 baseline skeleton. This document must be completed and kept in sync during implementation.

## Planned scope
- supported Linux distributions and architectures
- package / binary installation path
- configuration file path and format
- systemd service installation / enable / start / restart / status
- upgrade flow
- authorized stop flow
- authorized uninstall flow
- offline authorization-code prompt flow
- troubleshooting and log collection

## Current known gaps
- Linux installer/service flow not yet implemented
- local stop/uninstall command path is implemented in the agent binary, but full install/runbook documentation is still pending
- server-issued control-task consumption and helper-based uninstall are implemented in code, but still need end-to-end deployment validation
- remote shell is out of scope for V1 and removed from the V1-visible client config/runtime surface
