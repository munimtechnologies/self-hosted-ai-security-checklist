# Ollama API key: your local Ollama has none. How to require one (Caddy or nginx) and still use Open WebUI, n8n and OpenAI clients

*Part of the [self-hosted AI security checklist](../README.md). Written by MV2 of Munim, Inc., with AI agents, and checked against the Ollama, n8n, Open WebUI and Caddy docs on 12 October 2026. Longer version with LAN-only TLS options and a Docker Compose example: [munimv2.github.io/ollama-api-key.html](https://munimv2.github.io/ollama-api-key.html).*

Search "Ollama API key" and you'll mostly find `OLLAMA_API_KEY`. That key is for **ollama.com**, Ollama's cloud. It does nothing for the server on your own machine. Ollama's docs say it plainly: "The local API at `http://localhost:11434` does not require authentication." No setting turns a login on.

That's fine while Ollama listens on `127.0.0.1`, the default. It stops being fine once you set `OLLAMA_HOST=0.0.0.0` so another computer, a Docker container or n8n can reach it. From then on, anyone who can reach port 11434 can run prompts on your GPU and pull, create or delete models.

**The fix:** keep Ollama on `127.0.0.1` and make a reverse proxy that checks an `Authorization: Bearer <key>` header the only way in. That header is exactly what OpenAI-style clients, n8n and Open WebUI send when you fill in an "API key" field.

## Make a key

```bash
openssl rand -hex 32
```

## Caddy

```
ollama.example.com {
    @key header Authorization "Bearer PASTE_YOUR_KEY_HERE"
    handle @key {
        reverse_proxy 127.0.0.1:11434 {
            header_up Host localhost:11434
            header_up -Authorization
        }
    }
    handle {
        respond "Missing or wrong API key" 401
    }
}
```

- Caddy's `header` matcher is an exact match.
- `header_up Host localhost:11434` follows the Ollama FAQ's proxy example.
- `header_up -Authorization` keeps the key from being passed on to Ollama.
- The Caddyfile now holds a secret, so make it readable only by root and Caddy.

## nginx

```nginx
map $http_authorization $ollama_key_ok {
    default                        0;
    "Bearer PASTE_YOUR_KEY_HERE"   1;
}

server {
    listen 443 ssl;
    server_name ollama.example.com;
    # ssl_certificate / ssl_certificate_key ...

    location / {
        if ($ollama_key_ok = 0) { return 401; }
        proxy_pass http://127.0.0.1:11434;
        proxy_set_header Host localhost:11434;
        proxy_set_header Authorization "";
        proxy_buffering off;
        proxy_read_timeout 600s;
    }
}
```

## Test it, including the bypass

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://ollama.example.com/api/version   # 401
curl -H "Authorization: Bearer YOUR_KEY" https://ollama.example.com/api/version  # {"version":...}
curl --max-time 5 http://<server LAN IP>:11434/api/version   # from another machine: must FAIL
```

If the last command answers, the proxy can be bypassed. Check `OLLAMA_HOST`, and check Docker's `ports:`, because on Linux ufw doesn't block ports that Docker publishes.

## Connect your apps

- **n8n:** in the Ollama credential, set Base URL to `https://ollama.example.com` and API Key to your key. n8n sends it as a Bearer token.
- **Open WebUI:** go to Admin Panel > Settings > Connections. Set the Ollama connection's URL to the proxy and put the key in its Key field. Or add the proxy as an OpenAI connection at `https://ollama.example.com/v1`.
- **OpenAI SDK and compatible tools:** `OpenAI(base_url="https://ollama.example.com/v1", api_key="YOUR_KEY")`.
- **ollama-python:** `Client(host="https://ollama.example.com", headers={"Authorization": "Bearer YOUR_KEY"})`.

**Already running Open WebUI?** It can be the gate itself. It proxies Ollama under `/ollama/` and checks its own API keys, for example `curl https://webui.example/ollama/api/tags -H "Authorization: Bearer <your Open WebUI key>"`. Open WebUI's API keys are off by default since 0.6.37: turn them on with `ENABLE_API_KEYS=true` (or the toggle in Admin > Settings > General). Only admins can create them unless you also set `USER_PERMISSIONS_FEATURES_API_KEYS=true`, and `ENABLE_API_KEYS_ENDPOINT_RESTRICTIONS` can limit what a key may call.

## Basic auth isn't enough for apps

Basic auth works for browsers and `curl -u`. API clients send `Authorization: Bearer`, so basic auth rejects them. That mismatch is usually why people give up and leave port 11434 open.

## Related

- [Is my Ollama exposed?](https://munimv2.github.io/secure-ollama.html)
- [Use Ollama from another computer or a phone without exposing it](https://munimv2.github.io/ollama-remote-access.html) (SSH tunnel, Tailscale, and why `tailscale serve` in front of Ollama gets a 403)
- [One-click browser check](https://munimv2.github.io/ollama-origins-check.html): can websites you visit read your local Ollama? It only contacts 127.0.0.1.
- [local-ai-checkup](https://github.com/munimtechnologies/local-ai-checkup): a read-only script that shows which AI ports other machines can reach.

---

General technical information, not a security certification or professional advice. Text licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Written by MV2 of Munim, Inc., with AI agents. Corrections are welcome as issues.
