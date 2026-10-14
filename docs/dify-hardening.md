# Self-hosted Dify security checklist

By MV2 of Munim, Inc., with AI agents. Checked against Dify's [environment variables](https://docs.dify.ai/en/self-host/deploy/configuration/environments) and [Docker Compose](https://docs.dify.ai/en/self-host/deploy/quick-start/docker-compose) docs, and the `docker/.env.example` and `docker/docker-compose.yaml` files of releases 1.13.0, 1.14.0, 1.15.0, 1.16.0 and 1.17.1, on 12 October 2026 (still the latest stable release on 13 October). For your own servers only.

Most people install Dify with `cp .env.example .env` and `docker compose up -d`. That copy is made once and kept through every upgrade, so what *your* `.env` says depends on when you installed, not on the version you run now. Work through these steps in order.

## Short version

- **Update to 1.17.1.** Anything before 1.16.0 has at least one 2026 advisory.
- **Until someone creates the admin account, whoever opens `/install` first gets it.** Set `INIT_PASSWORD` before the first start on any server others can reach.
- **Installed before 1.15.0? Look at `SECRET_KEY` in your `.env`.** Up to 1.14.x, `.env.example` shipped one fixed value, starting `sk-9f73s3lj`, which is public on GitHub. Dify signs logins with it. If yours still starts that way, replace it.
- **The Compose file publishes nginx (80, 443) and the plugin debugging port (5003) on every interface**, and some vector store options publish their database port too. On Linux, Docker-published ports skip ufw.
- **The bundled database, Redis, sandbox, plugin daemon and Weaviate keys are public defaults** (`difyai123456`, `dify-sandbox` ...). None of those containers publishes a port by default, so this matters less. Change them anyway on a shared host.

## 1. Update

Find your version under your avatar, then *About*, or with `docker compose images` in `dify/docker` (the `langgenius/dify-api` tag). Compare it with [Dify's security advisories](https://github.com/langgenius/dify/security/advisories) or the [CVE checker](https://munimv2.github.io/index.html?product=dify). The 2026 ones include a cross-tenant file preview (GHSA-9c9q-5rj5-mjj2, fixed in 1.14.2) and an MCP server IDOR (GHSA-ccrj-frp2-c945, fixed in 1.16.0). Back up `docker/volumes` and `.env` before you upgrade.

## 2. The setup page: set `INIT_PASSWORD`

A new Dify has no admin until someone fills in `http://your-server/install`, and the first account becomes the workspace owner. From Dify's docs: when `INIT_PASSWORD` is set, "the `/install` page requires this password before the admin account can be created". It's empty by default, can be at most 30 characters, and "once setup is complete, this variable has no further effect".

```bash
cd dify/docker
cp .env.example .env
# before the first start:
sed -i "s|^INIT_PASSWORD=.*|INIT_PASSWORD=$(openssl rand -hex 12)|" .env
grep '^INIT_PASSWORD=' .env   # you'll type this on /install
```

It isn't your admin password. You enter it once to unlock the page, then create the admin account with its own password. If setup is already finished, there's nothing to do here.

## 3. `SECRET_KEY`: is yours the published one?

Dify's docs say this key is used for "session cookie signing, JWT authentication tokens, file URL signatures (HMAC-SHA256), and encrypting third-party OAuth credentials". Anyone who knows it can sign tokens your Dify accepts.

- **1.13.0 and 1.14.0** (and earlier): `.env.example` had `SECRET_KEY=sk-9f73s3lj...`, one fixed value, the same for everyone. (Only its start is shown here, so secret scanners don't flag this file. The full value is in the old `docker/.env.example` on GitHub.)
- **1.15.0 and later**: `SECRET_KEY=` (empty), with the comment "Leave empty to auto-generate a persistent key in the storage directory."

Upgrading doesn't change your `.env`, so an install from before 1.15.0 keeps the old value:

```bash
grep -c '^SECRET_KEY=sk-9f73s3lj' dify/docker/.env
# 1 -> the published key: replace it
# 0 -> grep '^SECRET_KEY=' dify/docker/.env
#      SECRET_KEY=   (empty, on 1.15.0+) -> auto-generated, kept in ./volumes/app/storage
#      anything else                     -> your own key: keep it
```

To replace it:

```bash
cd dify/docker
cp .env .env.bak
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -base64 42)|" .env
docker compose up -d
```

Per Dify's docs, changing the key "will immediately log out all users, invalidate all file URLs", and OAuth-based plugin integrations need to be authorized again because "their encrypted credentials become unrecoverable". Do it at a quiet time and tell your users. More detail: [dify-secret-key.md](dify-secret-key.md).

## 4. What's reachable from the network

From the 1.17.1 Compose file:

- **nginx:** `"${EXPOSE_NGINX_PORT:-80}:${NGINX_PORT:-80}"` and the same for 443, so ports 80 and 443 on every interface.
- **plugin_daemon:** `"${EXPOSE_PLUGIN_DEBUGGING_PORT:-5003}:${PLUGIN_DEBUGGING_PORT:-5003}"`, the remote plugin debugging port, also on every interface.
- **Vector stores other than the default Weaviate**, chosen with `VECTOR_STORE`, publish their own ports. Examples: Elasticsearch 9200 and Kibana 5601, Milvus 19530 and 9091, MyScale 8123, OpenGauss 6600, MatrixOne 6001, OceanBase 2881, IRIS 1972 and 52773.

The `db`, `redis`, `weaviate`, `sandbox`, `api` and `web` services publish nothing. To see what your install actually publishes:

```bash
docker compose ps --format "table {{.Service}}\t{{.Ports}}"
# "0.0.0.0:5003->5003/tcp" = reachable from other machines
```

These variables go straight into the port mapping, so they can carry an address. In `.env`:

```
# only this machine (put your own HTTPS proxy in front, or use a VPN)
EXPOSE_NGINX_PORT=127.0.0.1:8080
EXPOSE_NGINX_SSL_PORT=127.0.0.1:8443
# not developing plugins? keep the debugging port local too
EXPOSE_PLUGIN_DEBUGGING_PORT=127.0.0.1:5003
```

Run `docker compose up -d` and check `docker compose ps` again. One caveat: the console shows `EXPOSE_PLUGIN_DEBUGGING_PORT` to plugin developers as part of the debugging address, so it will look odd there; that only matters if you debug plugins. For vector store ports, use a `docker-compose.override.yaml` that maps them to `127.0.0.1`, or don't publish them at all, since Dify reaches them over the internal network.

Want people outside to reach Dify? Serve it over HTTPS, either with your own proxy in front of `127.0.0.1:8080`, or with Dify's nginx (`NGINX_HTTPS_ENABLED=true` and a certificate). Then do step 5.

## 5. URLs, cookies and CORS

- Set `CONSOLE_API_URL`, `CONSOLE_WEB_URL`, `SERVICE_API_URL` and `APP_WEB_URL` to your `https://` address. Per the docs, `CONSOLE_API_URL` "also determines whether secure (HTTPS-only) cookies are used", and email links break while `CONSOLE_WEB_URL` is empty.
- **Console CORS:** the docs say `CONSOLE_CORS_ALLOW_ORIGINS` falls back to `CONSOLE_WEB_URL` if not set. But `.env.example` sets it, to `*`, so that fallback never applies. Set it to your console's address, for example `CONSOLE_CORS_ALLOW_ORIGINS=https://dify.example.com`.
- `WEB_API_CORS_ALLOW_ORIGINS` (also `*`) covers the public web app API. Leave it if you embed Dify apps on other sites; otherwise set it to your own address.

## 6. Accounts and sign-in

- Keep `ALLOW_REGISTER=false` and `ALLOW_CREATE_WORKSPACE=false` (both default `false`). Invite people instead.
- `REFRESH_TOKEN_EXPIRE_DAYS` (default 30) is how long someone stays signed in without a password. Shorten it on shared or kiosk machines.
- Using GitHub or Google sign-in (`ENABLE_SOCIAL_OAUTH_LOGIN`)? You can turn off `ENABLE_EMAIL_PASSWORD_LOGIN`. Dify's docs say to keep at least one sign-in method enabled.

## 7. The bundled services' default passwords and keys

In 1.17.1's `.env.example`: `DB_PASSWORD=difyai123456`, `REDIS_PASSWORD=difyai123456`, `SANDBOX_API_KEY=dify-sandbox` (and `CODE_EXECUTION_API_KEY`, which must match), fixed `PLUGIN_DAEMON_KEY` and `PLUGIN_DIFY_INNER_API_KEY` values, and a fixed Weaviate key with `WEAVIATE_AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true`. They sit on Dify's internal Docker networks, so they aren't reachable from outside unless you publish a port. Change them if other people or containers share the host, and always before you publish one of those ports.

- **Pairs must match.** `CODE_EXECUTION_API_KEY` must equal `SANDBOX_API_KEY`, and `WEAVIATE_API_KEY` must equal `WEAVIATE_AUTHENTICATION_APIKEY_ALLOWED_KEYS`. Change both of a pair together.
- **The database password is the tricky one.** The Postgres image applies its password only when the data folder is first created. On an existing install, change it inside Postgres first, then in `.env`:

  ```bash
  docker compose exec db_postgres psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'NEW_PASSWORD';"
  # then set DB_PASSWORD=NEW_PASSWORD in .env and run: docker compose up -d
  ```

  Use letters and digits, or check how your shell treats special characters. Back up `volumes/db` first. (The service is `db_postgres` in 1.17.1; check `docker compose ps` on older releases.)

## 8. Outbound requests and code

- HTTP Request nodes, tools and code go out through Dify's SSRF proxy. With `SSRF_PROXY_ALLOW_PRIVATE_IPS` empty (the default), it keeps "the deny-by-default policy" for private addresses. If a workflow needs an internal service, allow that one address (`10.0.0.5/32`), not `10.0.0.0/8`. The sandbox sits on an internal network whose only way out is that proxy.
- `SANDBOX_ENABLE_NETWORK=true` lets code nodes make network calls (through the proxy). Set it to `false` if your code nodes don't need the network.
- Keep `FORCE_VERIFYING_SIGNATURE=true`, so only signed plugins install. Turn it off only for a plugin you built or reviewed yourself, then turn it back on.

## 9. Test it

```bash
cd dify/docker
# no published key, no setup page left open
grep -c '^SECRET_KEY=sk-9f73s3lj' .env            # should print 0
grep -E '^(INIT_PASSWORD|CONSOLE_CORS_ALLOW_ORIGINS)=' .env
curl -s http://127.0.0.1:8080/console/api/setup   # "step": "finished" = the admin account exists

# from ANOTHER machine: these should fail to connect if you bound them to 127.0.0.1
curl --max-time 5 http://<server LAN IP>:80/
nc -vz -w 5 <server LAN IP> 5003
```

The free [local-ai-checkup](https://github.com/munimtechnologies/local-ai-checkup) script reads the version of a running `langgenius/dify-api` container, lists the advisories that apply, and flags AI containers, such as Dify's plugin daemon, whose ports are published on every interface.

## Mistakes to avoid

- **Starting Dify on a public server and finishing `/install` later.**
- **Assuming an upgrade fixed your `.env`.** It didn't change `SECRET_KEY`, the CORS lines or the default passwords.
- **Changing `DB_PASSWORD` in `.env` only:** the API then can't connect to a database that still has the old password.
- **Allowing whole private ranges in `SSRF_PROXY_ALLOW_PRIVATE_IPS`** to make one workflow work.
- **Relying on ufw** to block ports Docker publishes on Linux.

Dify often calls a local model server, and Dify's login doesn't protect that server. Lock it down too: [Ollama API key](ollama-api-key.md), [vLLM `--api-key`](vllm-api-key.md), [LiteLLM proxy](litellm-hardening.md).

---

General technical information, not a security certification or professional advice. Settings are from Dify's docs and release files as of 12 October 2026 and change between releases; check them against your version before changing production. Corrections are welcome as issues in this repo. Written by MV2 of Munim, Inc., with AI agents.
