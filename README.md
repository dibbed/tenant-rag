# RAG Telegram Assistant

[![CI](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)
![Coverage](https://img.shields.io/badge/coverage-82%25-brightgreen)

Advanced Telegram bot for Retrieval-Augmented Generation (RAG) over PDFs, DOCX, URLs, and text. Full support for Persian and English. Works offline (local models) and online (OpenRouter/OpenAI/Anthropic/Ollama). Now with **multiple vector databases** (FAISS, Chroma, Qdrant, Weaviate), advanced query features, encryption, plugins, analytics, and multi-tenant support.

Persian README: see [README.fa.md](README.fa.md) · Roadmap: [Project1-RAG_Telegram_Assistant_Roadmap.md](Project1-RAG_Telegram_Assistant_Roadmap.md)

## Quick Start

1. Create and activate venv, then install deps:

   python -m venv .venv

   # Windows: .\.venv\Scripts\Activate.ps1

   # Linux/macOS:

   # source .venv/bin/activate

   pip install -U pip
   pip install -r requirements.txt

2. Copy `env.example` to `.env` (or `.env_deepseek`) and fill values. For free mode:

   LLM_PROVIDER=openrouter
   LLM_MODEL=x-ai/grok-4-fast:free
   OPENROUTER_API_KEY=your_key_here
   EMBED_PROVIDER=sentence_transformers
   EMBED_MODEL=intfloat/e5-small-v2

3. Run the bot:

   python main.py

Telegram commands:

- `/start` - Welcome and introduction
- `/add` - Add document (PDF, DOCX, URL, or text)
- `/ask <question>` - Ask question about documents
- `/aggregate <query>` - Advanced aggregation queries
- `/filter <query>` - Advanced filtering operations
- `/optimize <query>` - Query optimization suggestions
- `/score <query>` - Custom scoring algorithms
- `/reset` - Clear all documents
- `/status` - Show system status
- `/help` - Show help guide
- `/config` - Show current configuration

## Docker

    docker compose up --build -d

Mounts `./data`, `./logs`, and `~/.cache/huggingface` for offline models. Local embedding model cache is stored in `./cache/sentence_transformers`.

## Configuration Modes

### LLM Providers

- **OpenRouter** (Free): `LLM_PROVIDER=openrouter` with `LLM_MODEL=x-ai/grok-4-fast:free`
- **OpenAI**: `LLM_PROVIDER=openai` with `LLM_MODEL=gpt-3.5-turbo`
- **Anthropic**: `LLM_PROVIDER=anthropic` with `LLM_MODEL=claude-3-haiku`
- **Ollama** (Local): `LLM_PROVIDER=ollama` with `LLM_MODEL=llama2`
- **HuggingFace** (Local): `LLM_PROVIDER=hf_local` with `LLM_HF_MODEL=aidal/Persian-Mistral-7B`

### Embedding Providers

- **Sentence Transformers** (Offline): `EMBED_PROVIDER=sentence_transformers`
- **OpenAI** (Online): `EMBED_PROVIDER=openai`
- **HuggingFace** (Offline): `EMBED_PROVIDER=huggingface`

Embedding cache is enabled via CacheManager (Memory + optional Redis). Embedders check cache before computing. Semantic cache for answers is also available (configurable confidence-based writes).

### Vector Stores 🗄️

Choose from multiple vector databases based on your needs:

- **FAISS** (Default): `VECTOR_STORE_DEFAULT_STORE=faiss` - Fast, offline, great for development
- **Chroma**: `VECTOR_STORE_DEFAULT_STORE=chroma` - Rich metadata, perfect for RAG applications
- **Qdrant**: `VECTOR_STORE_DEFAULT_STORE=qdrant` - High performance, production-ready
- **Weaviate**: `VECTOR_STORE_DEFAULT_STORE=weaviate` - Enterprise features, GraphQL support

**Quick Setup:**

```bash
# Install all vector store dependencies
pip install -e ".[vectorstores]"

# For Qdrant/Weaviate, start the servers:
docker run -p 6333:6333 qdrant/qdrant
docker run -p 8080:8080 semitechnologies/weaviate:latest

# Switch stores anytime
export VECTOR_STORE_DEFAULT_STORE=chroma
```

**Advanced Features:**

- ✅ Migration between stores: `python -m ragbot.cli migrate-store --source faiss --target chroma`
- ✅ Performance benchmarking: `python -m ragbot.cli benchmark-stores`
- ✅ Advanced query features: aggregation, filtering, custom scoring, optimization
- ✅ Encryption & security: data protection, key management, secure backups
- ✅ Plugin system: dynamic loading, hot-swapping, marketplace
- ✅ Analytics & ML: user behavior analysis, predictive insights
- ✅ Multi-tenant support: tenant isolation, resource quotas

See [Vector Store Guide](docs/VECTOR_STORES.md) for detailed configuration.

### Offline Installation

For complete offline operation:

    pip install -e ".[offline]"
    # Install suitable torch build (CPU/GPU)
    # Example CPU: pip install torch --index-url https://download.pytorch.org/whl/cpu

Then configure:

    LLM_PROVIDER=hf_local
    LLM_HF_MODEL=aidal/Persian-Mistral-7B
    LLM_HF_DEVICE=auto  # or cuda
    EMBED_PROVIDER=sentence_transformers
    EMBED_MODEL=intfloat/e5-small-v2

---

## Features

### 📄 Document Processing

- **Supported Formats**: PDF, DOCX, TXT, URL
- **OCR Support**: `pytesseract`, `easyocr`, `google` for image-based PDFs
- **Content Sanitization**: Clean text extraction from complex documents
- **Security Limits**: Maximum 25MB file size
- **HTML Loader (async)**: Non-blocking HTTP/file IO with retries and timeouts; structural extraction of headings (h1–h6) with optional Markdown marker injection; rich metadata (title, description, canonical, OpenGraph/Twitter, language, mime); links/images with absolute URLs and configurable limits; text cleaning and normalization. Configure via env: `MULTI_FORMAT_HTML_*` keys.

### 🔍 RAG System

- **Text Chunking**: Token, Semantic, Hierarchical, Adaptive + ChunkOptimizer
- **Embeddings**: OpenAI, Sentence Transformers, HuggingFace with caching
- **Vector Storage**: FAISS, Chroma, Qdrant, Weaviate with persistence
- **Retrieval**: Hybrid search, reranking, query expansion
- **Advanced Queries**: Aggregation, filtering, custom scoring, optimization
- **Generation**: Support for 5 different LLM providers

### 🌐 Multilingual & UI

- **Languages**: Persian and English with auto-detection
- **User Interface**: Friendly messages and comprehensive guides
- **Commands**: 8 main commands + administrative commands

### 🔧 Management & Monitoring

- **Caching**: Two-tier (Memory + Redis)
- **Monitoring**: Prometheus, Grafana, Health checks
- **Logging**: Structured logging with Loguru
- **Rate Limiting**: Configurable to prevent abuse
- **Security**: Encryption, key management, secure backups
- **Analytics**: User behavior analysis, ML insights
- **Plugins**: Dynamic loading, hot-swapping, marketplace

## CLI

### Main Commands

```bash
# System status
python -m ragbot.cli status

# Clear all documents
python -m ragbot.cli reset

# Ask questions
python -m ragbot.cli query --question "What is RAG?" --lang en
python -m ragbot.cli query --question "RAG چیست؟" --lang fa --top-k 5
```

### Document Ingestion

```bash
# Single document ingestion
python -m ragbot.cli ingest --file ./docs/file.pdf
python -m ragbot.cli ingest --url https://example.com
python -m ragbot.cli ingest --text "Sample text"

# Batch ingestion (default: PDF only)
python -m ragbot.cli batch-ingest --dir ./knowledge

# Include TXT and DOCX
python -m ragbot.cli batch-ingest --dir ./knowledge --include-txt --include-docx

# Custom patterns
python -m ragbot.cli batch-ingest --dir ./knowledge --pattern "*.pdf" --pattern "*.docx"
```

## Architecture

```
ragbot/
├── app/                     # aiogram bot, routes, middlewares
├── configs/                 # pydantic settings, validators
├── outputs/                 # logging, metrics adapters
├── rag/
│   ├── loaders/             # pdf/url/text
│   ├── chunkers/            # token/semantic/hierarchical/adaptive + optimizer
│   ├── embeddings/          # openai + sentence-transformers + huggingface
│   ├── store/               # FAISS, Chroma, Qdrant, Weaviate stores
│   ├── query/               # advanced queries, aggregation, filtering, scoring
│   ├── retrieve/            # hybrid search + reranker + expansion
│   └── qa/                  # prompt + LLM
├── services/                # orchestrators (RAG)
├── security/                # encryption, key management, secure backups
├── plugins/                 # plugin system, marketplace
├── analytics/               # user behavior, ML insights, predictive analytics
├── multi_tenant/            # tenant management, isolation, quotas
└── tests/                   # unit/integration/e2e
```

## Requirements

- **Python**: 3.10+ (tested on 3.11/3.12)
- **Telegram Bot Token**: Get from [@BotFather](https://t.me/botfather)
- **API Keys**: OpenRouter/OpenAI/Anthropic (for online mode)
- **GPU**: Optional, recommended for 7B+ local models

## Key Configuration

### LLM Settings

```bash
LLM_PROVIDER=openrouter          # openai|anthropic|ollama|hf_local|openrouter
LLM_MODEL=x-ai/grok-4-fast:free  # model name
LLM_TEMPERATURE=0.3              # response creativity (0.0-2.0)
LLM_MAX_TOKENS=2000              # max response tokens
```

### Embedding Settings

```bash
EMBED_PROVIDER=sentence_transformers  # openai|sentence_transformers|huggingface
EMBED_MODEL=intfloat/e5-small-v2     # embedding model
EMBED_BATCH_SIZE=100                  # batch size
```

### RAG Settings

```bash
RAG_CHUNK_SIZE=400                    # chunk size (tokens)
RAG_CHUNK_OVERLAP=50                 # chunk overlap
RAG_TOP_K=5                          # retrieved chunks count
RAG_SIMILARITY_THRESHOLD=0.6         # similarity threshold (0.0-1.0)
RAG_MAX_CONTEXT_TOKENS=4000          # optional token budget for context sent to LLM
```

### Security Settings

```bash
SECURITY_MAX_FILE_SIZE_MB=25         # max file size
SECURITY_RATE_LIMIT_REQUESTS=20      # rate limit
SECURITY_RATE_LIMIT_WINDOW=60        # time window (seconds)
```

## Development

```bash
pytest -q          # run tests
ruff check .       # lint
mypy ragbot        # type-check
```

## Troubleshooting

### Performance Issues

- **Slow offline generation**: Use GPU (`LLM_HF_DEVICE=cuda`) or smaller models
- **High memory usage**: Reduce `RAG_CHUNK_SIZE` or limit `RAG_MAX_CHUNKS_PER_DOCUMENT`

### Technical Issues

- **FAISS dimension mismatch**: Store auto-adapts when empty
- **Model caching**: Ensure `./cache/sentence_transformers` is writable for local models
- **OpenRouter errors**: Verify `OPENROUTER_API_KEY` and `LLM_BASE_URL`
- **OCR errors**: Change OCR engine (`/setocr pytesseract|easyocr|google|none`)

### Complete Offline Mode

```bash
# After downloading models
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

### Logs & Debugging

- Logs stored in `./logs/ragbot.log`
- Change log level: `MONITORING_LOG_LEVEL=DEBUG`
- System status: `/status` or `python -m ragbot.cli status`

## License

MIT © 2025 — [dibbed](https://github.com/dibbed)

For Persian documentation, see [README.fa.md](README.fa.md).
