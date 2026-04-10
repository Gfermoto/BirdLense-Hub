# Heimdall tiles for BirdLense Hub

How to add **BirdLense** (and related services) to **[linuxserver/Heimdall](https://github.com/linuxserver/Heimdall)** v2 as dashboard tiles. For the opposite direction (Hub probing Heimdall), see **heimdall_url** in [Configuration](./CONFIGURATION.md) (section *Heimdall vs Hub metrics*).

[Русский](./HEIMDALL.ru.md)

---

## Can Heimdall import a list of tiles?

**Not via the web UI today.** Upstream feature requests ([#294](https://github.com/linuxserver/Heimdall/issues/294), [#383](https://github.com/linuxserver/Heimdall/issues/383)) did not add built-in import/export for applications. For **moving a full dashboard**, maintainers suggest **copying the SQLite database** while Heimdall is stopped (see [#831](https://github.com/linuxserver/Heimdall/issues/831)).

This page is the **manual path**: copy URLs from the table into **Items - Add** in Heimdall.

---

## Placeholders

| Token | Meaning |
|-------|---------|
| `YOUR_HUB_HOST` | Hostname or IP your **browser** uses for BirdLense. |
| `YOUR_HUB_PORT` | Hub HTTP port (default **8085**, or `BIRDLENSE_PORT` / reverse-proxy). |
| `YOUR_HUB_BASE` | e.g. `http://YOUR_HUB_HOST:YOUR_HUB_PORT` (use `https://` behind TLS). |

Optional:

| Token | Meaning |
|-------|---------|
| `YOUR_FRIGATE_URL` | Frigate UI base URL. |
| `YOUR_BIRDNET_URL` | Same as Hub **Settings - General - birdnet_url** if set. |

---

## Recommended tiles

In Heimdall: **Items - Add**. Use a standard bookmark-style tile unless a Foundation app matches.

| Suggested title | URL | Notes |
|-----------------|-----|--------|
| BirdLense Hub | `YOUR_HUB_BASE/` | Main UI. |
| BirdLense health | `YOUR_HUB_BASE/api/ui/health` | Quick API up check. |
| BirdLense metrics (Prometheus) | `YOUR_HUB_BASE/metrics` | Plain text metrics. |
| BirdLense metrics (JSON) | `YOUR_HUB_BASE/api/metrics/summary` | JSON snapshot. |

### Optional neighbours

| Suggested title | URL |
|-----------------|-----|
| Frigate | `YOUR_FRIGATE_URL/` |
| BirdNET | `YOUR_BIRDNET_URL/` |

---

## Metrics and `BIRDLENSE_METRICS_TOKEN`

If **`BIRDLENSE_METRICS_TOKEN`** is set, **`/metrics`**, **`/api/metrics`**, and **`/api/metrics/summary`** need **`Authorization: Bearer`**. Heimdall link tiles cannot send that header. Use **`/api/ui/health`** for a simple tile, or open metrics where you can pass the token. See [SECURITY](./SECURITY.md).

---

## Step-by-step

1. Open the Hub in a browser; copy the origin as `YOUR_HUB_BASE`.
2. Add tile **BirdLense Hub** pointing to `YOUR_HUB_BASE/`.
3. Add **BirdLense health** to `YOUR_HUB_BASE/api/ui/health`.
4. If no metrics token, optionally add Prometheus / JSON rows from the table.
5. Optionally add Frigate / BirdNET.

---

## Optional: HTML bookmarks for your browser

Heimdall does **not** import this file. For Firefox / Chrome bookmark import, edit and use:

- [examples/heimdall/birdlense-bookmarks.html](./examples/heimdall/birdlense-bookmarks.html)

---

## See also

- [CONFIGURATION](./CONFIGURATION.md)
- [SCENARIOS](./SCENARIOS.md)
