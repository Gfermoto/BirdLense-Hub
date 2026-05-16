# UI copy: tone and review (operators, not engineers)

[Русский](./UI_COPY_STYLE.ru.md)

Use this checklist when writing or editing user-visible strings in the web UI (i18n under `app/ui/locales/`).

## Audience

- Primary reader: **station owner / operator** who configures the hub from the browser.
- Secondary: contributor with limited permissions.
- Avoid assuming knowledge of internal module names, YAML keys, or log phrases unless the text is explicitly in **Service** / diagnostics.

## Tone

- **Short, imperative labels**; helper text explains *what happens*, not how the code is structured.
- Prefer **plain consequences** (“Recording won’t start”) over internal causes (“ByteTrack returned 0 tracks”).
- One idea per sentence in helper text; avoid stacked caveats in the same field.

## What to avoid in Station (`/settings`)

- Raw dotted config keys (`triggers.frigate.*`) in labels — use human names; put keys only in docs or YAML export help.
- “Expert / legacy / Frigate-only” jargon unless the control is behind an explicit advanced or service surface.
- Duplicating the same explanation in three places (hint, alert, doc) — pick **one** primary place.

## Review

- Product-facing copy: **UX + language editor** pass for `en` / `ru` (and `zh` when touched).
- Technical accuracy: cross-check against `default_config.yaml` and OpenAPI where the field affects API behaviour.

## Machine-readable settings inventory

Every leaf key in `app/app_config/default_config.yaml` must either appear as `form.Field name="..."` under `app/ui/src/pages/Settings/` or be explicitly allowlisted in `scripts/check-settings-ui-coverage.py` (with category and rationale). Run:

```bash
python3 scripts/check-settings-ui-coverage.py
```

See also: [UI settings map](./UI_SETTINGS_MAP.md) · [RU](./UI_SETTINGS_MAP.ru.md). Epic closure notes: [BirdLense-Hub#421](https://github.com/Gfermoto/BirdLense-Hub/issues/421).
