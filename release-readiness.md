# Release Readiness Checklist

## Security and secrets

- [ ] No hardcoded tokens/passwords in tracked files
- [ ] No private IPs/hosts leaked in user-facing docs
- [ ] `RELEASE_STRATEGY.md` and disclosure path are up to date
- [ ] `gitleaks` scan is clean

## Repository hygiene

- [ ] No benchmark/temp artifacts in repository root
- [ ] `.gitignore` covers local ML/training artifacts
- [ ] `docs/` has EN-first structure and <=50 markdown files

## Build and runtime

- [ ] `bash scripts/public/ci-full-local.sh` passes (или целевой CI gate репозитория)
- [ ] `./install.sh --dry-run --gpu nvidia` passes
- [ ] Fresh install validated on clean Orin

## Deployment

- [ ] `make deploy` completed
- [ ] `verify-stack` health/readiness/status are OK
- [ ] Rollback command tested and documented
