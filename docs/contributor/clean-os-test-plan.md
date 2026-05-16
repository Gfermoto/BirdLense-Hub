# Clean OS Validation Matrix

## Platforms

- Ubuntu 24.04 LTS (x86_64)
- Debian 12 (x86_64)
- macOS 14+ with Docker Desktop (amd64/arm64 host)

## Scenarios

1. Fresh install
   - `./install.sh`
   - Validate UI, `/api/ui/health`, `/api/ui/readiness`
2. Pull mode
   - `./install.sh --pull`
3. Update mode
   - `./install.sh --update`
4. Backup/restore
   - `./install.sh --backup`
   - `./install.sh --restore --restore-file <archive>`
5. Uninstall
   - `./install.sh --uninstall`
6. Dry run and validation
   - `./install.sh --dry-run --gpu intel --port 8086`

## Acceptance

- All commands return success codes
- No secret values printed to logs
- Restored instance returns same readiness contract
- Uninstall leaves no running BirdLense containers
