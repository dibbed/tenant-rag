# Edge Protection

Phase 3 security hardening. This feature closes audit findings C9, C10 and C11 in `docs/BASELINE_AUDIT.md` and implements requirements REQ-MTS-EDGE-001 to REQ-MTS-EDGE-004 of the Multi-Tenant Security feature. It does not change authentication or authorization.

| Area | Secure default | Settings |
|---|---|---|
| Client address | The TCP peer. `X-Forwarded-For`, `X-Real-IP` and similar headers are ignored. | `SECURITY_TRUSTED_PROXIES` |
| Rate limiting | 10 requests per 60 seconds for each principal or client address, counted per instance | `SECURITY_RATE_LIMIT_REQUESTS`, `SECURITY_RATE_LIMIT_WINDOW`, `SECURITY_RATE_LIMIT_STORAGE_URL` |
| Browser access (CORS) | No origin allowed | `SECURITY_CORS_ALLOWED_ORIGINS` |
| Request size | 50 MB | `SECURITY_MAX_FILE_SIZE_MB` |

## Request path

```text
Client
  -> TrustedProxyMiddleware    Client Address: the TCP peer, or the address a trusted proxy reports
  -> CORSMiddleware            answers preflights; CORS headers on every response, 413 and 429 included
  -> RateLimitMiddleware       requests without credentials: counted per Client Address before the body
  -> BodySizeLimitMiddleware   HTTP 413 when the declared or received body size passes the limit
  -> FastAPI routes
       enforce_rate_limit      requests with credentials: counted per Principal after authentication
       get_current_principal   failed credentials: counted per Client Address before HTTP 401
       upload route            file copied to disk in 1 MiB chunks, exact size limit
```

Code: `ragbot/api/edge/` (settings, client address, rate limiter and stores, CORS policy), `ragbot/api/middleware/trusted_proxy.py`, `ragbot/api/middleware/rate_limit.py`, `ragbot/api/middleware/body_size_limit.py`, `ragbot/api/app.py`, `ragbot/api/dependencies.py`, `ragbot/api/routes/documents.py` and `ragbot/main.py`.

## Configuration

| Variable | Default | Format | Effect |
|---|---|---|---|
| `SECURITY_TRUSTED_PROXIES` | empty | Comma-separated IP addresses and CIDR networks, for example `127.0.0.1` or `10.0.0.5,10.1.0.0/16` | Empty: forwarded headers are ignored. Otherwise `X-Forwarded-For` is used only when the TCP peer is listed. |
| `SECURITY_RATE_LIMIT_STORAGE_URL` | empty | `redis://[:password@]host:port/db` or `rediss://...` | Empty: each instance and each worker process counts on its own. Set: one shared count for all instances. |
| `SECURITY_CORS_ALLOWED_ORIGINS` | empty | Comma-separated origins, for example `https://app.example.com`, or `*` | Empty: no browser origin. `*`: every origin without credentials, only with `ENVIRONMENT=development`. |
| `SECURITY_RATE_LIMIT_REQUESTS` | `10` | Integer | Requests per Rate Limit Subject in one window. |
| `SECURITY_RATE_LIMIT_WINDOW` | `60` | Seconds | Length of the sliding window, and the TTL of shared store records. |
| `SECURITY_MAX_FILE_SIZE_MB` | `50` | Integer (MiB) | Upload and text size limit. Every request body is limited to this size plus 64 KiB for multipart framing. |

The settings are read when the application starts. These values stop startup with an error that names the setting:

- a trusted proxy entry that is not an IP address or CIDR network, or a catch-all entry (`*`, `0.0.0.0/0`, `::/0`);
- an origin with a path, query, fragment, user information or wildcard, an origin whose scheme is not `http` or `https`, and `null`;
- `SECURITY_CORS_ALLOWED_ORIGINS=*` when `ENVIRONMENT` is not `development`;
- a storage URL that is not `redis://` or `rediss://`.

At startup the service logs one line each for trusted proxies, the rate limit store mode (per instance or shared), the CORS mode and the request size limit. A trusted network wider than /16 (IPv4) or /48 (IPv6), and `WORKERS` above 1 without a shared store, log a warning.

## Behavior

### Rate limiting (C9)

- The Client Address is the TCP peer. Only when the peer is a trusted proxy does the service read `X-Forwarded-For`, from right to left, and use the first address that is not a trusted proxy. Entries that are not IP addresses are never used, and only the last 20 entries are read. `X-Real-IP`, `Forwarded`, `CF-Connecting-IP`, `True-Client-IP` and `X-Client-IP` are always ignored.
- A request that carries no `X-API-Key` or `Authorization` header counts against its Client Address before its body is read. A request with a credential counts after authentication: against its Principal (`principal:<tenant_id>:<principal_id>`) when the credential is valid, and against its Client Address when it is not. Each request counts once.
- IPv6 Client Addresses share one counter per /64 network.
- Over the limit, the answer is `HTTP 429` with `Retry-After`, `retry_after` in the body, and the `X-RateLimit-Limit`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` headers. After a run of failed credentials, the address gets `429` instead of `401` until the window passes. A valid key from the same address still works, because it counts against its own Principal.
- `/health`, `/api/v1/health` and the API documentation are never counted.
- Records are deleted when their window has passed: in memory by a sweep once per window, in Redis by the key TTL. The memory store keeps at most 100,000 subjects.

### Several instances

- Without `SECURITY_RATE_LIMIT_STORAGE_URL`, each instance counts on its own. With `WORKERS=4`, each worker process is an instance, so the effective limit is four times the setting. The startup log says so.
- With a `redis://` or `rediss://` URL, all instances share one sliding-window count in Redis: an atomic Lua script that uses the Redis server clock (Redis 5 or later). Keys are `ratelimit:v1:` followed by a SHA-256 digest of the subject, so addresses and principal ids do not appear in Redis.
- If Redis fails or takes longer than 250 ms, the request is counted per instance. It is never allowed without being counted. One warning is logged when the outage starts, Redis is tried again after 30 seconds, and one message is logged when it recovers. During an outage the effective limit is the setting times the number of instances.

### Browser access in development and production (C10)

| `ENVIRONMENT` | `SECURITY_CORS_ALLOWED_ORIGINS` | Result |
|---|---|---|
| any | empty (default) | No origin may call the API from a browser. Preflights get `HTTP 400`. |
| any | explicit list | Listed origins are allowed, with credentials. |
| `development` | `*` | Every origin is allowed, without credentials. A warning is logged. |
| any other value, or unset | `*` | Startup fails. Production must list its origins. |

- Development gets no automatic origins. List the local frontend, for example `SECURITY_CORS_ALLOWED_ORIGINS=http://localhost:3000`.
- Allowed methods are `GET` and `POST`. Allowed request headers are `Authorization`, `Content-Type`, `X-API-Key` and `X-Tenant-ID`. Browser code can read `Retry-After` and the `X-RateLimit-*` headers.
- CORS runs before rate limiting, so preflights do not use the limit, and `413` and `429` responses carry CORS headers for allowed origins.
- CORS only controls what a browser may read. Requests from other origins are still authenticated as usual.

### Request size (C11)

- Every request body is limited to `SECURITY_MAX_FILE_SIZE_MB` plus 64 KiB.
- A declared `Content-Length` above the limit gets `HTTP 413` before the body is read. With `Expect: 100-continue`, the client does not send the body at all.
- A body without a declared size, or with a false one, is counted while it is received. When it passes the limit, reading stops and the answer is `HTTP 413` with `Connection: close`.
- An invalid `Content-Length` gets `HTTP 400`.
- The upload route copies the file to disk in 1 MiB chunks and applies the exact limit: a file of exactly the limit is accepted, one byte more is refused. The text route counts UTF-8 bytes.
- Every 413 states the limit. From the edge: `{"detail": "Request body exceeds maximum allowed size of 50MB", "max_size_mb": 50, "max_size_bytes": 52428800}`. From the upload route: `{"detail": "File exceeds maximum allowed size of 50MB"}`.
- A refused upload keeps nothing: ingestion does not run and temporary files are removed.

## Migration notes

| Change | Before | After | Action |
|---|---|---|---|
| CORS default | Every origin, with credentials | No origin | Set `SECURITY_CORS_ALLOWED_ORIGINS` for browser frontends before you upgrade. Server-to-server clients are not affected. |
| `*` origins | Allowed everywhere, with credentials | Development only, without credentials | List origins in production. |
| Forwarded headers | The first `X-Forwarded-For` entry was trusted | Ignored unless the peer is in `SECURITY_TRUSTED_PROXIES` | Behind a proxy, set `SECURITY_TRUSTED_PROXIES`, or all traffic counts against the proxy address. |
| Uvicorn proxy headers | On (uvicorn default) | `python main.py` and the Docker image pass `proxy_headers=False` | Start uvicorn directly only with `--no-proxy-headers`. `FORWARDED_ALLOW_IPS` has no effect. |
| Rate limit subject | One counter per address | One counter per principal (key or session), or per address without a valid credential | Review `SECURITY_RATE_LIMIT_REQUESTS` for backends that send many requests with one key. |
| Failed credentials | Always `401` | `429` with `Retry-After` after the limit | Clients should honor `Retry-After`. |
| 413 order and text | `415` could come first; `File exceeds maximum allowed size of 50MB` | The edge `413` comes first, with the new text and numbers | Match on the status code. |
| Text limit | Characters | UTF-8 bytes; at the edge the size of the JSON body counts | Split very large texts. |
| Request body limit | None for query and URL routes | The upload limit for every route | None expected. |

Rollback: redeploy the previous version. It ignores the new variables, and Redis records expire after one window.

## Deployment requirements

- **Reverse proxy.** Keep `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;` and set `SECURITY_TRUSTED_PROXIES` to the address the proxy connects from (`127.0.0.1` for Nginx on the same host). Keep `client_max_body_size` a little above the upload limit (`60M` for 50 MB). Behind a CDN, resolve the client address in the proxy (for example with the Nginx `real_ip` module) instead of listing CDN ranges.
- **Uvicorn.** `python main.py` and the Docker image already turn off uvicorn proxy headers. A direct `uvicorn ragbot.api.app:app` command must add `--no-proxy-headers`. Never use `--forwarded-allow-ips='*'`: uvicorn then uses the address the client sends.
- **Containers.** Behind a proxy container, trust only that container's own address (a fixed address on a user-defined network), not the whole Docker network, and do not publish port 8000 on the host.
- **Several workers or instances.** Set `SECURITY_RATE_LIMIT_STORAGE_URL`. A dedicated Redis instance is best; at least use a database number that the cache does not use, because cache eviction can remove rate limit keys. The official `redis:7-alpine` image works; pin a tag or digest in production. Use `rediss://` and a password across hosts.
- **Kubernetes.** Trust the ingress controller addresses, and keep the client address at the load balancer (for example with `externalTrafficPolicy: Local`).

## Verification after deployment

```bash
# Forged headers do not reset the limit: the last call gets 429 (default limit 10)
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.example.com/api/v1/query \
    -H "X-Forwarded-For: 203.0.113.$i" -H "Content-Type: application/json" -d '{"question":"hi"}'
done

# An unlisted origin cannot read responses: HTTP 400 and no Access-Control-Allow-Origin
curl -si -X OPTIONS https://api.example.com/api/v1/query \
  -H "Origin: https://evil.example" -H "Access-Control-Request-Method: POST"

# An oversized upload is refused with the limit in the body: HTTP 413
head -c 60M /dev/zero > big.bin
curl -si -X POST https://api.example.com/api/v1/documents/upload -F "file=@big.bin"
```

## Tests

| File | Covers |
|---|---|
| `tests/security/test_edge_rate_limit.py` | Forged `X-Forwarded-For` and similar headers, trusted proxy disabled and enabled, proxy chains, IPv6 grouping, limits and `429` details, health exemption, per-principal counting, failed authentication, shared and separate instances, shared store outage, route inventory |
| `tests/security/test_edge_cors.py` | Allowed, blocked and missing origins, development and production configuration, wildcard rules, invalid entries, CORS headers on `413` and `429`, preflights and the rate limit, middleware order |
| `tests/security/test_edge_upload_limits.py` | Normal upload, exactly at the limit, one byte above, declared and huge sizes, streamed and false sizes, invalid `Content-Length`, UTF-8 text limit, memory use for large uploads and refusals, no files left |
| `tests/unit/test_edge_client_address.py` | Address parsing, trusted proxy parsing, right-to-left resolution, `X-Forwarded-Proto`, the middleware |
| `tests/unit/test_edge_rate_limit_store.py` | Memory store window, expiry and cap; Redis store with a fake client; fallback, cooldown and recovery; settings and startup messages |
| `tests/unit/test_edge_cors_policy.py` | Origin validation and normalization, wildcard rules |
| `tests/integration/test_edge_rate_limit_redis.py` | Real Redis: exact limit under concurrency, record expiry, two application instances. Needs `TEST_REDIS_URL`; CI provides Redis. |
| `tests/integration/test_edge_uvicorn_server.py` | Real uvicorn server: `Expect: 100-continue` with an oversized upload gets `413` without the body |

Run them with `pytest tests/security tests/unit/test_edge_*.py tests/integration/test_edge_*.py`. For the Redis tests, start Redis and set `TEST_REDIS_URL=redis://localhost:6379/15`.

## Implementation notes

- The new settings are environment variables read in `ragbot/api/edge/config.py` when the application is created, like the Phase 2 authentication mode settings, so `ragbot/configs/settings.py` does not change.
- The rate limiter keeps the sliding-window log of the earlier middleware, in memory and in Redis, so a limit means the same thing in both stores.
- The existing metric `ragbot_rate_limit_hits_total` is still recorded for each refusal.
