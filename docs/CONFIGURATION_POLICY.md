# Configuration Policy

[Русский](./CONFIGURATION_POLICY.ru.md)

This document is the policy layer for BirdLense Hub configuration. The key
reference stays in [CONFIGURATION](./CONFIGURATION.md).

## Sources of Truth

| Source | Owns | Persistence | Notes |
| --- | --- | --- | --- |
| `app/app_config/default_config.yaml` | Shipped defaults and documented key shape | Git | New non-breaking defaults start here. |
| `app/app_config/user_config.yaml` | Local operator overrides | Runtime file, not committed | Recursively merged over defaults. Missing keys keep defaults; empty strings are values. |
| `app/.env.example` and deployment env | Secrets and runtime-only deployment knobs | Host/container env | `BIRDLENSE_*` secret overlays replace merged config in memory without writing to YAML. |
| `app/web/config.py` | Flask/SQLAlchemy/CORS process settings | Env-derived Python config | Validated at import/startup where unsafe defaults would be dangerous. |
| `app/web/routes/ui_settings_routes.py` + `services/settings_patch_service.py` | Mutating Settings API | Writes `user_config.yaml` through `AppConfig.save()` | PATCH must validate the merged candidate before save. |
| `app/processor/src/*` | Runtime consumers | Reads merged config from `app_config` | Processor should not invent new config shapes without defaults and docs. |

## Precedence

1. Load `default_config.yaml`.
2. Load and recursively merge `user_config.yaml`.
3. Apply migrations for legacy user keys where a safe automatic mapping exists.
4. Apply runtime secret/env overlays.
5. Validate the merged config shape.

The web Settings PATCH path validates the candidate merged config before saving.
Example operator error:

```json
{
  "error": "Validation failed",
  "issues": ["top-level key 'mqtt' must be a mapping or null, got str"]
}
```

## Validation Policy

- Reject top-level sections that are not mappings or `null`.
- Reject mutating API payloads before writing `user_config.yaml`.
- Keep startup validation soft by default for old installations; use
  `BIRDLENSE_STRICT_CONFIG=1` when operators want fail-fast startup.
- Add semantic validation incrementally for high-risk keys: secrets, processor
  thresholds, storage paths, and external-service URLs.

## Compatibility Policy

- Non-breaking: adding a key with a default, accepting a legacy alias, widening an
  enum, or clamping a legacy unsafe threshold with a warning.
- Breaking: removing a key, changing its type, narrowing an enum, or changing
  default behavior for existing persisted YAML.
- Breaking changes require release notes and, where possible, a migration in
  `app/app_config/app_config.py`.
- Deprecated keys should remain readable for at least one release cycle unless
  they create a security or data-loss risk.
