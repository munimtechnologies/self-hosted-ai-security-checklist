# Open WebUI: ENABLE_SIGNUP=false and sign-up is still open? Your env change was ignored (persistent config)

*Part of the [self-hosted AI security checklist](../README.md). Written by MV2 of Munim, Inc., with AI agents, and checked against Open WebUI's [environment variable reference](https://docs.openwebui.com/reference/env-configuration/) and its source (`backend/open_webui/main.py` and `config.py` on the main branch) on 12 October 2026. Longer version with the full settings table: [munimv2.github.io/openwebui-env-ignored.html](https://munimv2.github.io/openwebui-env-ignored.html).*

You add `ENABLE_SIGNUP=false` (or a new `OLLAMA_BASE_URLS`, `WEBUI_URL` or `ENABLE_API_KEYS`) to `docker-compose.yml`, recreate the container, and nothing changes. If Open WebUI had already started once, **sign-up may still be open.** Your Compose file isn't broken. It's how Open WebUI's settings work.

## Why the env var is ignored

Settings marked `ConfigVar` in the docs (older docs call it PersistentConfig) are read from the environment on the **first** start and saved to Open WebUI's database. After that, the saved value wins. From the docs: "if you restart the container, `ConfigVar` environment variables will no longer use the external environment variable values. Instead, they will use the internally stored values." `ENABLE_PERSISTENT_CONFIG` defaults to `True`.

| Stored after the first start (env ignored later) | Read from the environment on every start |
|---|---|
| `ENABLE_SIGNUP` (default `True`), `DEFAULT_USER_ROLE` (`pending`), `ENABLE_LOGIN_FORM`, `WEBUI_URL`, `ENABLE_API_KEYS` (`False`), `ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS`, `API_KEYS_ALLOWED_ENDPOINTS`, `JWT_EXPIRES_IN` (`4w`), `OLLAMA_BASE_URLS`, `ENABLE_OLLAMA_API`, `OPENAI_API_KEYS`, `ENABLE_DIRECT_CONNECTIONS`, `ENABLE_CODE_EXECUTION`, `ENABLE_CODE_INTERPRETER`, `ENABLE_COMMUNITY_SHARING` | `CORS_ALLOW_ORIGIN` (default `*`), `WEBUI_SECRET_KEY`, `WEBUI_AUTH`, `ENABLE_PERSISTENT_CONFIG`, `RESET_CONFIG_ON_START` |

OAuth/SSO works the other way round: `ENABLE_OAUTH_PERSISTENT_CONFIG` defaults to `False`, so OAuth settings come from the environment on every restart.

## Check what your server actually does

`/api/config` answers without a login, because the sign-in page needs it. It returns the stored `enable_signup` and `enable_login_form`, and `"onboarding": true` while no user exists yet. On the server, with your own port:

```bash
curl -s http://127.0.0.1:3000/api/config | python3 -m json.tool \
  | grep -E '"(enable_signup|enable_login_form|onboarding)"'
```

- `"enable_signup": true`: anyone who can open the page can create an account. New accounts start as `pending` by default, so an admin has to approve them, but `DEFAULT_USER_ROLE` is a stored setting too. Check it under Admin Settings > General.
- `"onboarding": true`: no admin exists yet, so **the first person to sign up becomes admin**. If others can reach the server, create your admin account now.

## Three fixes

1. **Admin Panel (recommended).** Admin Panel > Settings > General has sign-up, the default user role, the WebUI URL and API keys; Connections has the Ollama and OpenAI URLs and keys. It takes effect at once and survives restarts. Then make your Compose file say the same, so a fresh install gets it right too.
2. **Re-apply the environment once with `RESET_CONFIG_ON_START=true`.** At startup Open WebUI clears the stored config and seeds it again from the environment and defaults. That resets **every** setting saved in the Admin Panel (connections, web search, audio...). Users, chats and files stay. Back up first, start once with it, remove it, start again:

   ```bash
   docker run --rm -v open-webui:/data -v "$PWD":/backup alpine tar czf /backup/open-webui-backup.tgz -C /data .
   # add RESET_CONFIG_ON_START=true to the environment, then
   docker compose up -d
   # remove RESET_CONFIG_ON_START again, then
   docker compose up -d
   ```
3. **Make the environment win every time with `ENABLE_PERSISTENT_CONFIG=False`.** Good if Compose or Helm manages everything. Admin Panel changes then last only until the next restart, so tell other admins. Per the docs, two-factor sign-in (`ENABLE_MFA`) needs persistent config on.

Don't `docker volume rm open-webui` to "start clean": it deletes every user, chat and file.

## While you're there

- **Update to 0.11.4 or newer.** Earlier versions have 15+ advisories with no CVE ID, including session-token theft through `javascript:` links in chat messages (GHSA-wf9m-46cp-c6h6).
- Publish the port as `127.0.0.1:3000:8080` and put an HTTPS proxy in front ([Open WebUI behind nginx or Caddy](https://munimv2.github.io/openwebui-reverse-proxy.html)).
- Set `CORS_ALLOW_ORIGIN` to your own address, keep `WEBUI_SECRET_KEY` fixed, and don't set `JWT_EXPIRES_IN=-1`.

---

General technical information, not a security certification or professional advice. Only change servers you own or are allowed to manage. Text licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Written by MV2 of Munim, Inc., with AI agents. Corrections are welcome as issues.
