# Frequently Asked Questions (FAQ)

## 1. General Questions

### What is RAGBot?
RAGBot is an API-first Retrieval-Augmented Generation (RAG) platform. It ingests documents (PDF, Word, Excel, PowerPoint, HTML, Markdown, and text), generates semantic vector embeddings, stores them in a vector database, and synthesizes accurate, context-grounded answers to user queries using Large Language Models.

### How do I interact with RAGBot?
RAGBot operates as a standard HTTP REST API via FastAPI. You can interact with it using:
- The built-in interactive Swagger UI at `http://localhost:8000/docs`
- ReDoc UI at `http://localhost:8000/redoc`
- HTTP clients like `curl`, Postman, or custom frontends via `fetch` or Python `httpx`

### What languages are supported?
RAGBot provides native support for **English** and **Persian (فارسی)**. Queries automatically adapt prompt templates and retrieval ranking to the requested language.

---

## 2. Ingestion & Documents

### What document file formats can I upload?
RAGBot supports:
- **Documents**: PDF (`.pdf`), Microsoft Word (`.docx`), Plain Text (`.txt`), Markdown (`.md`)
- **Web Pages**: HTML files (`.html`, `.htm`) and remote URLs (`http://` / `https://`)
- **Presentations & Spreadsheets**: PowerPoint (`.pptx`), Excel (`.xlsx`)
- **Images (via OCR)**: PNG, JPG, JPEG, TIFF, BMP (when OCR dependencies are installed)

### What is the maximum file size?
The default maximum upload size is **50 MB** (configurable via `SECURITY_MAX_FILE_SIZE_MB` in `.env`). Files exceeding this limit are rejected with `HTTP 413 Request Entity Too Large`.

---

## 3. Models & Hardware

### What LLM providers can I use?
RAGBot supports five providers configurable via `LLM_PROVIDER`:
- **OpenAI**: `gpt-3.5-turbo`, `gpt-4o`, `gpt-4o-mini`
- **Anthropic**: `claude-3-haiku-20240307`, `claude-3-5-sonnet-20240620`
- **OpenRouter**: Access to numerous hosted models (including free tiers like `x-ai/grok-4-fast:free`)
- **Ollama**: Local models running on an Ollama server (`llama3`, `mistral`, `qwen`)
- **HuggingFace Local**: Directly loading transformers checkpoints on local hardware

### Can RAGBot run completely offline?
**Yes.** Set:
```env
EMBED_PROVIDER=sentence_transformers
EMBED_MODEL=intfloat/e5-small-v2
VECTOR_STORE_DEFAULT_STORE=faiss
LLM_PROVIDER=ollama  # or hf_local
```
SentenceTransformers runs embeddings locally on CPU, FAISS runs index operations locally, and Ollama provides local model inference.

### Why do automated tests require CPU isolation?
Running PyTorch or CUDA operations during continuous unit testing can trigger GPU memory contention and display freezes on desktop workstations. Setting `$env:CUDA_VISIBLE_DEVICES = ""` and `$env:TORCH_DEVICE = "cpu"` forces safe, reproducible CPU-only test execution.

---

## 4. Operational & Architecture

### How does the Rate Limiter work?
RAGBot enforces an in-memory sliding-window rate limit per client IP address. The default is **60 requests per 60 seconds** (`SECURITY_RATE_LIMIT_REQUESTS=60`, `SECURITY_RATE_LIMIT_WINDOW=60`). Exceeding the quota returns `HTTP 429 Too Many Requests` with a `Retry-After` header.

### How does the Semantic Cache work?
Before executing vector database retrieval and calling the LLM, RAGBot computes the cosine similarity of the query embedding against recently cached query embeddings. If similarity exceeds `CACHE_SIMILARITY_THRESHOLD` (default `0.85`), the cached answer is returned immediately in under 50ms.

### How do I clear the knowledge base?
Send an authenticated HTTP POST request to:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/reset"
```
This clears the vector store index files and purges all semantic and general cache entries.
