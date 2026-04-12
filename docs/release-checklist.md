# WindSentinel Release Checklist

## Release line
- Initial target release: `v1.0`
- Minor version rule: if overall architecture is unchanged, every 2 new requirements increments the minor version

## Mandatory gates
- [ ] client meets current version functional requirements
- [ ] server meets current version functional requirements
- [ ] admin UI meets current version functional requirements
- [ ] all V1 required feature areas verified
- [ ] remote shell absent / inaccessible in V1
- [ ] Linux deployment docs validated
- [ ] macOS current-target install/uninstall artifacts validated
- [ ] code docs and architecture docs updated
- [ ] version/tag prepared in git
- [ ] release notes drafted
- [ ] audit coverage validated for security-sensitive admin operations

## Evidence to attach
- build outputs
- deployment logs
- service status outputs
- screenshots / API traces for critical workflows
- documentation validation notes
