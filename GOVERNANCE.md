# Governance

## Maintainer model

BirdLense Hub is maintainer-led. Core maintainers decide roadmap, review policy, and release timing.

## Decision process

1. Proposals start as GitHub Issue.
2. Significant architecture changes require ADR-style issue notes and explicit acceptance criteria.
3. Merge to `main` only through PR with green CI and release gate checks.

## Release policy

- Day-to-day work: `dev`
- Release integration: PR `dev -> main`
- Emergency fixes in `main` must be merged back into `dev` immediately.

## Backward compatibility

Public API and user-facing CLI/scripts are changed with deprecation notes and at least one release transition window where feasible.
