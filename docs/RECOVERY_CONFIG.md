# Recovering configuration

If the UI shows wrong defaults or empty cameras after an edit, restore from backup or re-sync from the server.

[Русский](./RECOVERY_CONFIG.ru.md)

---

> **Placeholders:** `YOUR_SSH_HOST` — SSH host alias (`~/.ssh/config` or `DEPLOY_HOST`); `YOUR_REMOTE_DIR` — app root on the server (**default deploy:** `/root/BirdLense` = `DEPLOY_REMOTE_DIR`; `/opt/birdlense` is a legacy example).

---

## Fast path: `restore-config.sh`

```bash
# Restore from .bak on the server (if present)
./scripts/restore-config.sh

# Push a known-good local file to the server
./scripts/restore-config.sh from-local
```

Then restart:

```bash
ssh YOUR_SSH_HOST "cd YOUR_REMOTE_DIR/app && make stop && make start"
```

---

## Automatic `.bak` file

Each save can create `app/app_config/user_config.yaml.bak` next to `user_config.yaml`.

**Local:**

```bash
cp app/app_config/user_config.yaml.bak app/app_config/user_config.yaml
```

**Remote:**

```bash
ssh YOUR_SSH_HOST "cp YOUR_REMOTE_DIR/app/app_config/user_config.yaml.bak YOUR_REMOTE_DIR/app/app_config/user_config.yaml"
```

Restart or wait for processor reload per your setup.

---

## Deploy does not wipe `user_config.yaml`

Standard deploy syncs code but **keeps** server-side `user_config.yaml`. If settings “vanished” locally, the server copy may still be intact:

```bash
ssh YOUR_SSH_HOST "cat YOUR_REMOTE_DIR/app/app_config/user_config.yaml"
```

Copy the content back or edit via **Settings** in the UI.

---

## Git (discouraged for secrets)

If you accidentally committed `user_config.yaml`:

```bash
git checkout app/app_config/user_config.yaml
```

Prefer **not** storing API keys or tokens in git — use env vars documented in [CONFIGURATION](./CONFIGURATION.md).

---

## Manual rebuild

Re-enter critical keys in **Settings** or edit YAML directly:

- `video.cameras`, `video.go2rtc_url`
- `mqtt.broker`, `mqtt.password`
- `notifications.telegram_bot_token`, `notifications.telegram_chat_id`
- `general.settings_password`, `general.contributor_password`

Full reference: [CONFIGURATION](./CONFIGURATION.md).

---

## See also

[INSTALL](./INSTALL.md) · [CONFIGURATION](./CONFIGURATION.md) · [TROUBLESHOOTING](./TROUBLESHOOTING.md)
