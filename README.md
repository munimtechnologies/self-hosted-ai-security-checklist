# Self-hosted AI security checklist

Safe defaults and one-line tests for the AI apps people run on their own machines and servers: **Ollama, Open WebUI, vLLM, LiteLLM, ComfyUI, LM Studio, n8n, Dify, Langflow, Flowise, RAGFlow and AnythingLLM**.

Written by MV2 of Munim, Inc., with AI agents, and checked on **12 October 2026** against each project's own docs, source and security advisories (the OSV.dev section, the vLLM advisory range, the Open WebUI proxy guide, the LiteLLM advisories, the n8n secure-cookie fixes and the Flowise Advisory Database check on 13 October; the Dependabot-blind advisory counts on 14 October). Every section links to a longer guide with sources. For machines you own or are allowed to manage. Corrections are welcome as issues.

Contents: [Six rules](#six-rules-that-cover-most-of-it) · [Ollama](#ollama) · [LM Studio](#lm-studio) · [Open WebUI](#open-webui) · [vLLM](#vllm) · [LiteLLM](#litellm-proxy) · [ComfyUI](#comfyui) · [n8n](#n8n) · [Dify](#dify) · [Langflow](#langflow) · [Flowise](#flowise) · [RAGFlow](#ragflow) · [AnythingLLM](#anythingllm) · [Guides in this repo](#guides-in-this-repo) · [Check it for me](#check-it-automatically)

## Six rules that cover most of it

1. **`docker run -p 11434:11434` publishes the port on every interface, and on Linux it skips ufw and firewalld.** Write `-p 127.0.0.1:11434:11434`, or give the service no `ports:` at all and let other containers reach it by service name on the Compose network.
2. **Many of these apps have no login at all** (Ollama, ComfyUI, an LM Studio server without its auth setting, Langflow with auto-login). For them, "who can reach the port" is the only access control. Keep them on `127.0.0.1` and use an SSH tunnel, Tailscale or an authenticating reverse proxy to reach them from elsewhere ([how](docs/ollama-remote-access.md)). Don't set `0.0.0.0` just to make another device or a container connect.
3. **The first account is the admin.** Open WebUI's first sign-up, Dify's `/install` page and n8n's owner setup all go to whoever gets there first. Finish setup before the server is reachable from the network.
4. **Your config file outlived the default.** `cp .env.example .env` happens once; upgrades don't touch it. Dify installs from before 1.15.0 can still carry the `SECRET_KEY` that the example file published (see [Dify](#dify)). Open WebUI stores many settings in its database after the first start, so later env changes are ignored (see [Open WebUI](#open-webui)).
5. **CORS `*` is a common default** (Langflow, Dify's console, Open WebUI). If you sign in from a browser, set it to your own address.
6. **Many 2026 advisories have no CVE ID** (Open WebUI, n8n, vLLM, LiteLLM, Flowise, RAGFlow), some vulnerability databases get the fixed version wrong (OSV.dev can turn a CVE's "through X" into "fixed in X": [details and a checker](docs/osv-through-read-as-fixed.md)), some advisories list the wrong affected range (see [vLLM](#vllm)), and some projects stop shipping fixes at all (Flowise was archived in August 2026). CVE-only scanners and `npm audit`/`pip-audit` can miss them. So can Dependabot: it ignores unreviewed advisories, and Langflow, n8n, Flowise, vLLM, Open WebUI, Dify and Ollama each have dozens of them ([counts](docs/dependabot-blind-ai-advisories.md)). Compare your version against the project's GitHub security advisories, or use the [CVE checker](https://munimv2.github.io/).

## Ollama

- **Default:** `127.0.0.1:11434`, **no authentication**. Anyone who can reach the port can list, pull, create and delete models and use your GPU.
- **Gets exposed by:** `OLLAMA_HOST=0.0.0.0`, the app's "Expose Ollama to the network" setting, or Docker's `-p 11434:11434`.
- **Update:** CVE-2026-103663 (path traversal in `/api/pull`) affects 0.34.2 up to 0.35.0. Latest is 0.40.3.
- **Test** (from another device): `curl --max-time 5 http://<LAN IP>:11434/api/version`. A version number in the reply means it's open to your network.
- **Need it from elsewhere?** SSH tunnel (`ssh -L 11434:127.0.0.1:11434 you@host`), or Open WebUI over Tailscale Serve. A plain `tailscale serve 11434` in front of a loopback Ollama returns 403, because Ollama checks the Host header; bind Ollama to its Tailscale IP instead ([docs/ollama-remote-access.md](docs/ollama-remote-access.md)).
- **Need a key?** Ollama has none. Put an exact-match `Authorization: Bearer` check in Caddy or nginx in front of it: [docs/ollama-api-key.md](docs/ollama-api-key.md).
- **Any website can talk to it if `OLLAMA_ORIGINS=*`.** Check it in one click: [browser check](https://munimv2.github.io/ollama-origins-check.html).
- Guides: [Remote access without exposing it (in this repo)](docs/ollama-remote-access.md) · [Ollama API key (in this repo)](docs/ollama-api-key.md) · [Is my Ollama exposed?](https://munimv2.github.io/secure-ollama.html) · [Docker apps can't reach Ollama](https://munimv2.github.io/docker-ollama.html)

## LM Studio

- **Default:** the local server listens on port 1234. "Serve on Local Network" makes it reachable from the LAN.
- **Turn on "Require Authentication"** (LM Studio 0.4.0 and newer) before serving on the network, and give each client its own token.
- **Test:** `curl --max-time 5 http://<LAN IP>:1234/v1/models` from another device should fail or return 401.
- Guide: [Remote access without exposing it (in this repo)](docs/ollama-remote-access.md#lm-studio) (LM Studio section)

## Open WebUI

- **Update to 0.11.4 or newer** (0.12.0 is the latest). Earlier versions have 15+ advisories with no CVE ID, including session-token theft through `javascript:` links in chat messages (GHSA-wf9m-46cp-c6h6).
- **First sign-up becomes admin.** Create the admin while it's still local, or set `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` and `WEBUI_ADMIN_NAME` for the first start. Keep `DEFAULT_USER_ROLE=pending`.
- **Behind nginx, Caddy or Nginx Proxy Manager:** set `CORS_ALLOW_ORIGIN` to your address (the default is `*`; Open WebUI's nginx guide says WebSockets fail without it) and turn off `proxy_buffering` in nginx (the usual cause of garbled streaming). Set `WEBUI_URL`, a fixed `WEBUI_SECRET_KEY` and `WEBUI_SESSION_COOKIE_SECURE=true`. Full configs: [docs/openwebui-reverse-proxy.md](docs/openwebui-reverse-proxy.md).
- **API keys:** limit what they can call with `ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS=true` and `API_KEYS_ALLOWED_ENDPOINTS=/api/chat/completions,/api/v1/models`.
- **Env change ignored?** Settings marked `ConfigVar` (formerly PersistentConfig), including `ENABLE_SIGNUP`, `DEFAULT_USER_ROLE`, `WEBUI_URL`, `ENABLE_API_KEYS` and `JWT_EXPIRES_IN`, are read from the environment only on the first start; after that the database wins. Change them in the Admin Panel.
- **Test:** `curl -s http://127.0.0.1:3000/api/config` needs no login. It should show `"enable_signup": false` and no `"onboarding": true` (that one means no admin exists yet, so the first sign-up becomes admin).
- **Don't publish port 3000/8080 to the network "to test"** and leave it. Anyone who reaches it skips your proxy's TLS and logs.
- Guides: [Behind nginx or Caddy: WebSocket and streaming errors (in this repo)](docs/openwebui-reverse-proxy.md) · [ENABLE_SIGNUP=false and sign-up still open (in this repo)](docs/openwebui-signup-still-open.md) · [Env change ignored? Persistent config](https://munimv2.github.io/openwebui-env-ignored.html) · Official: [Open WebUI hardening guide](https://docs.openwebui.com/getting-started/advanced-topics/hardening/)

## vLLM

- **`vllm serve` listens on every interface by default** (`--host` unset). Pass `--host 127.0.0.1`.
- **`--api-key` only covers `/v1`, `/v2`, `/inference` and `/cohere`.** vLLM's own security guide says other routes, such as `/invocations`, `/pooling`, `/score`, `/tokenize`, `/pause`, `/resume` and `/abort_requests`, have no authentication. Put a proxy in front that allows only the routes your apps use: [docs/vllm-api-key.md](docs/vllm-api-key.md).
- **Pass the key as `VLLM_API_KEY`**, not on the command line where `ps` shows it. Add `--disable-fastapi-docs`. Never set `VLLM_SERVER_DEV_MODE=1` on a reachable server.
- **Update:** the October 2026 batch of advisories needs 0.31.0.
- **Don't trust one advisory's range on its own.** [GHSA-mm38-5g96-7j6x](https://github.com/vllm-project/vllm/security/advisories/GHSA-mm38-5g96-7j6x) (9 October 2026: the Nemotron-VL processors switch off Pillow's decompression-bomb limit for the whole process) lists the affected range as `<= 0.8.5` and the fix as 0.25.0. Neither file it names exists in 0.8.5; the line it describes ships in `nano_nemotron_vl.py` from **0.10.2** and is still in **0.24.0**, and 0.25.0 removes it. So treat 0.10.2 to 0.24.x as affected, even though a scanner reading that range would say otherwise. (Checked against the release tags on 13 October 2026; reported as [vllm-project/vllm#61327](https://github.com/vllm-project/vllm/issues/61327).)
- **Test:** `curl --max-time 5 http://<LAN IP>:8000/version` from another device should fail to connect. Through your proxy, `POST /invocations` without a key should get 401 or 404, not 200.
- Guides: [vLLM --api-key doesn't cover every endpoint (in this repo)](docs/vllm-api-key.md) · [Lock down vLLM](https://munimv2.github.io/vllm-api-key.html) · [vLLM advisories](https://munimv2.github.io/vllm.html)

## LiteLLM proxy

- **Update to 1.95.0 or newer at the very least.** GHSA-7hp6-4w63-5g45 (CVSS 9.9, no CVE ID): from 1.91.0, an `internal_user` can become proxy admin. Fixed in 1.100.4, 1.101.3, 1.102.2, 1.103.1 and later. [GHSA-g5ff-637f-6q2m](https://github.com/BerriAI/litellm/security/advisories/GHSA-g5ff-637f-6q2m) (1 October 2026, high, no CVE ID): before 1.95.0, a user with the read-only `internal_user_viewer` role can read local files on the proxy host through `vertex_ai_credentials`. On 13 October it wasn't in the GitHub Advisory Database or OSV.dev, so `pip-audit` won't show it. 1.82.7 and 1.82.8 on PyPI were malicious: if you ever installed them, rotate every key.
- **The CLI listens on `0.0.0.0:4000` by default.** Keep 4000 on localhost or a private network; let only the model API routes out.
- **The master key is the Admin UI password** unless you set `UI_PASSWORD`. Create admin users, then set `disable_env_credential_login: true`.
- **Set `LITELLM_SALT_KEY` before you store any credential, and never change it.** Without it, LiteLLM encrypts stored provider keys with the master key.
- **Leave stdio MCP servers off** (`LITELLM_ENABLE_MCP_STDIO` unset).
- Guides: [LiteLLM hardening (in this repo)](docs/litellm-hardening.md) · [LiteLLM hardening checklist](https://munimv2.github.io/litellm-hardening.html)

## ComfyUI

- **No login.** `--multi-user` is per-user storage, not authentication.
- **Plain `--listen` means `0.0.0.0,::`**, every interface. Name addresses instead: `--listen 127.0.0.1,100.101.102.103` (your Tailscale IP) or `127.0.0.1,192.168.1.50`.
- **From a phone:** leave ComfyUI on localhost and run `tailscale serve --bg 8188`. Never `tailscale funnel` it, and never forward 8188 on the router.
- **Don't add `--enable-cors-header`** unless you must: it replaces ComfyUI's cross-site check.
- **Test:** `ss -tlnp | grep 8188` should show `127.0.0.1:8188` (plus only the address you named).
- Guides: [ComfyUI --listen safely (in this repo)](docs/comfyui-listen.md) · [ComfyUI --listen safely (site)](https://munimv2.github.io/comfyui-listen.html)

## n8n

- **Update:** the September 2026 batches (26+ advisories, no CVE IDs) are fixed in 2.41.4, 2.42.1 and 1.123.83.
- **"Secure cookie" error?** Don't set `N8N_SECURE_COOKIE=false`: it sends your login session in clear text. Use `http://localhost:5678` on the same machine (not in Safari), `tailscale serve 5678` for your own devices, a local certificate (Caddy `tls internal`, or `N8N_SSL_KEY`/`N8N_SSL_CERT`) on a LAN, or a TLS reverse proxy for the internet ([all four](docs/n8n-hardening.md#2-your-n8n-server-is-configured-to-use-a-secure-cookie-fix-it-with-https)).
- **Keep the 2.0 defaults:** Execute Command and Local File Trigger excluded via `NODES_EXCLUDE`, file access limited to `~/.n8n-files`, task runners not in insecure mode, and `N8N_BLOCK_ENV_ACCESS_IN_NODE=true` set explicitly.
- **Turn on SSRF protection** (2.12.0 and newer, off by default): `N8N_SSRF_PROTECTION_ENABLED=true`, then allow only the internal hosts your workflows need.
- **Run `n8n audit`**, and protect webhooks with header, basic or JWT auth on the Webhook node. `N8N_BASIC_AUTH_*` was removed in 1.0 and does nothing.
- Guides: [n8n security checklist (in this repo)](docs/n8n-hardening.md) · [Self-hosted n8n security checklist (site)](https://munimv2.github.io/n8n-hardening.html)

## Dify

- **Set `INIT_PASSWORD` before the first start.** Until the admin exists, whoever opens `/install` first gets the workspace.
- **Installed before 1.15.0?** Up to 1.14.x, `docker/.env.example` shipped one fixed `SECRET_KEY` (it starts `sk-9f73s3lj`). Dify signs logins with it, and upgrades keep your old `.env`. Check: `grep -c '^SECRET_KEY=sk-9f73s3lj' docker/.env`. If it prints 1, replace the key (everyone gets logged out, and OAuth plugin credentials need re-authorizing).
- **Compose publishes nginx 80/443 and plugin debugging port 5003 on every interface.** Bind them in `.env`: `EXPOSE_NGINX_PORT=127.0.0.1:8080`, `EXPOSE_PLUGIN_DEBUGGING_PORT=127.0.0.1:5003`.
- **`CONSOLE_CORS_ALLOW_ORIGINS=*`** is set in `.env.example`. Set it to your console address.
- **Change the public default service passwords** (`difyai123456`, `dify-sandbox`) on shared hosts. For Postgres, change the password inside the database first.
- **Update to 1.17.1.** Anything before 1.16.0 has at least one 2026 advisory.
- **Dependabot won't tell you.** Dify ships as Docker images, and GitHub's database has no reviewed Dify advisories (33 unreviewed on 14 October 2026). Watch [Dify's security advisories](https://github.com/langgenius/dify/security/advisories) yourself.
- Guides: [Dify security checklist (in this repo)](docs/dify-hardening.md) · [The SECRET_KEY your upgraded .env may still have (in this repo)](docs/dify-secret-key.md) · [Self-hosted Dify security checklist (site)](https://munimv2.github.io/dify-hardening.html)

## Langflow

- **pip installs sign everyone in as superuser** (`LANGFLOW_AUTO_LOGIN` defaults to `True`; the official Docker images set it to false). Test: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:7860/api/v1/auto_login`. 200 means auto-login is on; 403 means off.
- **Turn it off:** `LANGFLOW_AUTO_LOGIN=False` with `LANGFLOW_SUPERUSER` and a long `LANGFLOW_SUPERUSER_PASSWORD`, plus `LANGFLOW_ENABLE_SIGNUP=False` and `LANGFLOW_ENABLE_SUPERUSER_CLI=False`.
- **CORS defaults to `*` with credentials.** Set `LANGFLOW_CORS_ORIGINS` to your address.
- **Don't swap `LANGFLOW_SECRET_KEY` on an existing install.** Stored credentials are encrypted with it; use the migration script from Langflow's SECURITY.md.
- **Every account that can edit flows can run Python on the host.** On shared servers, consider `LANGFLOW_ALLOW_CUSTOM_COMPONENTS=False` (beta) and `LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK=False`.
- **Update to 1.12.5.** Before 1.10.3, MCP server settings allow OS command execution (GHSA-w794-rj3p-xv45, critical).
- Guides: [Langflow auto-login: check and turn it off (in this repo)](docs/langflow-auto-login.md) · [Langflow hardening checklist](https://munimv2.github.io/langflow-hardening.html)

## Flowise

- **Flowise is archived.** Code freeze 29 July 2026, repository archived 13 August, core team gone after 31 August; its SECURITY.md no longer takes vulnerability reports. **3.1.4 is the final release.**
- **Six advisories from 10 September 2026 affect 3.1.4 and will get no official fix**, two of them critical: SSO account and invitation takeover by email match (GHSA-cffm-583c-vffr / CVE-2026-100607, GHSA-vf3j-89vf-r697 / CVE-2026-100606), plus four cross-workspace authorization bugs. Fixes matching two of them (upsert history #6680, BullMQ dashboard #6713) were merged to the archived `main` after 3.1.4 but never released.
- **Your scanner may call 3.1.4 clean.** None of the six GHSA IDs is in the GitHub Advisory Database or OSV.dev. GitHub's database holds the two critical CVEs only as unreviewed records with no package (GHSA-mjgh-prrr-9qw5, GHSA-mgrx-3hqw-485h), so Dependabot doesn't alert on them. They aren't alone: on 13 October 2026 GitHub listed 55 unreviewed Flowise advisories, and the 25 newest, eight of them critical, name no package. OSV.dev's records for the two critical CVEs list the 3.1.4 release commit as the "fix" (reported as [google/osv.dev#6149](https://github.com/google/osv.dev/issues/6149); [why it happens](docs/osv-through-read-as-fixed.md)). Check any ID with [tools/ghsa_coverage_check.py](tools/ghsa_coverage_check.py), or list them all with [tools/advisory_gap_finder.py](tools/advisory_gap_finder.py).
- **Still on 3.1.3 or older? Dependabot won't flag that either.** Two critical Custom MCP code-execution advisories fixed in 3.1.4 ([GHSA-vcwp-f9rq-3887](https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-vcwp-f9rq-3887), [GHSA-x7x8-95gh-42xm](https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-x7x8-95gh-42xm), 31 August 2026) were never imported; their CVEs (CVE-2026-91931, CVE-2026-91932) are unreviewed records with no package. Upgrade to 3.1.4.
- **While you still run it:** be on 3.1.4; use one strictly email-verifying SSO provider, or none; one instance per team you trust; block `/admin/queues` at the proxy in queue mode; publish port 3000 as `127.0.0.1:3000:3000` and keep it off the public internet.
- **Plan a move** (Langflow, Dify and n8n are maintained; none imports Flowise flows). Back up the `.flowise` data folder with its secret key first. Vet any community fork before trusting it with your provider keys.
- Guides: [Flowise is archived (in this repo)](docs/flowise-archived.md) · [Flowise is archived: what to do](https://munimv2.github.io/flowise.html)

## RAGFlow

- **0.25.2 to 0.27.2 have GHSA-c6q8-23rp-32cv**, where an OpenAI-compatible agent completion request skips the private-agent check for any signed-in user who knows the agent's ID. No 0.x release fixes it, and the advisory still lists no patched version.
- **Fix status (checked 12 October 2026):** the Python fix, [PR #19817](https://github.com/infiniflow/ragflow/pull/19817) (merged 18 September), is in `v1.0.0-rc1` and not in `v0.27.2`. But 1.0.0-rc1's `docker/.env` sets `API_PROXY_SCHEME=go`, so by default the new Go server handles that request, and the advisory doesn't say whether the Go path is covered. Treat 1.0.0-rc1 as probably fixed, not confirmed. It's a release candidate with a one-way data migration: back up and test on a copy.
- **Older releases have critical template-injection, Zip Slip and token-prediction flaws** (0.24.0 and earlier). Stay on 0.27.2 at least.
- **Until a confirmed fix ships:** only give accounts to people you trust, turn off open sign-up (`REGISTER_ENABLED=0`), and keep it off the public internet.
- **Default Compose publishes its databases on every interface with shared default passwords** (1.0.0-rc1 adds NATS, Kvrocks and ClickHouse to the default profiles). Replace every default password in `docker/.env` before the first start and bind internal ports to `127.0.0.1`.
- Advisories: [RAGFlow page](https://munimv2.github.io/ragflow.html)

## AnythingLLM

- **Update past 1.16.1.** The September 2026 advisories include one where, on single-user instances, anonymous visitors to an **embed widget** get the owner's private Memories (GHSA-8wh8-3v68-whwj).
- **Default port 3001.** Publish it as `127.0.0.1:3001:3001` unless you mean to share it, and use multi-user mode with passwords if others do use it.
- Advisories: [AnythingLLM page](https://munimv2.github.io/anythingllm.html)

## Guides in this repo

- [Use Ollama remotely without exposing it](docs/ollama-remote-access.md): SSH tunnel, Open WebUI over Tailscale Serve, why `tailscale serve 11434` gets 403 (Ollama's Host check) and two fixes, a LAN-only firewall rule for Linux and Windows, and LM Studio.
- [Ollama API key: your local Ollama has none](docs/ollama-api-key.md): Caddy and nginx Bearer-key configs, tests including the bypass, and client settings for n8n, Open WebUI, the OpenAI SDK and ollama-python.
- [Open WebUI behind nginx or Caddy](docs/openwebui-reverse-proxy.md): the WebSocket 403, garbled streaming, sign-outs on reload and OAuth `http://` redirects, with Caddy and nginx configs, the env settings (`CORS_ALLOW_ORIGIN`, `WEBUI_URL`, cookies, `FORWARDED_ALLOW_IPS`), Nginx Proxy Manager notes and tests.
- [Open WebUI: ENABLE_SIGNUP=false and sign-up still open](docs/openwebui-signup-still-open.md): which settings are stored in the database, a one-line check, three fixes.
- [vLLM `--api-key` doesn't cover every endpoint](docs/vllm-api-key.md): the routes it leaves open, an allowlist proxy for Caddy or nginx, and tests.
- [LiteLLM proxy hardening](docs/litellm-hardening.md): the master key as Admin UI password, `LITELLM_SALT_KEY`, `EXPERIMENTAL_UI_LOGIN`, stdio MCP, and keeping port 4000 private.
- [n8n security checklist](docs/n8n-hardening.md): four ways to fix the secure-cookie error without turning it off (localhost, Tailscale Serve, a local certificate, a reverse proxy), keeping 5678 private, `n8n audit`, the 2.0 defaults to keep, SSRF protection, webhook auth, the encryption key, and a Compose file that puts it together.
- [Dify security checklist](docs/dify-hardening.md): `INIT_PASSWORD` for the setup page, the published `SECRET_KEY`, the ports Compose publishes, URLs, cookies and CORS, sign-in settings, the bundled services' default passwords, the SSRF proxy and sandbox, and tests.
- [Dify: the SECRET_KEY your upgraded .env may still have](docs/dify-secret-key.md): a 10-second check and how to replace it.
- [Langflow auto-login](docs/langflow-auto-login.md): a one-request check, the `.env` that turns it off, CORS, the secret key and port 7860.
- [Flowise is archived](docs/flowise-archived.md): the six advisories that will never be fixed, why scanners miss them (including OSV.dev's wrong "fixed" commit), mitigations and planning a move.
- [ComfyUI `--listen` safely](docs/comfyui-listen.md): what bare `--listen` binds, naming addresses, Tailscale Serve from a phone, `--enable-cors-header`, the "non matching host and origin" 403 and ComfyUI-Manager.
- [When OSV.dev calls the last vulnerable version "fixed"](docs/osv-through-read-as-fixed.md): which records are affected (Flowise, LightLLM), why the converter does it, and how to check any record.
- [Dependabot-blind advisories in self-hosted AI apps](docs/dependabot-blind-ai-advisories.md): how many unreviewed advisories (which Dependabot ignores) each app has, with the searches to re-check them, what that means if you run one, and how to close a gap through GitHub's "Suggest improvements" form.

## Check it automatically

- **[local-ai-checkup](https://github.com/munimv2/local-ai-checkup):** one read-only, dependency-free Python script. It finds the AI apps above on your machine, shows which ports other machines can reach, which versions have known advisories (including ones without CVE IDs), unsafe settings, and GPU/model fit. It sends nothing anywhere.
- **[ai-stack-advisories](https://github.com/munimv2/ai-stack-advisories):** a GitHub Action and CLI that flags affected versions pinned in your compose files, Dockerfiles, requirements and package.json.
- **[tools/osv_record_check.py](tools/osv_record_check.py)** (in this repo, Apache-2.0): give it CVE or GHSA IDs and it flags OSV.dev records that list the last affected version as fixed. Standard library only, exits 1 on a suspect record so it can run in CI. `python3 tools/osv_record_check.py CVE-2026-100607`
- **[tools/ghsa_coverage_check.py](tools/ghsa_coverage_check.py)** (in this repo, Apache-2.0): give it GHSA or CVE IDs and it tells you whether Dependabot can alert on each one: missing from the global GitHub Advisory Database (a repository advisory not imported yet), or imported with no package (with the link to suggest one). Standard library only, no token, exits 1 on a gap. `python3 tools/ghsa_coverage_check.py GHSA-cffm-583c-vffr CVE-2026-100607`
- **[tools/advisory_gap_finder.py](tools/advisory_gap_finder.py)** (in this repo, Apache-2.0): for people who fix advisory data. Point it at a local clone of [github/advisory-database](https://github.com/github/advisory-database) and it lists every unreviewed record with no package (the ones Dependabot can't alert on), most severe first, sorted into three kinds: the project's own repository advisory exists but was never imported (copy its packages into GitHub's "Suggest improvements" form), a duplicate of a reviewed advisory, or no upstream at all. It also flags records with no summary, since that form needs a Title. Offline, standard library only. `git clone --depth 1 https://github.com/github/advisory-database && python3 tools/advisory_gap_finder.py advisory-database --repo FlowiseAI/Flowise --severity critical,high`
- **[CVE checker](https://munimv2.github.io/):** type a product and version, get the advisories that apply, in your browser.

### Or have it checked for you

Running this for staff or clients, and want someone to read the output for you? MV2 writes a plain-language report from the free script's output: every finding explained, the exact commands for your OS, an ordered fix list, and model picks that fit your hardware. [See a sample report](https://munimv2.github.io/sample-report.html).

1. Pay: [$49 for one machine](https://buy.stripe.com/5kQcN43Gcfii6Jo47L3Ru00) or [$199 for a small office](https://buy.stripe.com/aFabJ0foU2vw6Jo8o13Ru01) (up to 5 machines, or one shared Open WebUI / Ollama server plus its clients).
2. Run `python3 local_ai_checkup.py --json > checkup.json` on each machine and email the files, your OS and what you use local AI for to munimversion2@gmail.com.
3. The report arrives within 48 hours, with one follow-up question answered by email.

Reports are prepared with AI agents working for MV2. Each is general technical information, not a certification. MV2 never asks for passwords, keys or remote access, and the script's JSON holds no secret values (only the names of key variables).

---

General technical information, not a security certification or professional advice. Settings change between releases; check them against your version. Text licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); code in `tools/` licensed Apache-2.0. Written by MV2 of Munim, Inc., with AI agents. Contact: munimversion2@gmail.com.
