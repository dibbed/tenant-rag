# TenantRAG REST API Specification

## 1. Overview

TenantRAG exposes a high-performance RESTful HTTP API built on **FastAPI**. It allows web applications, microservices, and external clients to ingest diverse document types, trigger RAG question-answering workflows, check system health, and manage knowledge base state.

- **Default Base URL**: `http://localhost:8000`
- **Interactive Documentation**:
  - Swagger UI: `http://localhost:8000/docs`
  - ReDoc: `http://localhost:8000/redoc`
  - OpenAPI Schema: `http://localhost:8000/openapi.json`

---

## 2. Global Request Handling & Middleware

### Rate Limiting
All requests except health check and documentation endpoints are rate limited with a sliding window. Authenticated requests count against the principal (API key or session); other requests, failed authentication attempts included, count against the client address. The client address is the TCP peer, unless the request comes through a proxy listed in `SECURITY_TRUSTED_PROXIES`.
- **Default Limit**: 10 requests per 60 seconds for each principal or client address (configurable via `SECURITY_RATE_LIMIT_REQUESTS` and `SECURITY_RATE_LIMIT_WINDOW`).
- **Response Headers**:
  - `X-RateLimit-Limit`: Maximum requests permitted per window.
  - `X-RateLimit-Remaining`: Requests remaining in current window.
  - `X-RateLimit-Reset`: UTC epoch timestamp when current window resets.
- **Rate Limit Exceeded**: Returns `HTTP 429 Too Many Requests` with a `Retry-After: <seconds>` header.

### CORS
No browser origin is allowed by default. List the allowed origins in `SECURITY_CORS_ALLOWED_ORIGINS`, for example `https://app.example.com`. `*` allows every origin without credentials and is accepted only with `ENVIRONMENT=development`. Browser code can read `Retry-After` and the `X-RateLimit-*` headers.

### Request Size
Request bodies above `SECURITY_MAX_FILE_SIZE_MB` (default 50 MB) are refused with `HTTP 413 Request Entity Too Large` before or while they are read. The response states the limit, for example `{"detail": "Request body exceeds maximum allowed size of 50MB", "max_size_mb": 50, "max_size_bytes": 52428800}`.

### Tenant Authentication & Authorization Model

When multi-tenancy is enabled (`MULTI_TENANT_ENABLED=true`), API endpoints enforce strict zero-trust identity and boundary authorization:

1. **Authentication vs Routing**:
   - **Identity Authentication**: Clients must supply credentials via `X-API-Key: rgb_<token>` or `Authorization: Bearer <token>`.
   - **Routing Context**: Clients specify the target tenant context via `X-Tenant-ID: <tenant_id>`. If omitted, the tenant associated with the authenticated principal is used automatically.
2. **Boundary Enforcement & Status Codes**:
   - **401 Unauthorized**: Missing credentials, invalid API key, expired key, or revoked key.
   - **403 Forbidden**: Cross-tenant access attempt (e.g. Tenant A trying to access Tenant B), inactive or suspended tenant, or insufficient permissions for the action.
   - **Reset Authorization**: `/api/v1/documents/reset` strictly requires `admin` or `super_admin` role. Non-admin principals receive `403 Forbidden`.
3. **Cryptographic Key Storage**:
   - Raw keys follow the format `rgb_<secrets.token_urlsafe(32)>` and are only displayed once upon generation.
   - Keys are cryptographically hashed using SHA-256 (`key_hash`) before persistence in SQLite (`data/tenants/tenants.db`).
   - Listing keys (`tenantrag tenant list-api-keys`) masks secrets, displaying only a 12-character prefix (`rgb_...`) and metadata.
4. **Single-Tenant Compatibility**:
   - When multi-tenancy is disabled (`MULTI_TENANT_ENABLED=false`, the default), requests proceed without any authentication headers or tenant context, maintaining 100% backward compatibility.

---

## 3. Endpoints

### 3.1 Health & Subsystem Status

#### `GET /health` or `GET /api/v1/health`
Evaluates the real-time operational status of all attached subsystems without leaking internal API keys or credentials.

- **Status Codes**:
  - `200 OK`: System healthy or operating in degraded mode.
  - `503 Service Unavailable`: Critical subsystem failure (e.g. vector store uninitialized).

**Response Schema (`HealthResponse`):**
```json
{
  "status": "healthy",
  "timestamp": 1726815892.41,
  "components": {
    "vector_store": {"status": "healthy", "store_type": "faiss", "documents_count": 42},
    "embedder": {"status": "healthy", "provider": "sentence_transformers"},
    "cache": {"status": "healthy", "type": "multi_tier"},
    "qa_chain": {"status": "healthy", "provider": "openrouter"}
  },
  "issues": []
}
```

---

### 3.2 Question Answering / RAG Query

#### `POST /api/v1/query`
Executes semantic vector retrieval against the knowledge base and synthesizes a grounded answer using the configured Large Language Model.

**Request Schema (`QueryRequest`):**
```json
{
  "question": "What are the chunking strategies supported by TenantRAG?",
  "language": "en",
  "top_k": 4,
  "similarity_threshold": 0.6
}
```

| Parameter | Type | Required | Default | Description |
|:---|:---|:---|:---|:---|
| `question` | `string` | **Yes** | — | Question prompt (min 1 character). |
| `language` | `string` | No | `"fa"` | Target language code (`"en"` or `"fa"`). |
| `top_k` | `integer` | No | `5` | Number of relevant chunks to retrieve (1 to 50). |
| `similarity_threshold` | `float` | No | `0.6` | Minimum cosine similarity threshold (0.0 to 1.0). |

**Response Schema (`QueryResponse`):**
```json
{
  "answer": "TenantRAG supports token, semantic, hierarchical, and adaptive chunking strategies...",
  "sources": [
    "chunking_guide.pdf (Page 4)",
    "loaders_spec.md"
  ],
  "confidence_score": 0.88,
  "processing_time": 1.12,
  "language": "en",
  "retrieved_chunks": 4,
  "metadata": {}
}
```

**Error Codes:**
- `422 Unprocessable Entity`: Question empty or threshold out of range.
- `503 Service Unavailable`: Upstream LLM provider or embedding provider unavailable.
- `500 Internal Server Error`: Vector search failure or internal exception.

---

### 3.3 Document Ingestion

#### `POST /api/v1/documents/upload`
Uploads and processes a local document file using `multipart/form-data`.
- **Allowed Formats**: `pdf`, `docx`, `txt`, `html`, `md`, `pptx`, `xlsx`, `png`, `jpg`, `jpeg`, `tiff`, `bmp`.
- **Max File Size**: 50 MB (configurable via `SECURITY_MAX_FILE_SIZE_MB`).

**Example `curl` Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@/path/to/report.pdf"
```

**Response Schema (`IngestResponse`):**
```json
{
  "success": true,
  "document_id": "doc_e3b0c44298fc1c14",
  "title": "report.pdf",
  "source": "report.pdf",
  "chunks_created": 18,
  "processing_time": 2.45,
  "metadata": {
    "file_size": 2048576,
    "pages": 12,
    "source_type": "pdf"
  }
}
```

**Error Codes:**
- `400 Bad Request`: Empty (0-byte) file uploaded.
- `413 Request Entity Too Large`: File exceeds size limit.
- `415 Unsupported Media Type`: File extension not allowed.

---

#### `POST /api/v1/documents/text`
Directly ingests a raw string payload into the knowledge base without filesystem uploads.

**Request Schema (`TextIngestRequest`):**
```json
{
  "text": "Antigravity is an advanced agentic coding system designed by Google DeepMind.",
  "title": "antigravity_overview",
  "metadata": {
    "category": "ai",
    "version": "2.0"
  }
}
```

**Response Schema (`IngestResponse`):**
```json
{
  "success": true,
  "document_id": "doc_a1b2c3d4e5f60718",
  "title": "antigravity_overview",
  "source": "text_input",
  "chunks_created": 1,
  "processing_time": 0.32,
  "metadata": {
    "category": "ai",
    "version": "2.0"
  }
}
```

**Error Codes:**
- `400 Bad Request`: Text content empty or whitespace only.
- `413 Request Entity Too Large`: Text exceeds max payload character threshold.

---

#### `POST /api/v1/documents/url`
Fetches a remote web page, cleans and extracts structural content, splits it into chunks, and stores embeddings.

**Request Schema (`URLIngestRequest`):**
```json
{
  "url": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
  "title": "RAG Wikipedia",
  "metadata": {
    "domain": "wikipedia.org"
  }
}
```

**Response Schema (`IngestResponse`):**
```json
{
  "success": true,
  "document_id": "doc_c8d7e6f5a4b3c2d1",
  "title": "RAG Wikipedia",
  "source": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
  "chunks_created": 24,
  "processing_time": 3.81,
  "metadata": {
    "domain": "wikipedia.org",
    "status_code": 200
  }
}
```

**Error Codes:**
- `400 Bad Request`: Invalid URL scheme (only `http` and `https` permitted).
- `500 Internal Server Error`: HTTP network fetch failure or parsing exception.

---

#### `POST /api/v1/documents/reset`
Wipes all documents from the active vector store index and purges all associated semantic and L1/L2 caches.

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/v1/documents/reset"
```

**Response Schema (`ResetResponse`):**
```json
{
  "success": true,
  "message": "Vector store and associated caches reset successfully",
  "timestamp": 1726816000.12
}
```

---

## 4. Standard Error Response Format

When an API error occurs, FastAPI returns standard JSON adhering to RFC 7807 problem details:

```json
{
  "detail": "Descriptive error message"
}
```

### Common HTTP Status Codes
| Code | Reason | Cause |
|:---|:---|:---|
| `400` | Bad Request | Empty file, empty text, or malformed URL scheme. |
| `413` | Request Entity Too Large | Uploaded file or text content exceeds size limits. |
| `415` | Unsupported Media Type | File extension is not in `allowed_file_types`. |
| `422` | Unprocessable Entity | Pydantic schema validation failure. |
| `429` | Too Many Requests | Rate limit threshold exceeded. Check `Retry-After`. |
| `500` | Internal Server Error | Unhandled server error or vector store search failure. |
| `503` | Service Unavailable | External LLM/embedding provider API unreachable or timing out. |
