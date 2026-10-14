# vLLM `--api-key` doesn't cover every endpoint. How to lock vLLM down with an allowlist proxy (Caddy or nginx)

*Part of the [self-hosted AI security checklist](../README.md). Written by MV2 of Munim, Inc., with AI agents, and checked against vLLM's [security guide](https://github.com/vllm-project/vllm/blob/main/docs/usage/security.md), the `vllm serve` reference and the Caddy matcher docs on 12 October 2026, with vLLM 0.31.0 the latest release. Longer version with a Docker Compose example and multi-node notes: [munimv2.github.io/vllm-api-key.html](https://munimv2.github.io/vllm-api-key.html).*

`vllm serve --api-key ...` looks like it puts your server behind a key. It doesn't, not entirely. vLLM's own security guide says the key applies "only for endpoints under the `/v1`, `/v2`, `/inference`, and `/cohere` path prefixes", and lists the routes that "do not require authentication even when `--api-key` is configured":

- **Inference:** `/invocations` (the same models as `/v1`), `/generative_scoring`, `/pooling`, `/classify`, `/score`, `/rerank`
- **Operational control:** `/pause`, `/resume`, `/is_paused`, `/abort_requests`, `/update_weights`, `/init_weight_transfer_engine`, `/scale_elastic_ep`, `/fault_tolerance/apply` and more
- **Utility:** `/metrics`, `/tokenize`, `/detokenize`, `/health`, `/ping`, `/version`, `/load`

So anyone who can reach the port can run prompts on your GPU through `/invocations`, pause the server or cancel other people's requests, key or no key. The guide's advice: "Do not rely exclusively on `--api-key` for securing access to vLLM." There is no setting that extends the key to every route.

Second surprise: **`vllm serve` listens on every interface by default.** Without `--host`, the launcher binds to all interfaces and prints `http://0.0.0.0:8000`. Docker's `-p 8000:8000` does the same on the host and, on Linux, skips ufw and firewalld.

**The fix:** bind vLLM to `127.0.0.1` (or keep it on a private Docker network) and put a reverse proxy in front that passes *only* the routes your apps use, with a key, and answers everything else with 404.

## 1. Bind vLLM to localhost and set a key

```bash
openssl rand -hex 32                      # make a key
export VLLM_API_KEY='PASTE_YOUR_KEY_HERE' # env var, not --api-key: ps shows command lines
vllm serve Qwen/Qwen3-8B --host 127.0.0.1 --port 8000 --disable-fastapi-docs
```

- Keep the key in vLLM as well as in the proxy, so a mistake in one layer doesn't leave `/v1` open.
- `--disable-fastapi-docs` removes the Swagger UI and OpenAPI schema, which list every route.
- Never set `VLLM_SERVER_DEV_MODE=1` on a server others can reach. It adds `/collective_rpc`, which the guide calls "extremely dangerous", plus `/sleep` and cache-reset routes. Leave the profiler and `--enable-tokenizer-info-endpoint` off too.
- With Docker Compose, give the `vllm` service no `ports:` and publish only the proxy. With `docker run`, use `-p 127.0.0.1:8000:8000`.

If only programs on the same machine use vLLM, this step is enough. Check it with the last test in step 4.

## 2. Caddy: allow only what your apps call

Most OpenAI-style clients need four routes:

```
llm.example.com {
    @api path /v1/chat/completions /v1/completions /v1/embeddings /v1/models
    @api_with_key {
        path /v1/chat/completions /v1/completions /v1/embeddings /v1/models
        header Authorization "Bearer PASTE_YOUR_KEY_HERE"
    }

    handle @api_with_key {
        reverse_proxy 127.0.0.1:8000 {
            flush_interval -1
        }
    }
    handle @api {
        respond "Missing or wrong API key" 401
    }
    handle {
        respond 404
    }
}
```

- Inside one named matcher, all matcher types must match: an allowed path *and* the exact header.
- `path` is an exact match, so `/invocations`, `/tokenize`, `/pause`, `/metrics` and everything else gets 404. Add routes only when an app needs them (for example `/v1/responses` or `/v1/rerank`).
- `flush_interval -1` streams tokens as they arrive.
- The Caddyfile now holds a secret: `sudo chown root:caddy /etc/caddy/Caddyfile && sudo chmod 640 /etc/caddy/Caddyfile`.

## 3. Or nginx

```nginx
map $http_authorization $vllm_key_ok {
    default                        0;
    "Bearer PASTE_YOUR_KEY_HERE"   1;
}

server {
    listen 443 ssl;
    server_name llm.example.com;
    # ssl_certificate / ssl_certificate_key ...

    location ~ ^/v1/(chat/completions|completions|embeddings|models)$ {
        if ($vllm_key_ok = 0) { return 401; }
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 600s;
    }

    location / {
        return 404;   # /invocations, /tokenize, /pause, /docs ...
    }
}
```

Put it in `/etc/nginx/conf.d/` (where `map` is valid), `sudo chmod 600` the file, then `sudo nginx -t && sudo systemctl reload nginx`.

## 4. Test it

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://llm.example.com/v1/models              # 401
curl -H "Authorization: Bearer YOUR_KEY" https://llm.example.com/v1/models             # your model
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://llm.example.com/invocations   # 404
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://llm.example.com/pause         # 404
curl --max-time 5 http://<server LAN IP>:8000/version   # from ANOTHER machine: must FAIL
```

If the last one prints a version, the proxy can be bypassed. Check `--host`, Docker `ports:`, and `ss -tlnp | grep 8000` (it should show `127.0.0.1:8000`, not `0.0.0.0:8000` or `*:8000`).

## Mistakes to avoid

- **Proxying `/` with a key check.** Better than nothing, but anyone with the key still reaches `/pause` and `/update_weights`. Allow named routes only.
- **Forgetting multi-node traffic.** The proxy protects HTTP only. vLLM's guide calls inter-node traffic (PyTorch distributed, KV-cache transfer) "insecure by default". Keep nodes on an isolated network and set `VLLM_HOST_IP` to the private address.
- **Treating the proxy as the whole fix.** Key holders still reach the inference code most of 2026's vLLM advisories are in, many with no CVE ID. The October 2026 batch needs 0.31.0; check yours with the [CVE checker](https://munimv2.github.io/index.html?product=vllm).

## Related

- [vLLM advisories, by version](https://munimv2.github.io/vllm.html)
- [Ollama API key](ollama-api-key.md): the same proxy idea for Ollama, which has no key at all.
- [local-ai-checkup](https://github.com/munimv2/local-ai-checkup): a read-only script that shows which AI ports other machines can reach, including vLLM's.

---

General technical information, not a security certification or professional advice. Endpoint lists change between releases; re-check after updating. Text licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Written by MV2 of Munim, Inc., with AI agents. Corrections are welcome as issues.
