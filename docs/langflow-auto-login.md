# Langflow never asked you for a password? Check `LANGFLOW_AUTO_LOGIN` in one request

If you installed Langflow with `pip` or `uv` and ran `langflow run`, it never asked you to sign in. That isn't a missing feature. It's **auto-login**, and Langflow's docs describe it plainly: it "automatically signs in all users as the configured superuser".

`LANGFLOW_AUTO_LOGIN` defaults to `True` for pip installs. The docs add that "official Langflow Docker images set `false`", so the same app behaves differently depending on how you installed it.

On a laptop nobody else can reach, that's fine. On a server, a shared machine or a forwarded port, anyone who can open the page is the admin. In Langflow, the admin can edit a component's Python code, and that code runs on your host.

## Check it in one request

When the editor loads, it calls `/api/v1/auto_login`. In Langflow's source (`api/v1/login.py`), that endpoint returns a superuser token when auto-login is on, and `403` with "Auto login is disabled." when it's off. On the Langflow machine:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7860/api/v1/auto_login
# 403 = off: people have to sign in
# 200 = anyone who can reach this port is signed in as superuser
```

Then, from another machine on your network:

```bash
curl --max-time 5 http://<server LAN IP>:7860/api/v1/version
```

If both answer (`200` and a version), your Langflow is an open admin console to everyone on that network.

## Turn it off

Export your flows as JSON from the editor first. Flows made under auto-login belong to the auto-login account, so you may need to import them again under your new login.

Put these in an `.env` file next to Langflow (`chmod 600 .env`). They're from Langflow's own production example:

```bash
LANGFLOW_AUTO_LOGIN=False
LANGFLOW_SUPERUSER=administrator
LANGFLOW_SUPERUSER_PASSWORD=change-me-to-a-long-random-password
LANGFLOW_NEW_USER_IS_ACTIVE=False
LANGFLOW_ENABLE_SIGNUP=False
LANGFLOW_ENABLE_SUPERUSER_CLI=False
```

Start it with `langflow run --env-file .env`. Generate the password with `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`. Current releases refuse to start if it's the legacy default, `langflow`.

`LANGFLOW_ENABLE_SUPERUSER_CLI` defaults to `true`. The docs recommend `false` "to prevent unrestricted superuser creation".

Run the first check again: it should now print `403`.

## Three more defaults worth changing

**CORS is `*` with credentials.** The defaults are `LANGFLOW_CORS_ORIGINS=*` and `LANGFLOW_CORS_ALLOW_CREDENTIALS=True`. Langflow's docs warn that this means "any website can make requests to your Langflow API". Set it to the address in your address bar, as a JSON list:

```bash
LANGFLOW_CORS_ORIGINS=["https://langflow.example.com"]
```

Check it. No output means other sites are refused:

```bash
curl -s -D - -o /dev/null -H "Origin: https://example.org" \
  http://127.0.0.1:7860/api/v1/version | grep -i access-control-allow-origin
```

**Don't swap `LANGFLOW_SECRET_KEY` on an existing install.** Langflow encrypts the API keys you save as global variables with it. If you never set one, Langflow generated one and kept it. A new key makes your stored credentials unreadable. To rotate it, use the migration script described in Langflow's SECURITY.md, after a database backup.

**Port 7860 in Docker.** `-p 7860:7860` publishes it on every interface, and on Linux Docker-published ports skip ufw. Use `-p 127.0.0.1:7860:7860` and reach it over an SSH tunnel, Tailscale or an HTTPS proxy. If you serve it over HTTPS, also set `LANGFLOW_ACCESS_SECURE=True` and `LANGFLOW_REFRESH_SECURE=True`.

## And update

Before 1.10.3, MCP server settings let a signed-in user run OS commands on the host ([GHSA-w794-rj3p-xv45](https://github.com/langflow-ai/langflow/security/advisories/GHSA-w794-rj3p-xv45), CVE-2026-105697, critical). With auto-login on, "signed-in user" means anyone who can reach the port. The latest release is 1.12.5. Find your version at `http://127.0.0.1:7860/api/v1/version`.

## More

- [Langflow hardening checklist](https://munimv2.github.io/langflow-hardening.html): API keys, `LANGFLOW_SKIP_AUTH_AUTO_LOGIN`, webhook auth, code execution and SSRF settings for shared servers, and a Caddy config.
- [Langflow advisories by version](https://munimv2.github.io/langflow.html).
- Back to the [checklist](../README.md#langflow).

---

Written by MV2 of Munim, Inc., with AI agents, and checked on 12 October 2026 against Langflow's authentication and environment variable docs (1.12.x), its source (`api/v1/login.py`) and its security advisories. Settings change between releases, so check them against your version. General technical information, not professional advice. Corrections are welcome as issues. Text licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
