# BirdLense Hub — open-source release preparation

**Goal:** Documentation and repo hygiene for a credible public release. Focus: **security**, **no credential leaks**, **clear paths for users and contributors**.

**Plan version:** 1.1 · March 2026

[Русский](./OPEN_SOURCE_PREP.ru.md)

---

## 1. Audit summary

### 1.1 Documentation

| Area | Files | Status (March 2026) |
|------|-------|---------------------|
| **Root** | `README.md`, `README.ru.md`, `CHANGELOG.md`, `SECURITY.md` | EN primary root README; RU mirror |
| **`docs/`** | Hub [README](./README.md), [OVERVIEW](./OVERVIEW.md), [SITE_MAP](./SITE_MAP.md), guides | EN `.md` + `*.ru.md` for major guides; see [I18N_STATUS](./I18N_STATUS.md) |
| **`docs/archive/`** | Historical notes | Trimmed; optional reading |
| **Other** | `article/`, `scripts/datasets/README` | Spot-check relevance |

### 1.2 Leaks (use placeholders in docs)

| Issue | Example fix |
|-------|-------------|
| Real LAN IPs, SSH host aliases, `/root/...` paths | `YOUR_HOST`, `YOUR_SSH_HOST`, `YOUR_REMOTE_DIR` |
| Tokens in examples | `your-secret-token`, `your-api-key` |
| `user_config.yaml.bak` committed | `.gitignore` |

`app/.env.example` may keep **example** private IPs. Cursor-only rules (e.g. deploy) stay local — not in repo.

### 1.3 Security themes (from [docs/SECURITY](./SECURITY.md))

- Prefer **env** over YAML for secrets in production.
- OpenAPI: mark sensitive fields (`x-sensitive` where applicable).
- Rate limiting for `verify-password` — **implemented** (5 fails / 60 s per IP, 429 + `Retry-After`); see [ACCESS_CONTROL](./ACCESS_CONTROL.md).
- **Settings password** recommended for any internet-exposed install.

---

## 2. Workstreams

### Phase 1 — Security & leaks

| # | Task | Done |
|---|------|:----:|
| 1.1 | `.gitignore`: `user_config.yaml.bak`, `*.bak` under `app_config` | [x] |
| 1.2 | Placeholders in docs (no real hosts/paths in examples) | [x] |
| 1.3 | Git history scan for real tokens (maintainer) | [ ] |
| 1.4 | Root `SECURITY.md` (GitHub policy) | [x] |
| 1.5 | `docs/SECURITY.md` analysis (EN) + `SECURITY.ru.md` | [x] |

### Phase 2 — Structure

| # | Task | Done |
|---|------|:----:|
| 2.1 | Root `README.md` EN, concise | [x] |
| 2.2 | `README.ru.md`; `app/README.md` + `app/README.ru.md`; `SHORT_DESCRIPTION*.md` | [x] |
| 2.3 | `docs/README.md` hub (Run / Integrate / Build) | [x] |
| 2.4 | `CONTRIBUTING.md` | [x] |
| 2.5 | `CODE_OF_CONDUCT.md` | [x] |
| 2.6 | LICENSE review (code vs image) | [ ] |

### Phase 3 — Content (technical writer)

| # | Task | Done |
|---|------|:----:|
| 3.0 | `docs/archive/` cleanup | [x] |
| 3.1 | Instructional tone: INSTALL, SCENARIOS, CONFIGURATION | [x] |
| 3.2 | Unified placeholders | [x] |
| 3.3 | Hugging Face `gfermoto/*` links — public; keep | [x] |
| 3.4 | `deploy.local.sh.example` generic | [x] |
| 3.5 | Document `deploy.local.sh` as **local secret file**, never commit | [x] |

### Phase 4 — Infra & final

| # | Task | Done |
|---|------|:----:|
| 4.1 | GitHub: Security Advisories, Dependabot | [x] |
| 4.2 | Repo description, topics, website URL | [ ] |
| 4.3 | `make test-web`, `make test-e2e` green | [ ] |
| 4.4 | Link check (internal + external) | [ ] |

---

## 3. Placeholders

| Kind | Placeholder |
|------|-------------|
| Host | `YOUR_HOST`, `localhost` |
| Remote dir | `YOUR_REMOTE_DIR` |
| SSH alias | `YOUR_SSH_HOST` |
| Token | `your-secret-token` |
| API key | `your-api-key` |
| Public URL | `https://your-birdlense.example.com` |

---

## 4. Must-not-commit

Verify `.gitignore` includes at least:

```
app/app_config/user_config.yaml.bak
scripts/deploy.local.sh
.env
*.pem
**/secrets/
```

---

## 5. Roles

| Role | Scope |
|------|--------|
| **Security** | Phase 1, secret review |
| **Technical writer** | IA, tone, dedup, cross-links |
| **Translator** | RU mirrors after structure is stable |
| **DevOps** | Phase 4, CI |
| **Maintainer** | Release sign-off |

**Order:** structure (EN) → review → translate → ship.

---

## 6. Release readiness checklist

- [ ] No install-specific IPs/hostnames/paths in **published** docs
- [ ] No real tokens in repo or docs
- [ ] EN README understandable globally
- [ ] `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, root `SECURITY.md` present
- [ ] LICENSE matches distribution intent (code vs Docker image)
- [ ] Tests pass

---

## 7. Next steps

1. Maintainer: git history / secret scan (**1.3**).
2. LICENSE: clarify code vs container image (e.g. add OSS license for source if needed).
3. Complete **4.2–4.4** before announcing.
4. Documentation site: MkDocs config is in-repo ([Documentation](./Documentation.md) § *Static documentation site*); enable **GitHub Pages** (Actions source) and merge to **`main`** to deploy. Nav template: [SITE_MAP](./SITE_MAP.md).
