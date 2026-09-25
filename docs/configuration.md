# ⚙️ Configuration Reference Guide

RAGBot utilizes **Pydantic Settings** to validate and manage configuration values from environment variables and `.env` files.

---

## 1. HTTP Server & Network

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `HOST` | `string` | `"0.0.0.0"` | Network interface to bind the API server to. |
| `PORT` | `integer` | `8000` | Port number to bind the API server to. |
| `WORKERS` | `integer` | `1` | Number of Uvicorn worker processes to spawn. |
| `RELOAD` | `boolean` | `false` | Enable live code reload (for development only). |

---

## 2. LLM Provider Settings

Configures the Large Language Model provider used by `QAChain` to formulate answers.

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `LLM_PROVIDER` | `string` | `"openai"` | Active provider: `openai`, `anthropic`, `openrouter`, `ollama`, `hf_local`. |
| `LLM_MODEL` | `string` | `"gpt-3.5-turbo"` | Model identifier (e.g. `gpt-4o-mini`, `claude-3-haiku-20240307`, `x-ai/grok-4-fast:free`, `llama3`). |
| `OPENAI_API_KEY` | `string` | `None` | Secret key for OpenAI API. |
| `ANTHROPIC_API_KEY` | `string` | `None` | Secret key for Anthropic Claude API. |
| `OPENROUTER_API_KEY` | `string` | `None` | Secret key for OpenRouter API. |
| `LLM_BASE_URL` | `string` | `None` | Custom API base URL (for OpenRouter, vLLM, or Ollama proxy). |
| `LLM_TEMPERATURE` | `float` | `0.7` | Sampling temperature between `0.0` and `2.0`. |
| `LLM_MAX_TOKENS` | `integer` | `1000` | Maximum number of tokens in generated answer. |
| `LLM_TIMEOUT` | `float` | `30.0` | HTTP request timeout in seconds for upstream LLM calls. |
| `LLM_HF_MODEL` | `string` | `None` | HuggingFace model checkpoint path (when using `hf_local`). |
| `LLM_HF_DEVICE` | `string` | `"auto"` | Hardware device for local models (`"cpu"`, `"cuda"`, `"auto"`). |

---

## 3. Embedding Model Settings

Controls the embedding model used for vectorizing documents and incoming user questions.

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `EMBED_PROVIDER` | `string` | `"sentence_transformers"` | Provider: `sentence_transformers`, `openai`, `huggingface`. |
| `EMBED_MODEL` | `string` | `"intfloat/e5-small-v2"` | Model identifier (e.g. `intfloat/e5-small-v2`, `text-embedding-3-small`). |
| `EMBED_BATCH_SIZE` | `integer` | `32` | Number of chunks encoded in each embedding batch. |
| `EMBED_TIMEOUT` | `float` | `30.0` | Timeout in seconds for embedding generation. |

---

## 4. Vector Store Settings

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `VECTOR_STORE_DEFAULT_STORE` | `string` | `"faiss"` | Default vector store backend: `faiss`, `chroma`, `qdrant`. |
| `VECTOR_STORE_AVAILABLE_STORES` | `list` | `["faiss", "chroma", "qdrant"]` | Enabled vector store types. |
| `VECTOR_STORE_PERSIST_PATH` | `string` | `"./data/vector_stores"` | Local filesystem directory for storing index files. |

---

## 5. Caching & Semantic Cache Settings

TenantRAG implements a multi-tier cache to avoid redundant embedding generation and LLM calls.

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `ENABLE_CACHE` | `boolean` | `true` | Globally enable or disable the caching subsystem. |
| `CACHE_TYPE` | `string` | `"memory"` | Primary cache driver: `"memory"` or `"redis"`. |
| `ENABLE_REDIS` | `boolean` | `false` | Enable Redis as L2 distributed cache backend. |
| `REDIS_URL` | `string` | `"redis://localhost:6379/0"` | Connection URI for Redis. |
| `CACHE_TTL` | `integer` | `3600` | Expiration time for cached responses (in seconds). |
| `CACHE_SIMILARITY_THRESHOLD`| `float` | `0.85` | Cosine similarity threshold for returning semantic cache hits. |

---

## 6. Security & Rate Limiting

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `SECURITY_RATE_LIMIT_REQUESTS` | `integer` | `60` | Maximum requests permitted within the sliding window per IP. |
| `SECURITY_RATE_LIMIT_WINDOW` | `integer` | `60` | Duration of the sliding window (in seconds). |
| `SECURITY_MAX_FILE_SIZE_MB` | `integer` | `50` | Maximum permitted file upload and text ingest size (in MB). |
| `SECURITY_ALLOWED_FILE_TYPES` | `list` | `["pdf","docx","txt","html","md","pptx","xlsx","png","jpg","jpeg","tiff","bmp"]` | Allowed document file extensions. |

---

## 7. RAG Chunking & Retrieval Knobs

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `RAG_CHUNK_SIZE` | `integer` | `400` | Target chunk size (in tokens). |
| `RAG_CHUNK_OVERLAP` | `integer` | `50` | Overlap size between adjacent chunks (in tokens). |
| `RAG_TOP_K` | `integer` | `5` | Default number of chunks retrieved per query. |
| `RAG_SIMILARITY_THRESHOLD` | `float` | `0.6` | Minimum similarity score required for retrieved context chunks. |
| `RAG_MAX_CONTEXT_TOKENS` | `integer` | `4000` | Maximum token budget for context passed to LLM prompt. |
| `DEFAULT_LANG` | `string` | `"fa"` | Fallback language code (`"fa"` or `"en"`). |
| `LOG_LEVEL` | `string` | `"INFO"` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

---

## 8. HTML Loader Settings

Fine-tunes the asynchronous HTML and web document ingestion engine.

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `MULTI_FORMAT_HTML_EXTRACT_LINKS` | `boolean` | `true` | Extract hyperlinks found in web pages. |
| `MULTI_FORMAT_HTML_EXTRACT_IMAGES`| `boolean` | `true` | Extract image references found in web pages. |
| `MULTI_FORMAT_HTML_CLEAN_CONTENT` | `boolean` | `true` | Strip script, style, and navigation tags. |
| `MULTI_FORMAT_HTML_TIMEOUT` | `float` | `20.0` | Web page HTTP fetch timeout in seconds. |
| `MULTI_FORMAT_HTML_RETRIES` | `integer` | `2` | Number of retry attempts on network fetch failures. |
| `MULTI_FORMAT_HTML_USER_AGENT` | `string` | `"ragbot-html-loader/1.0"` | HTTP User-Agent string sent during web fetches. |

---

## 9. Multi-Tenant Subsystem Settings

Configures tenant isolation, SQLite storage, API key authentication, and quota management.

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `MULTI_TENANT_ENABLED` | `boolean` | `false` | Enable multi-tenant data, cache partitioning, and API key authentication. |
| `MULTI_TENANT_DEFAULT_TIER` | `string` | `"free"` | Default subscription tier (`free`, `basic`, `premium`, `enterprise`). |
| `MULTI_TENANT_DATA_DIR` | `string` | `"./data/tenants"` | Storage location for `tenants.db` and SQLite metadata. |
| `MULTI_TENANT_AUTO_PROVISION` | `boolean` | `false` | Automatically provision tenants on first detected request. |

### CLI Key Management Commands
When `MULTI_TENANT_ENABLED=true`, manage API keys via the CLI (both `tenantrag` and `ragbot-cli` work):
- `tenantrag tenant create-api-key --tenant-id <id> --name <label>`: Generate a new raw `rgb_...` API key.
- `tenantrag tenant list-api-keys --tenant-id <id>`: List active keys with masked prefixes.
- `tenantrag tenant revoke-api-key --tenant-id <id> --key-id <key_id_or_token>`: Immediately revoke a key.

---

## 10. Plugin Subsystem Settings

Configures the trusted in-process plugin loader and hook executor.

| Environment Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `PLUGINS_PLUGIN_DIRECTORY` | `string` | `"plugins"` | Filesystem directory containing plugin modules. |
| `PLUGINS_AUTO_LOAD` | `boolean` | `false` | Automatically load all plugins from the directory at startup. |
| `PLUGINS_ALLOW_DYNAMIC_LOADING` | `boolean` | `true` | Allow runtime plugin loading and reloading via CLI or API. |

