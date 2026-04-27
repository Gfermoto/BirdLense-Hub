# Manual fixes required

| Priority | Area | Finding | Why manual | Recommendation |
|---|---|---|---|---|
| high | CSRF | No explicit CSRF token enforcement found for cookie-auth state-changing UI requests. | Requires auth design decision and API/client contract change. | Add CSRF token endpoint + header middleware, or switch strict production mutations to API key/Bearer/session policy with SameSite documented. |
| medium | UI accessibility | axe: `page-has-heading-one` and `heading-order` on most routes. | Requires component design pass across pages. | Make `PageHelp`/page wrappers render a real `h1`; audit heading hierarchy. |
| medium | Static analysis | Many `except: pass` / broad `except Exception` in low-level processor/web utilities. | Some are intentional best-effort cleanup paths; changing blindly can alter runtime noise/control flow. | Replace with explicit exceptions + debug logging in batches. |
| medium | UI coverage thresholds | UI coverage tool is now installed and script added, but no threshold policy is configured. | Threshold values need team/product agreement. | Add Vitest coverage thresholds for critical UI areas first (routes, auth, API clients). |
| low | Secret scan | Fallback regex scan has many documentation/config-template matches. | Needs curated allowlist or gitleaks config. | Add `.gitleaks.toml` and run real Gitleaks in CI. |
