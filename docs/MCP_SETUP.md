# MCP setup — BirdLense Hub

[**Model Context Protocol (MCP)**](https://modelcontextprotocol.io/) exposes BirdLense Hub tools (from your OpenAPI surface) to **authorized MCP clients**—automation, IDE extensions, monitoring, or custom integrations—so they can query and operate the hub with your consent and a valid token.

[Русский](./MCP_SETUP.ru.md)

---

## 1. Set `MCP_TOKEN`

**Option A — deploy hook (recommended)**  
In your local `scripts/deploy.local.sh` (not committed):

```bash
export MCP_TOKEN="your-secret-token-min-16-chars"
```

`make deploy` merges this into `app/.env` on the server (`scripts/deploy.sh`).

**Option B — on the server**

```bash
ssh YOUR_SSH_HOST "echo 'MCP_TOKEN=your-secret-token' >> YOUR_REMOTE_DIR/app/.env"
# then: make stop && make start
```

You can also set the token in **Settings → MCP** in the UI; env overrides are documented in [CONFIGURATION](./CONFIGURATION.md).

---

## 2. Enable MCP in the UI

1. Open Hub → **Settings**
2. Section **MCP** → enable the MCP server
3. Save and **restart** the container

---

## 3. Client configuration

Add the server entries below in your **MCP host application** (exact config path depends on the product). **Never commit** tokens or secrets.

### 3a. Hub API (tools + OpenAPI)

```json
{
  "mcpServers": {
    "birdlense": {
      "url": "http://YOUR_HOST:8085/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN_HERE"
      }
    }
  }
}
```

Replace:

- `YOUR_HOST:8085` — reachable Hub host and port (path **`/mcp`** — check **Settings → MCP** if you use an older `/sse` URL).
- `YOUR_MCP_TOKEN_HERE` — same value as `MCP_TOKEN` / UI MCP token

**LAN example:** **`http://192.168.1.11:8085/mcp`** — same host as the UI (`http://192.168.1.11:8085/`).

**Public host (TLS, alternate):** e.g. **`https://birdlense.eyera.info/mcp`** — SSH e.g. `185.218.111.196:2222` if that deployment is still in use. Same Bearer token; nginx terminates HTTPS and proxies to the Hub.

With a valid token, tools such as settings read/update can run **without** typing the settings UI password (server-side trust).

### 3b. Repository documentation (GitMCP, read-only)

Optional: read **Markdown in the GitHub repo** (`docs/`, `README`, etc.) without a running Hub via [GitMCP](https://gitmcp.io):

```json
{
  "mcpServers": {
    "BirdLense-Hub Docs": {
      "url": "https://gitmcp.io/Gfermoto/BirdLense-Hub"
    }
  }
}
```

You can combine **3a** and **3b** in one `mcpServers` object. GitMCP is **not** a substitute for Hub MCP — it does not call your deployment; it only mirrors repository documentation.

---

## Connect timeout / `SSE error: fetch failed`

A message like `Connect Timeout Error (birdlense.eyera.info:443, timeout: 10000ms)` means the **MCP client never completed TCP/TLS** to the server in time. This is usually **network path from your PC to the VPS**, not a wrong token (the Bearer check may never run).

**On the same machine and network as the MCP client:**

```bash
curl -m 15 -sS -o /dev/null -w '%{http_code}\n' https://birdlense.eyera.info/api/ui/health
curl -m 15 -sS -H "Authorization: Bearer YOUR_MCP_TOKEN" -o /dev/null -w '%{http_code}\n' https://birdlense.eyera.info/mcp
```

- If **curl also times out** — routing or firewall to `185.218.111.196:443`. Try another network or VPN.
- If **curl is fast (200/401) but the MCP client times out** — try disabling the **system proxy**, forcing **IPv4** (e.g. add `185.218.111.196 birdlense.eyera.info` to hosts), or updating the client.

**SSH tunnel** when SSH to the VPS works but direct HTTPS from the PC does not:

```bash
ssh -p 2222 -N -L 18085:127.0.0.1:8085 root@185.218.111.196
```

Point MCP at **`http://127.0.0.1:18085/mcp`** with the same `Authorization: Bearer …` while the session stays open.

**LAN:** if the hub is on your LAN, `http://<hub-ip>:8085/mcp` with the same Bearer is fine.

---

## 4. Restart the MCP client

Restart the MCP client after changing its configuration.

---

## Verify

Both servers (if configured) should show as connected in the client’s MCP panel: **birdlense** (Hub) and **BirdLense-Hub Docs** (GitMCP).

---

## See also

[INSTALL](./INSTALL.md) · [API](./API.md) · [CONFIGURATION](./CONFIGURATION.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.md)
