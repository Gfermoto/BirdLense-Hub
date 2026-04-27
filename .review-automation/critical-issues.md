# Critical issues

Verdict: no blocker with severity `critical` remained after automatic fixes.

High-priority production risks that must be consciously accepted or resolved before a public deployment:

| Priority | Area | Issue | Required action |
|---|---|---|---|
| high | CSRF / session auth | State-changing UI endpoints rely on session cookies/password/API-key gates; no explicit CSRF token layer was found. | Add CSRF token for cookie-auth mutations or require `BIRDLENSE_UI_API_KEY`/strict auth for automation and keep SameSite hardened at proxy/browser level. |
| high | Production config | `BIRDLENSE_STRICT_API_AUTH` is opt-in; without it, some `/api/ui/*` read endpoints remain public by product design. | Set `BIRDLENSE_ENV=production` and `BIRDLENSE_STRICT_API_AUTH=1` in production. |
| high | UI accessibility | axe reports moderate heading issues (`page-has-heading-one`, `heading-order`) across major routes. | Normalize page headings (`h1` per route; no skipped levels). |
