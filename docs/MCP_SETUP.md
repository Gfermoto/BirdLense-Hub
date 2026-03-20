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

Create `.cursor/mcp.json` (folder is gitignored — do not commit secrets):

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

- `YOUR_HOST:8085` — reachable Hub host and port
- `YOUR_MCP_TOKEN_HERE` — same value as `MCP_TOKEN` / UI MCP token

With a valid token, tools such as settings read/update can run **without** typing the settings UI password (server-side trust).

---

## 4. Restart the MCP client

Restart the editor or agent after editing `mcp.json`.

---

## Verify

The server should appear connected in your client’s MCP panel.

---

## See also

[INSTALL](./INSTALL.md) · [API](./API.md) · [CONFIGURATION](./CONFIGURATION.md) · [ACCESS_CONTROL](./ACCESS_CONTROL.md)
