# Release Readiness Checklist

## Security and secrets

- [ ] No hardcoded tokens/passwords in tracked files
- [ ] No private IPs/hosts leaked in user-facing docs
- [ ] `SECURITY.md` and disclosure path are up to date
- [ ] `gitleaks` scan is clean

## Repository hygiene

- [ ] No benchmark/temp artifacts in repository root
- [ ] `.gitignore` covers local ML/training artifacts
- [ ] `docs/` has EN-first structure and <=50 markdown files

## Build and runtime

- [ ] `make ci-local` passes
- [ ] `make verify-prod-env` passes with deployment `.env`
- [ ] `./install.sh --dry-run` passes
- [ ] Fresh install validated on clean machine

## Deployment

- [ ] `make deploy` completed
- [ ] `verify-stack` health/readiness/status are OK
- [ ] Rollback command tested and documented
