# Open WebUI behind nginx or Caddy: fix the WebSocket and streaming errors without opening it up

Written by MV2 of Munim, Inc., with AI agents. Checked on 12 and 13 October 2026 against Open WebUI's [nginx guide](https://docs.openwebui.com/reference/https/nginx/), [HTTPS and reverse proxy reference](https://docs.openwebui.com/reference/https/), [connection error guide](https://docs.openwebui.com/troubleshooting/connection-error/), [hardening guide](https://docs.openwebui.com/getting-started/advanced-topics/hardening/) and the [0.12.0 release notes](https://github.com/open-webui/open-webui/releases/tag/v0.12.0) (0.12.0, 10 October 2026, is the latest release). For your own servers only.

Contents: [Symptoms](#the-symptoms-and-the-shortcuts-to-skip) · [1. Keep it behind the proxy](#1-keep-open-webui-reachable-only-by-the-proxy) · [2. Settings](#2-settings-open-webui-needs-behind-a-proxy) · [3a. Caddy](#3a-caddy) · [3b. nginx](#3b-nginx) · [4. Test it](#4-test-it) · [5. While you're there](#5-while-youre-there)

## The symptoms, and the shortcuts to skip

After putting Open WebUI behind a proxy, the usual problems are:

- **"WebSocket connection failed"**, or a 403 on `/ws/socket.io` in the browser console
- answers that **stall or arrive as garbled markdown**
- being **signed out on every reload**
- OAuth sign-in sending you back to an **`http://` address**

They come from four settings: WebSocket headers, proxy buffering, `CORS_ALLOW_ORIGIN` and `WEBUI_URL`.

Shortcuts that make the error go away but leave the server open:

- **Publishing port 3000 to the whole network** "to test without the proxy", and leaving it that way. Anyone who reaches port 3000 skips your proxy, its TLS and its logs.
- **Leaving `CORS_ALLOW_ORIGIN` at `*`**, the default. Open WebUI logs a warning at startup for it. Set your own address instead; that's also what fixes the WebSocket error.
- **Exposing a fresh install before you've signed up.** Sign-up is open until the first account is created, and that first account becomes the admin. If a stranger gets there first, they own the server. Create your admin account while it's still local, or set `WEBUI_ADMIN_EMAIL`, `WEBUI_ADMIN_PASSWORD` and `WEBUI_ADMIN_NAME` for the first start.
- **Turning sign-ups back on** for a coworker and leaving them on. If you need it, keep `DEFAULT_USER_ROLE=pending` (the default) so new accounts wait for your approval, and turn it off again afterwards. If `ENABLE_SIGNUP=false` doesn't seem to work, see [ENABLE_SIGNUP=false and sign-up still open](openwebui-signup-still-open.md).

## 1. Keep Open WebUI reachable only by the proxy

Open WebUI listens on port 8080 inside its container. Publish it on the host's loopback address only, so the proxy on the same host can reach it and other machines can't:

```bash
docker run -d --name open-webui --restart always \
  -p 127.0.0.1:3000:8080 \
  -v open-webui:/app/backend/data \
  --env-file /etc/open-webui.env \
  ghcr.io/open-webui/open-webui:main
```

If the proxy runs in Docker too, put both on one Compose network, give Open WebUI no `ports:` at all, and point the proxy at `open-webui:8080`. On Linux, ports Docker publishes skip ufw and firewalld, so `127.0.0.1:` (or no `ports:`) is what actually keeps it private.

A pip install listens on port 8080; start it with `open-webui serve --host 127.0.0.1`.

## 2. Settings Open WebUI needs behind a proxy

Put these in `/etc/open-webui.env` (readable only by root: `sudo chmod 600 /etc/open-webui.env`), with your own address:

```ini
WEBUI_URL=https://chat.example.com
CORS_ALLOW_ORIGIN=https://chat.example.com
WEBUI_SESSION_COOKIE_SECURE=true
WEBUI_SECRET_KEY=PASTE_OUTPUT_OF_openssl_rand_-base64_32
JWT_EXPIRES_IN=24h
```

- **`CORS_ALLOW_ORIGIN`:** Open WebUI's nginx guide says you "must" set it behind a reverse proxy: "Failure to do so will cause WebSocket connections to fail." List several addresses separated by semicolons, for example `https://chat.example.com;https://chat.lan`.
- **`WEBUI_URL`:** used for OAuth callbacks and links. It's saved in the database on first start, so if Open WebUI has already run, change it under *Admin Panel > Settings > General* instead; editing the variable alone won't take effect. The same is true of `JWT_EXPIRES_IN`, sign-up and many other settings ([why](openwebui-signup-still-open.md)).
- **`WEBUI_SESSION_COOKIE_SECURE=true`:** the cookie is only sent over HTTPS. The hardening guide also suggests `WEBUI_SESSION_COOKIE_SAME_SITE=strict`. If you sign in with OAuth and that breaks the sign-in, the `WEBUI_AUTH_COOKIE_*` variables set the OAuth cookies separately.
- **`WEBUI_SECRET_KEY`:** signs sign-in tokens. Without it, Open WebUI generates one in `/app/backend/.webui_secret_key`, outside the data volume, so recreating the container can sign everyone out. Changing it signs everyone out. If users have two-factor sign-in, set `MFA_ENCRYPTION_KEY` before they enroll, or Open WebUI won't start after a key change.
- **`JWT_EXPIRES_IN`:** the default is 4 weeks; the hardening guide suggests 8 to 24 hours.
- **`FORWARDED_ALLOW_IPS`:** which connections may set the client address through forwarded headers. The default `*` is safe only when nothing but your proxy can reach Open WebUI, which step 1 ensures. Otherwise anyone can fake their address, which, per the hardening guide, "defeats the per-address sign-in limit and falsifies the address in audit logs." Set it to the address your proxy connects from. Before 0.12.0, `open-webui serve` (pip installs) ignored this setting and trusted every connection.

Recreate the container after editing the file (`docker rm -f open-webui`, then the `docker run` above; your data is in the volume).

## 3a. Caddy

Caddy passes WebSockets and streams server-sent events without extra settings, and gets an HTTPS certificate on its own when the domain points at this machine:

```
chat.example.com {
    request_body {
        max_size 100MB
    }
    reverse_proxy 127.0.0.1:3000
}
```

For a LAN-only name such as `chat.home`, add `tls internal` inside the block and install Caddy's root certificate on your devices. `WEBUI_SESSION_COOKIE_SECURE=true` needs HTTPS, so don't fall back to plain `http://`. To reach it from your phone without opening a port, see [remote access without exposing it](ollama-remote-access.md).

## 3b. nginx

A trimmed version of the config in Open WebUI's nginx guide. Put it in `/etc/nginx/conf.d/open-webui.conf` and use your own certificate paths:

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    listen 80;
    server_name chat.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;                      # nginx before 1.25.1: "listen 443 ssl http2;" instead
    server_name chat.example.com;
    ssl_certificate     /etc/letsencrypt/live/chat.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chat.example.com/privkey.pem;

    client_max_body_size 100M;     # file and document uploads

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;    # needed for WebSockets
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;       # garbled or stalled streaming otherwise
        proxy_cache off;
        proxy_read_timeout 1800s;  # long answers
        proxy_send_timeout 1800s;
    }
}
```

Then `sudo nginx -t && sudo systemctl reload nginx`. The guide calls `proxy_buffering`, which nginx turns on by default, "the most common cause of garbled markdown and broken streaming responses."

**Nginx Proxy Manager:** its "Websockets support" switch isn't enough on its own. The guide says WebSocket connections still fail without `CORS_ALLOW_ORIGIN`, and the `proxy_buffering off;` / `proxy_cache off;` lines go in the proxy host's *Advanced* tab under Custom Nginx Configuration.

## 4. Test it

```bash
# through the proxy: should print 200
curl -s -o /dev/null -w "%{http_code}\n" https://chat.example.com/api/version

# from ANOTHER machine, straight to Open WebUI: should fail to connect
curl --max-time 5 http://<server LAN IP>:3000/api/version
```

- In the browser, open the developer tools' Network tab, filter on `WS` and reload: `/ws/socket.io/...` should show status **101**. A 403 there usually means `CORS_ALLOW_ORIGIN` doesn't match the address in the address bar exactly (scheme, name and port).
- `docker logs open-webui 2>&1 | grep -i cors` should no longer show the warning about `*`.
- On Linux, `ss -tlnp | grep 3000` should show `127.0.0.1:3000`, not `0.0.0.0:3000`.
- Sign-up really closed? `curl -s https://chat.example.com/api/config` should show `"enable_signup": false`. If it says `true` although you set `ENABLE_SIGNUP=false`, that's [persistent config](openwebui-signup-still-open.md).

## 5. While you're there

- **Keep Ollama behind Open WebUI**, not next to it. Ollama has no login, so it shouldn't be reachable from the network at all. If another app needs it, give it a key: [Ollama API key](ollama-api-key.md).
- **API keys:** if apps use Open WebUI's API, restrict what keys can call with `ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS=true` and `API_KEYS_ALLOWED_ENDPOINTS=/api/chat/completions,/api/v1/models`.
- **Turn on two-factor sign-in** for admins (0.12.0 and newer).
- **Update.** Versions before 0.11.4 have 15+ advisories with no CVE ID, including session-token theft through `javascript:` links in chat messages (GHSA-wf9m-46cp-c6h6). Check yours with the [CVE checker](https://munimv2.github.io/?product=openwebui) or the [Open WebUI advisories page](https://munimv2.github.io/openwebui.html).

Back to the [checklist](../README.md#open-webui).

---

General technical information, not a security certification or professional advice. Only change servers you own or are allowed to manage. Setting names and defaults change between Open WebUI releases; check them against your version. Text licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Written by MV2 of Munim, Inc., with AI agents. Corrections welcome as issues. Want it checked for you? See the [$49 local AI health check](https://munimv2.github.io/sample-report.html).
