# Security & Tenant Boundary Architecture

This document defines the security model, tenant boundaries, credential storage mechanisms, known operational limits, and responsible disclosure procedures for **TenantRAG**.

---

## 1. Security Architecture Principles

TenantRAG is an API-first RAG microservice designed to serve multi-tenant client applications. Its security architecture maintains strict separation between four core primitives:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SECURITY DOMAIN BOUNDARIES                      │
├──────────────────────┬─────────────────────────────────────────────────┤
│ Concept              │ Implementation Reality                          │
├──────────────────────┼─────────────────────────────────────────────────┤
│ Authentication       │ Verifying client identity via cryptographic     │
│                      │ SHA-256 API key token verification.             │
├──────────────────────┼─────────────────────────────────────────────────┤
│ Authorization        │ Enforcing tenant matching: requests cannot      │
│                      │ access or mutate tenants they do not own.       │
├──────────────────────┼─────────────────────────────────────────────────┤
│ Storage Isolation    │ Filesystem path partitioning: each tenant has   │
│                      │ its own dedicated vector index directory.       │
├──────────────────────┼─────────────────────────────────────────────────┤
│ Encryption at Rest   │ Host-level OS responsibility. Vector stores are │
│                      │ not encrypted per-tenant on disk.               │
└──────────────────────┴─────────────────────────────────────────────────┘
```

---

## 2. Authentication Model

### API Key Structure & Hashing
- Client API keys follow the format: `rgb_<32_random_bytes_base64url>` (e.g. `rgb_aBcDeF...`).
- When a key is created:
  1. The raw plaintext key is generated via `secrets.token_urlsafe(32)`.
  2. The SHA-256 hash of the key is computed (`hashlib.sha256(raw_key.encode("utf-8")).hexdigest()`).
  3. A 12-character prefix is recorded for identification and auditing (`rgb_xxxxxxxx`).
  4. The **SHA-256 hash** and **prefix** are persisted in the SQLite tenant database (`data/tenants/tenants.db`).
  5. The raw plaintext key is returned **once** to the client upon creation and is **never persisted to disk**.

### Credential Resolution & Validation
- Requests authenticate using the `X-API-Key` header or standard `Authorization: Bearer <key>` header.
- Upon receiving a request, the server hashes the provided token with SHA-256 and queries the database for an active key matching that hash.
- Key comparison uses constant-time string equality (`secrets.compare_digest`) to protect against timing side-channel attacks.

---

## 3. Authorization & Tenant Boundary Enforcement

### Decoupled Routing vs Identity
- Routing specifies the target tenant context: `X-Tenant-ID: <tenant_id>`.
- Identity specifies the caller: `X-API-Key: rgb_<token>`.
- The FastAPI dependency `get_current_tenant_dependency` enforces cross-tenant boundary verification:
  - If a client supplies an API key belonging to `tenant_alpha`, but specifies `X-Tenant-ID: tenant_beta`, the request is rejected with `HTTP 403 Forbidden`.
  - Clients cannot access, query, or ingest into another tenant's vector space simply by manipulating the `X-Tenant-ID` header.
- Inactive or suspended tenants (`is_active=False`) are rejected with `HTTP 403 Forbidden`.

### Role-Based Access Control (RBAC) on Store Resets
- Destructive operations (such as `POST /api/v1/store/reset`) require both matching tenant ownership and appropriate administrative permissions. An unauthenticated or mismatched caller cannot wipe a tenant's index.

---

## 4. Tenant Storage & Cache Partitioning

### Vector Store Partitioning
- TenantRAG uses **filesystem directory isolation** for vector stores.
- When documents are ingested for tenant `tenant_123`, the index files are stored in:
  `data/vector_stores/tenant_123/`
- FAISS index files (`faiss.index`, `documents.pkl`, `metadata.json`) are completely separated by directory. Tenant queries never search outside their designated directory.
- **Important note on terminology:** This is directory-level isolation and query partitioning. It is **not** cryptographic isolation (i.e., data files on disk are not encrypted with unique per-tenant cryptographic keys).

### Semantic Cache Partitioning
- The semantic cache tracks `tenant_id` for every stored query-answer pair.
- Lookups compare query embeddings only against entries where `entry.tenant_id == request.tenant_id`.
- Tenant A queries never hit or return answers cached by Tenant B.

---

## 5. Known Security & Architectural Limitations

1. **Single-Node Focus:**
   - TenantRAG's default SQLite and FAISS storage is designed for single-node deployments. If deployed across multiple load-balanced container replicas sharing a single NFS/EFS volume, file locking collisions may occur. For distributed scale-out, use centralized vector stores (Qdrant) and external database configurations.
2. **In-Process Plugins:**
   - Plugins execute in-process via lifecycle hooks. While exceptions are caught and contained at Python boundary levels, malicious or poorly written plugins could block the event loop or consume excessive CPU/memory. Do not install untrusted third-party plugins.
3. **Encryption at Rest:**
   - Documents and embeddings are stored on disk in plaintext or serialized pickle format. Production deployments must enable full-disk encryption (e.g., LUKS, BitLocker, or cloud volume encryption) at the infrastructure level.

---

## 6. Security Reporting & Vulnerability Disclosure

If you discover a potential security vulnerability in TenantRAG:

1. **Do NOT report security vulnerabilities via public GitHub issues.**
2. Please report security vulnerabilities through GitHub's private vulnerability reporting feature if enabled, or contact the repository maintainer privately.
3. Include:
   - A description of the vulnerability and attack vector.
   - Minimal reproduction steps or cURL commands.
   - The affected versions or environment details.
