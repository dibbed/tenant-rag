# Security & Tenant Boundary Architecture

This document defines the security model, tenant boundaries, credential storage, authentication modes, outbound request protection, known limits, and responsible disclosure procedures for **TenantRAG**.

> **Phase 2 security hardening** (findings C1 to C6 in `docs/BASELINE_AUDIT.md`) changed the API key format, the authorization levels, the default authentication mode, the handling of tenant storage failures, and URL ingestion. Read section 2.4, "API key migration", before you upgrade.

> **Phase 3 edge protection** (findings C9 to C11) changed how callers are identified for rate limiting, which browser origins may call the API, and how request sizes are checked. Read section 6, "Edge Protection", and the migration notes in `docs/features/edge-protection/README.md` before you upgrade.

---

## 1. Security Architecture Principles

| Concept | Implementation |
|---|---|
| Authentication | API keys `rgb_<key_id>_<secret>` verified against a salted scrypt hash. No anonymous access outside explicit development mode. |
| Authorization | Levels come from the user role: `system_admin`, `tenant_admin`, user. Requests cannot access or change tenants they do not own. |
| Storage isolation | One vector store partition per tenant (directory or collection). A partition that cannot be opened fails closed; there is no fallback to a shared store. |
| Outbound requests | URL ingestion blocks internal, private, link-local and cloud metadata targets, on every redirect hop and at DNS resolution time. |
| Rate limiting | Counted per Principal after authentication, otherwise per Client Address. Forwarded headers count only from configured trusted proxies. Optional shared Redis store with an explicit per-instance fallback. |
| Browser access (CORS) | No origin allowed by default. Explicit allowlist; `*` only in development and without credentials. |
| Request size | Bodies above `SECURITY_MAX_FILE_SIZE_MB` are refused before or while they are read; uploads are copied to disk in chunks. |
| Encryption at rest | Host-level responsibility. Vector stores are not encrypted per tenant on disk. |

---

## 2. Authentication Model

### 2.1 Authentication modes

| `MULTI_TENANT_ENABLED` | `ENVIRONMENT` | `ALLOW_ANONYMOUS` | Result |
|---|---|---|---|
| `true` | any | any (ignored) | Every API request needs a valid API key or session token. |
| `false` | `development` | `true` | Anonymous access. Insecure, for local development only. A warning is logged at startup. |
| `false` | any other value, or unset | any | Every API request except `/health` and `/api/v1/health` is rejected with `HTTP 401`. A warning is logged at startup. |

- `ENVIRONMENT` defaults to `production` when it is not set.
- The values are read from the process environment. The settings module loads `.env` into the environment at startup.
- Before Phase 2, the API accepted every request without credentials when `MULTI_TENANT_ENABLED=false`, which was the default.

### 2.2 API key format and storage

- Format: `rgb_<key_id>_<secret>`
  - `key_id`: 32 lowercase hex characters. It is stored in `tenant_api_keys.key_id` and used for direct lookup.
  - `secret`: `secrets.token_urlsafe(32)` (256 bits).
- When a key is created:
  1. The raw key is generated and returned **once**. It is never stored, logged, or kept in memory.
  2. The full raw key is hashed with scrypt (`n=2^14`, `r=8`, `p=1`, 16-byte random salt, 32-byte output).
  3. `tenant_api_keys.key_hash` stores `scrypt$<n>$<r>$<p>$<salt>$<hash>`. `key_prefix` stores the first 12 characters for identification.
- `TenantAuth.list_api_keys()` (used by `tenantrag tenant list-api-keys`) returns the key id, prefix, metadata and `hash_scheme` (`scrypt` or `legacy-sha256`). It never returns the secret or the hash.

### 2.3 Credential verification

- Clients send the key in `X-API-Key: <key>` or `Authorization: Bearer <key>`.
- The server parses the key id, loads that one record, and verifies the full key against the stored scrypt hash with a constant-time comparison (`hmac.compare_digest`).
- The stored hash is never accepted as a credential, and there is no lookup by the raw presented value.
- Revocation and expiry are read from SQLite on every request. A key revoked from the CLI (a different process) stops working immediately.
- To avoid running scrypt on every request, each process remembers a successful verification for up to 5 minutes (the key id and a SHA-256 digest of the presented key, in memory only). The revocation and expiry checks still run on every request.
- Users without a password hash (for example, users created automatically for an API key) cannot log in with a password.

### 2.4 API key migration (legacy SHA-256 keys)

Keys created before Phase 2 have the format `rgb_<token>` and are stored as unsalted SHA-256 digests. **They are rejected.** A request with a legacy key gets `HTTP 401` with this detail:

`Legacy API key format is no longer accepted. Issue a new API key and revoke the old one (see SECURITY.md, 'API key migration').`

There is no automatic migration, because the server never had the raw keys. No database schema change is needed: new keys use the existing `tenant_api_keys` columns.

For each tenant:

1. Find the legacy keys. Query the database:
   `SELECT key_id, tenant_id, name FROM tenant_api_keys WHERE is_active = 1 AND key_hash NOT LIKE 'scrypt$%';`
   or look for `hash_scheme: legacy-sha256` in the key listing.
2. Issue a replacement key: `tenantrag tenant create-api-key --tenant-id <tenant_id> --name <name>`. Store the printed key in your secret manager. It is shown only once.
3. Deploy the new key to every client of that tenant.
4. Revoke the old key: `tenantrag tenant revoke-api-key --tenant-id <tenant_id> --key-id <legacy_key_id>`. Legacy keys can still be revoked by key id or by raw key.

---

## 3. Authorization & Tenant Boundary Enforcement

### 3.1 Authorization levels

The level comes from the user's role only. Permissions attached to an API key never raise it.

| Level | Role | Scope |
|---|---|---|
| `system_admin` | `super_admin` | All tenants. |
| `tenant_admin` | `admin` | Its own tenant: access, manage and reset. |
| user | `manager`, `user`, `viewer`, and keys without a stored user | Its own tenant, limited to the granted permissions. |

- Before Phase 2, any API key with the `manage_tenant` permission was treated as a cross-tenant super admin.
- A key created without `--user-id` is never bound to a `super_admin` user. Binding a key to a system admin needs that user's explicit id.

### 3.2 Decoupled routing and identity

- Routing: `X-Tenant-ID: <tenant_id>`. Identity: the API key.
- `get_authorized_tenant_context` (in `ragbot/api/dependencies.py`) rejects a request with `HTTP 403 Forbidden` when `X-Tenant-ID` names another tenant, unless the principal is `system_admin`.
- If `X-Tenant-ID` is omitted, the principal's own tenant is used.
- Unknown, suspended or inactive tenants are rejected with `HTTP 403 Forbidden`.

### 3.3 Store reset and tenant management

- `POST /api/v1/documents/reset` needs one of: `system_admin`; `tenant_admin` of the target tenant; or the explicit `delete_documents` permission on the target tenant. The `manager` role and the `manage_tenant` permission do not grant reset.
- Tenant management routes must use the `require_tenant_admin` dependency: `tenant_admin` for its own tenant, `system_admin` for any tenant, `HTTP 403` for everyone else.
- Tenant, user and key management is currently available only in the `tenantrag` CLI, which runs with local operator access.

---

## 4. Tenant Storage & Cache Partitioning

### 4.1 Vector store partitioning

- FAISS: one directory per tenant, `<STORE_PATH>/tenants/<tenant_id>/` (default `STORE_PATH` is `./data/vector_store`).
- Chroma and Qdrant: one collection per tenant, `tenant_<tenant_id>`.
- Tenant ids must match `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. Other values are rejected before any path or collection name is built.
- This is directory and collection isolation. It is not cryptographic isolation.

### 4.2 Fail-closed tenant storage

- If a tenant store cannot be created or loaded (missing dependency, import error, corrupted index, unreachable Qdrant), the operation fails with `TenantStorageError`:
  - `/api/v1/query` returns `HTTP 503` (`Tenant storage is unavailable`) without internal details.
  - Ingestion returns an error and writes nothing.
  - A tenant reset returns an error and deletes nothing.
- There is no fallback to the shared default store or to another tenant's store. Tenant stores are created with `VectorStoreFactory.create_store(..., allow_fallback=False)`. The legacy FAISS fallback remains only for the non-tenant default store.
- Before Phase 2, a tenant storage failure silently used the shared default store and the shared retriever. Queries could return other data, ingestion could write into the shared index, and a tenant reset could wipe the shared index.

### 4.3 Semantic cache partitioning

- The semantic cache stores `tenant_id` with every query-answer pair and prefixes cache keys with it.
- Lookups compare query embeddings only with entries of the requesting tenant.

---

## 5. Outbound Request Protection (SSRF)

`ragbot/rag/loaders/url_guard.py` protects every fetch of a client-supplied URL (`POST /api/v1/documents/url`, `URLLoader`, `HTMLLoader`):

1. Only `http` and `https` URLs with a host are accepted.
2. Blocked targets: `localhost` and internal host names (`*.localhost`, `*.local`, `*.internal`, `*.localdomain`, cloud metadata names); loopback; RFC 1918 private ranges; link-local (`169.254.0.0/16`, `fe80::/10`); carrier-grade NAT (`100.64.0.0/10`); unique-local IPv6 (`fc00::/7`); multicast, reserved and unspecified addresses; IPv4-mapped, NAT64, 6to4 and Teredo forms of these; short numeric forms such as `127.1`; and cloud metadata addresses (`169.254.169.254`, `169.254.170.2`, `100.100.100.200`, `168.63.129.16`, `fd00:ec2::254`).
3. Redirects are followed manually (at most 5). Every `Location` target is validated before it is requested.
4. A custom resolver checks DNS results at connect time. This blocks host names that resolve to internal addresses, and DNS rebinding.
5. The API returns `HTTP 400` (`URL target is not allowed`) for a blocked target and makes no request.

Other outbound requests were audited and are not client-controlled: provider health checks (`ragbot/outputs/health.py`) and the plugin marketplace (`ragbot/plugins/plugin_marketplace.py`) use operator-configured URLs.

---

## 6. Edge Protection (Rate Limiting, CORS, Request Size)

Phase 3 hardening for audit findings C9, C10 and C11. Configuration, migration notes and deployment requirements: `docs/features/edge-protection/README.md`.

### 6.1 Client address and trusted proxies

- The Client Address is the TCP peer of the connection. `X-Forwarded-For`, `X-Real-IP`, `Forwarded`, `CF-Connecting-IP`, `True-Client-IP` and similar headers are ignored.
- `SECURITY_TRUSTED_PROXIES` lists reverse proxies (IP addresses or CIDR networks). It is empty by default. Only when the TCP peer is listed does the service read `X-Forwarded-For`, from right to left, and use the first address that is not a listed proxy. Entries that are not IP addresses are never used.
- An invalid entry or a catch-all entry (`*`, `0.0.0.0/0`, `::/0`) stops startup. Networks wider than /16 (IPv4) or /48 (IPv6) log a warning.
- `python main.py` and the Docker image start uvicorn with `proxy_headers=False`, so uvicorn does not rewrite the client address. Start uvicorn directly only with `--no-proxy-headers`, and never with `--forwarded-allow-ips='*'`.

### 6.2 Rate limiting

- A request without credentials counts against its Client Address before its body is read. A request with a credential counts after authentication: against its Principal (`principal:<tenant_id>:<principal_id>`) when the credential is valid, and against its Client Address when it is not. Each request counts once.
- IPv6 Client Addresses share one counter per /64 network.
- Over the limit, the service answers `HTTP 429` with `Retry-After`, `retry_after` in the body and the `X-RateLimit-*` headers. Health checks and documentation are never counted.
- Limits: `SECURITY_RATE_LIMIT_REQUESTS` (default 10) requests per `SECURITY_RATE_LIMIT_WINDOW` (default 60) seconds.
- Without `SECURITY_RATE_LIMIT_STORAGE_URL`, each instance and each worker process counts on its own, and the startup log says so. With a `redis://` or `rediss://` URL, all instances share one count. If Redis fails or is slow, requests are counted per instance (never allowed without counting), one warning is logged per outage, and Redis is tried again after 30 seconds.
- Records are deleted when their window has passed. Redis keys hold a SHA-256 digest of the subject, not the address or the principal id.

### 6.3 Browser access (CORS)

- `SECURITY_CORS_ALLOWED_ORIGINS` is empty by default: no origin may call the API from a browser.
- Each entry must be an origin, for example `https://app.example.com` or `http://localhost:3000`. Entries with a path, user information or wildcard, and `null`, stop startup.
- `*` allows every origin without credentials and is accepted only with `ENVIRONMENT=development`. With any other `ENVIRONMENT` value, or none, it stops startup, so production must list its origins.
- Listed origins may send credentials. Allowed methods: `GET`, `POST`. Allowed request headers: `Authorization`, `Content-Type`, `X-API-Key`, `X-Tenant-ID`. Browser code can read `Retry-After` and `X-RateLimit-*`.
- CORS limits what a browser may read. It does not replace authentication.

### 6.4 Request size

- Every request body is limited to `SECURITY_MAX_FILE_SIZE_MB` (default 50) plus 64 KiB for multipart framing.
- A declared `Content-Length` above the limit is refused with `HTTP 413` before the body is read. A body that passes the limit while it is received is cut off and refused with `HTTP 413`. An invalid `Content-Length` gets `HTTP 400`.
- The upload route copies the file to disk in 1 MiB chunks and applies the exact file limit. The text route counts UTF-8 bytes.
- Every 413 states the limit. A refused upload keeps nothing: ingestion does not run and temporary files are removed.

---

## 7. Known Security & Architectural Limitations

1. **Single-node focus:** SQLite and FAISS are designed for single-node deployments. For scale-out, use a centralized vector store (Qdrant) and external database configuration.
2. **In-process state:** user sessions and the key verification cache are per process. Sessions do not survive restarts and are not shared between workers.
3. **Rate limiting:** without `SECURITY_RATE_LIMIT_STORAGE_URL`, each instance and worker process counts on its own, and during a shared store outage the effective limit is multiplied by the number of instances. A request with a credential is counted only after its body has been received (bounded by the request size limit). A failed credential check runs scrypt before it is counted.
4. **Request parsing:** the pinned Starlette version (0.37.2, through FastAPI 0.111.0) keeps multipart form fields without a file name in memory and joins their parts with repeated copies (CVE-2024-47874, fixed in Starlette 0.40.0). The request size limit caps one such field at the upload limit, but not its memory or CPU cost: in the Phase 3 verification review, a 40 MiB field took 2.2 seconds and raised peak memory by 79 MiB, while the same data sent as a file part used no extra memory. Parallel requests multiply this cost. Content that expands during parsing (ZIP-based DOCX, XLSX and PPTX files) is not bounded by the upload limit.
5. **In-process plugins:** plugins run in-process. Exceptions are contained, but a faulty plugin can block the event loop or use too much CPU or memory. Do not install untrusted plugins.
6. **Encryption at rest:** documents and embeddings are stored on disk in plaintext or pickle format. Production deployments must use full-disk or volume encryption (for example LUKS, BitLocker, or cloud volume encryption).
7. **Open findings:** the risks found in the Phase 3 verification review, with their severity and the recommended actions, are listed in `docs/security/PHASE3_EDGE_SECURITY_REVIEW.md`.

---

## 8. Security Reporting & Vulnerability Disclosure

If you discover a potential security vulnerability in TenantRAG:

1. **Do NOT report security vulnerabilities via public GitHub issues.**
2. Please report security vulnerabilities through GitHub's private vulnerability reporting feature if enabled, or contact the repository maintainer privately.
3. Include:
   - A description of the vulnerability and attack vector.
   - Minimal reproduction steps or cURL commands.
   - The affected versions or environment details.
