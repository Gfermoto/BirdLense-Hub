# Access control — BirdLense Hub

How optional passwords split **view**, **contribute**, and **admin** capabilities. Default install: **no password** = full local trust.

[Русский](./ACCESS_CONTROL.ru.md)

---

## Configuration keys

```yaml
general:
  # Full access: settings, feeder, system, processor restart
  settings_password: ""

  # Optional: labeling & exports without admin (empty = single-password mode)
  contributor_password: ""
```

**Rules:**

- Both empty → legacy “open hub” (same as today for home labs).
- Only `settings_password` → one tier; unlock behaves as **admin** for all gated actions.
- Both set → `verify-password` returns `role`: **`admin`** (matches `settings_password` first) or **`contributor`**.

---

## Roles

| Role | Typical user | Scope |
|------|--------------|--------|
| **Viewer** | Guest, read-only share | Browse UI, exports that stay public in your policy |
| **Contributor** | Volunteer labeler | Unknowns, species fixes, iNaturalist crop, dataset export, reports |
| **Admin** | Owner | Everything Contributor has **plus** settings, feeder dispense, storage purge, processor restart |

Exact UI gates follow `settings_check_access()` (admin) and `contributor_or_admin_access()` (contributor + admin) in code.

---

## Permission matrix

### Viewer (not unlocked)

| Action | Allowed |
|--------|:-------:|
| Overview, Timeline, Live, species pages | ✅ |
| PDF report, timeline CSV/JSON/eBird (if you expose them without lock) | ✅* |
| Correct species / Unknowns | ❌ |
| iNaturalist export crop | ❌ |
| Feeder **dispense** | ❌ |
| Settings | ❌ |
| System (purge, scan, regenerate, logs…) | ❌ |
| Dataset ZIP export | ❌ |

\*Depends on route-level checks; sensitive exports require Contributor+.

### Contributor

| Action | Allowed |
|--------|:-------:|
| Everything Viewer | ✅ |
| Species correction, Unknowns | ✅ |
| iNaturalist | ✅ |
| Dataset export (where exposed to contributor) | ✅ |
| Feeder dispense | ❌ |
| Settings | ❌ |
| Destructive system actions | ❌ |

### Admin

| Action | Allowed |
|--------|:-------:|
| Everything Contributor | ✅ |
| Feeder `POST /api/ui/feed/dispense` | ✅ |
| Settings | ✅ |
| System tools, restart processor | ✅ |

---

## Session

After successful `POST /api/ui/settings/verify-password`:

```python
session['access_role'] = 'admin' | 'contributor'
session['settings_unlocked'] = True   # admin path; contributor may differ
```

Server checks `access_role` on each gated request.

**MCP:** Valid `Authorization: Bearer <MCP_TOKEN>` can satisfy **admin-level** checks for automation (`settings_check_access()`), so protect tokens like root passwords.

---

## Feeder API

`POST /api/ui/feed/dispense` requires **`settings_check_access()`** → **Admin** (or valid MCP Bearer where implemented). Otherwise **403**.

---

## Security notes

- Passwords in YAML are **plain text** today — prefer restricted file permissions; consider env-based secrets for production.
- Use **HTTPS** when exposing the UI beyond localhost so session cookies are not leaked.
- Processor and MCP use **separate** secrets (`PROCESSOR_SECRET`, `MCP_TOKEN`).

---

## Future ideas (not roadmap commitments)

Community / donation UX (leaderboards, “unlock with support”, badges) is listed under **Future work candidates** in [ROADMAP](./ROADMAP.md). Config hook `general.donate_url` already exists — see [CONFIGURATION](./CONFIGURATION.md).

---

## See also

[CONFIGURATION](./CONFIGURATION.md) · [API](./API.md) · [SECURITY](./SECURITY.md) · [GLOSSARY](./GLOSSARY.md)
