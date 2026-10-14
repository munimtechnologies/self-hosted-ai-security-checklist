# Self-hosted n8n security checklist

By MV2 of Munim, Inc., with AI agents. Checked against n8n's docs ([2.0 breaking changes](https://docs.n8n.io/2-0-breaking-changes/), [security variables](https://docs.n8n.io/hosting/configuration/environment-variables/security/), [deployment variables](https://docs.n8n.io/hosting/configuration/environment-variables/deployment/), [SSRF protection](https://docs.n8n.io/hosting/configuration/environment-variables/ssrf-protection/), [security audit](https://docs.n8n.io/hosting/securing/security-audit/), [webhook URL behind a proxy](https://docs.n8n.io/hosting/configuration/configuration-examples/webhook-url/), [Webhook node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)) on 12 October 2026, when the latest stable n8n was 2.42.6; the secure-cookie section was extended on 13 October with [Tailscale Serve](https://tailscale.com/kb/1312/serve) and local certificates. For your own instances only.

n8n holds the keys to everything it automates: email, CRMs, databases, cloud accounts and AI APIs. In September 2026 alone it published more than 40 security advisories, several exploitable without a login. Work through these steps in order.

## 1. Update first

Stable 2.x: **2.41.4 or newer** (2.42.6 was current on 12 October 2026). 1.x: **1.123.83 or newer**. Most of the September advisories have no CVE ID, so `npm audit` and Dependabot don't flag them; compare your version with [n8n's security advisories](https://github.com/n8n-io/n8n/security/advisories) or type it into the [CVE checker](https://munimv2.github.io/index.html?product=n8n).

Pin an exact image tag such as `docker.n8n.io/n8nio/n8n:2.42.6` rather than `latest`, so you know what you run and update on purpose. The free [ai-stack-advisories](https://github.com/munimtechnologies/ai-stack-advisories) GitHub Action can then flag a pinned version in your compose file once an advisory comes out for it.

## 2. "Your n8n server is configured to use a secure cookie": fix it with HTTPS

You see this when you open n8n over plain `http://` (for example `http://192.168.1.20:5678` or a NAS address), or in Safari. `N8N_SECURE_COOKIE` is `true` by default, so the browser only sends the login cookie over HTTPS. Many guides tell you to set `N8N_SECURE_COOKIE=false`. **Don't**: your session cookie would then cross the network in clear text, and anyone who copies it is signed in as you. Pick the fix that matches who uses n8n:

- **Only you, on the same machine:** open `http://localhost:5678` in Chrome, Edge or Firefox, which treat `localhost` as secure. Safari still refuses it; use one of the fixes below there.
- **Your own devices on a home network or NAS:** if they're on your tailnet, `tailscale serve 5678` gives n8n an HTTPS address such as `https://nas.your-tailnet.ts.net` without opening any port (Serve needs HTTPS certificates enabled for the tailnet; the CLI offers to turn them on). Set `N8N_HOST`, `N8N_PROTOCOL=https` and `WEBHOOK_URL` to that address. Webhooks are then reachable only from your tailnet.
- **LAN only, no Tailscale:** use a local certificate. Caddy with `tls internal` issues one from its own local CA:

  ```
  n8n.home.arpa {
      tls internal
      reverse_proxy 127.0.0.1:5678
  }
  ```

  Point the name at the server in your router's DNS or the clients' hosts files, and import Caddy's local root certificate (`pki/authorities/local/root.crt` in Caddy's data directory) on each client; `caddy trust` does it on the server itself. Or let n8n serve HTTPS itself: `N8N_PROTOCOL=https` with `N8N_SSL_KEY` and `N8N_SSL_CERT` pointing at a key and certificate (for example from [mkcert](https://github.com/FiloSottile/mkcert)).
- **Reachable from the internet:** put a reverse proxy with a public certificate in front. Caddy gets one on its own and passes the `X-Forwarded-*` headers and websockets without extra settings:

  ```
  n8n.example.com {
      reverse_proxy 127.0.0.1:5678
  }
  ```

  With nginx, pass `Host`, `X-Forwarded-For`, `X-Forwarded-Host` and `X-Forwarded-Proto`, plus the websocket `Upgrade`/`Connection` headers, and set `proxy_http_version 1.1`.

Then tell n8n its public address. `N8N_PROXY_HOPS=1` makes it trust exactly one proxy when it works out a client's IP, which the login rate limiter relies on:

```
N8N_HOST=n8n.example.com
N8N_PROTOCOL=https
WEBHOOK_URL=https://n8n.example.com/
N8N_PROXY_HOPS=1
```

Already ran with `N8N_SECURE_COOKIE=false`? Remove it, restart, and sign in again over HTTPS. If you used n8n that way over shared or public Wi-Fi, change your password and review the users and API keys on the instance.

## 3. Keep port 5678 private

If `5678` is still reachable, people can skip the proxy and its TLS. With Docker, `-p 5678:5678` (or `ports: ["5678:5678"]`) publishes it on every interface, and on Linux ufw doesn't block ports that Docker publishes. Use `127.0.0.1:5678:5678`, or no `ports:` at all when the proxy runs in the same Compose file.

**Test** from another machine: `curl -I --max-time 5 http://<server IP>:5678` should fail to connect.

## 4. Run n8n's own audit

```
n8n audit
# Docker:
docker exec -it <container> n8n audit
```

It reports on five areas: credentials that nothing uses, SQL nodes with expressions in their queries, nodes that touch the file system, risky official and community nodes, and the instance itself (unprotected webhooks, missing security settings, an outdated version). It can also run as a workflow (n8n node: Resource *Audit*, Operation *Generate*), for example on a weekly schedule.

## 5. Keep the 2.0 safety defaults

n8n 2.0 tightened several defaults. Old guides and workflows often switch them back off, so check your environment for these:

- `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`: the Code node and expressions can't read environment variables, which often hold database passwords and `N8N_ENCRYPTION_KEY`. It's the 2.0 default, but the variables reference still lists `false`, so set it explicitly. Put secrets in n8n credentials instead.
- **Execute Command and Local File Trigger stay off:** 2.0 disables them through `NODES_EXCLUDE`. `NODES_EXCLUDE="[]"` turns every node back on; if you really need one, re-enable only that one.
- **File access stays in `~/.n8n-files`:** the Read/Write Files from Disk nodes are limited to that folder by default. If you widen it with `N8N_RESTRICT_FILE_ACCESS_TO`, list specific folders, never `/`.
- **Task runners stay in secure mode:** Code node runs are isolated on task runners. Don't leave `N8N_RUNNERS_INSECURE_MODE=true` on in production; n8n itself calls it a temporary workaround.
- `N8N_GIT_NODE_DISABLE_BARE_REPOS=true` and `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true`: 2.0 defaults that the variables reference may still show as `false`. Set them explicitly too. The Git node was behind two 2026 code execution advisories (July and September).
- **Old basic-auth settings do nothing.** `N8N_BASIC_AUTH_ACTIVE` and its relatives were removed in n8n 1.0. n8n's own user accounts are the login now, so create the owner account right after the first start, before the server is reachable from the network.

## 6. Turn on SSRF protection (n8n 2.12.0 and newer)

Without it, anyone who can edit a workflow can make n8n call your internal network or a cloud metadata address. It's off by default:

```
N8N_SSRF_PROTECTION_ENABLED=true
N8N_SSRF_BLOCKED_IP_RANGES=default
```

`default` blocks private networks (10/8, 172.16/12, 192.168/16), loopback and link-local addresses, including 169.254.169.254. If a workflow needs one internal service, such as Ollama, allow just that service. Allow entries override blocks:

```
N8N_SSRF_ALLOWED_HOSTNAMES=ollama
# or one address:
N8N_SSRF_ALLOWED_IP_RANGES=172.17.0.1/32
```

n8n calls this an extra layer on top of firewall rules, not a replacement for them.

## 7. Protect webhooks

Production webhook URLs are public by design: anyone who learns the URL can start the workflow. In each Webhook node, set **Authentication** to Header auth, Basic auth or JWT auth unless the caller can't send credentials. Where the caller has fixed addresses, also fill in **IP(s) Allowlist**; requests from other addresses get a 403. If a browser page doesn't call the webhook, change **Allowed Origins (CORS)** from `*` to the page that does. `n8n audit` lists the webhooks that have no authentication.

## 8. Close what you don't use

- Public REST API and its playground, if nothing calls them: `N8N_PUBLIC_API_DISABLED=true` and `N8N_PUBLIC_API_SWAGGERUI_DISABLED=true`.
- Unverified community nodes run with n8n's full access. Set `N8N_UNVERIFIED_PACKAGES_ENABLED=false` (n8n's 3.0 notes make it the default) unless you've reviewed the package.
- Two-factor authentication: have every user turn it on. Recent versions can enforce it for all users (`N8N_MFA_ENFORCED_ENABLED=true` with `N8N_SECURITY_POLICY_MANAGED_BY_ENV=true`, or in the security settings) where your edition offers it.

## 9. Guard the encryption key

n8n encrypts stored credentials with `N8N_ENCRYPTION_KEY`. If you don't set it, n8n generates one in `~/.n8n/config` inside its data volume. Set it explicitly, keep a copy somewhere safe, and keep it out of Git. If you lose it, every stored credential is unreadable. If it leaks along with a database backup, every credential is exposed. Keep backups of the `/home/node/.n8n` volume and the database as private as the key.

## Putting it together (Docker Compose)

```yaml
services:
  n8n:
    image: docker.n8n.io/n8nio/n8n:2.42.6
    restart: unless-stopped
    ports: [ "127.0.0.1:5678:5678" ]      # only the proxy on this host
    env_file: .env                         # N8N_ENCRYPTION_KEY=... (chmod 600, not in Git)
    environment:
      - N8N_HOST=n8n.example.com
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://n8n.example.com/
      - N8N_PROXY_HOPS=1
      - N8N_BLOCK_ENV_ACCESS_IN_NODE=true
      - N8N_GIT_NODE_DISABLE_BARE_REPOS=true
      - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
      - N8N_SSRF_PROTECTION_ENABLED=true
      - N8N_SSRF_BLOCKED_IP_RANGES=default
      - N8N_PUBLIC_API_DISABLED=true
      - N8N_PUBLIC_API_SWAGGERUI_DISABLED=true
      - N8N_UNVERIFIED_PACKAGES_ENABLED=false
    volumes: [ "n8n_data:/home/node/.n8n" ]
volumes:
  n8n_data: {}
```

Leave out `N8N_PUBLIC_API_DISABLED` if you use the API, and add `N8N_SSRF_ALLOWED_HOSTNAMES` for internal services your workflows call. Then run `docker compose up -d` and `docker exec -it <container> n8n audit`. To connect n8n in Docker to Ollama on the host without exposing Ollama, see [Docker apps can't reach Ollama](https://munimv2.github.io/docker-ollama.html). To use a remote Ollama behind a key, see [ollama-api-key.md](ollama-api-key.md).

## If an old, exposed n8n ran for a while

Update first. Then review the users, API keys and OAuth clients on the instance, and look for executions and workflows you don't recognise. Rotate the stored credentials, starting with those that can send email, move money or reach production systems.

---

General technical information, not a security certification or professional advice. Variable names and defaults come from the linked n8n docs as of 12 October 2026; check the docs for your version before changing production. Corrections are welcome as issues in this repo. Written by MV2 of Munim, Inc., with AI agents.
