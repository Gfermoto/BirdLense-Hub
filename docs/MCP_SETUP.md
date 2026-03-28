# MCP setup — BirdLense Hub

[Model Context Protocol](https://modelcontextprotocol.io/) lets editors and agents call BirdLense Hub tools backed by your OpenAPI surface.

[Русский](./MCP_SETUP.ru.md)

---

## 1. Set `MCP_TOKEN`

**Option A — deploy hook (recommended)**  
In your local `scripts/deploy.local.sh` (not committed):

```bash
export MCP_TOKEN="your-secret-token-min-16-chars"
```

`make deploy` can merge this into `app/.env` on the server (see your deploy script).

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

## 3. Client config (example: Cursor)

Create `.cursor/mcp.json` (folder is gitignored — do not commit secrets).

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

For agents that should read **Markdown in the GitHub repo** (`docs/`, `README`, etc.) without a running Hub, add [GitMCP](https://gitmcp.io):

```json
{
  "mcpServers": {
    "BirdLense-Hub Docs": {
      "url": "https://gitmcp.io/Gfermoto/BirdLense-Hub"
    }
  }
}
```

You can combine **3a** and **3b** in one `mcpServers` object. GitMCP is **not** a substitute for Hub MCP — it does not call your deployment; it exposes repo content for documentation lookup.

---

## 4. Restart the MCP client

Restart the editor or agent after editing `mcp.json`.

---

## Verify

Both servers (if configured) should show as connected in the client’s MCP panel: **birdlense** (Hub) and **BirdLense-Hub Docs** (GitMCP).

---

## See also

[INSTALL](./INSTALL.md) · [API](./API.md) · [CONFIGURATION](./CONFIGURATION.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.md)
