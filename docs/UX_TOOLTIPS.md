# UX Guide: Tooltips and Inline Hints

English only (contributor-facing). This guide defines a consistent pattern for hints in BirdLense Hub UI.

## Principles

- Use **inline text** for critical context required to complete the action.
- Use **tooltip** for optional clarification, side effects, and constraints.
- Do not rely on native HTML `title` attributes for primary UX hints.

## Where to Use What

- **Inline hint (`Typography`/`Alert`)**
  - Preconditions and warnings (auth required, destructive actions).
  - Multi-step operator instructions.
- **Tooltip (`<Tooltip />`)**
  - Icon-only controls and compact action buttons.
  - Extra detail that should not clutter the layout.

## Implementation Rules

- Wrap disabled buttons with `<Tooltip><span><Button .../></span></Tooltip>`.
- Keep tooltip text short and action-specific.
- Reuse i18n keys for repeatable hints.
- For dangerous actions, keep confirmation dialogs even if tooltip exists.

## Applied on key screens

- `Library`: unified hints via `Tooltip` for dataset maintenance actions.
- `Unknowns`: unified action hints for apply/confirm controls.
