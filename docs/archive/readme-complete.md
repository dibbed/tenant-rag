# Archived Documentation

> [!NOTE]
> This document describes the previous Telegram-based architecture, experiments, or historical roadmap.
> The active production system uses the API-first architecture described in [README.md](../../README.md) and [docs/API.md](../API.md).

---

# RAG Telegram Assistant

[![CI](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/dibbed/rag-telegram-assistant/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)
![Coverage](https://img.shields.io/badge/coverage-82%25-brightgreen)

A production-ready, multilingual Telegram bot that uses Retrieval-Augmented Generation (RAG) to answer questions about your documents. It supports a wide range of file formats, LLM providers, embedding models, and vector databases, offering extensive customization for both online and offline use.

This assistant allows you to create a private, intelligent knowledge base that you can interact with directly through Telegram.

## Core Features

- **Conversational Interface**: Interact with your knowledge base through a simple and intuitive Telegram chat interface.
- **Multi-Format Document Support**: Ingest and process various document types, including PDF, DOCX, TXT, and web pages (URLs).
- **Advanced RAG Pipeline**: A sophisticated, configurable pipeline for optimal performance and accuracy.
- **Extensive LLM & Embedding Support**: Plug-and-play with different models to balance cost, performance, and privacy.
- **Flexible Vector Storage**: Choose the best vector database for your needs, from simple local files to production-grade servers.
- **Multilingual**: Fully functional in both English and Persian, with support for other languages.
- **Offline Capability**: Can run entirely offline using local models, ensuring data privacy and availability without an internet connection.
- **Enterprise-Ready**: Includes features like monitoring, security, caching, and a robust architecture.

## How It Works

The project follows a classic Retrieval-Augmented Generation (RAG) architecture, orchestrated within a Telegram bot framework.

1.  **Ingestion**: You send a document or URL to the bot. The system automatically extracts the text content. For image-based PDFs, it can use Optical Character Recognition (OCR).
2.  **Chunking**: The extracted text is divided into smaller, manageable pieces (chunks) to ensure that retrieval is focused and relevant.
3.  **Embedding**: Each chunk is converted into a numerical representation (a vector) using a powerful embedding model. This process captures the semantic meaning of the text.
4.  **Storage**: The vectors are stored in a specialized vector database, creating an indexed, searchable knowledge base.
5.  **Retrieval**: When you ask a question, the bot converts your query into a vector and uses it to search the database for the most semantically similar text chunks.
6.  **Generation**: The retrieved chunks (the "context") are combined with your original question and sent to a Large Language Model (LLM), which generates a coherent, context-aware answer.

This entire process is seamless. You simply add documents and ask questions.

## Technical Capabilities

### 1. Supported Models & Providers

The system is designed for maximum flexibility, allowing you to switch between different services and models via configuration.

| Category             | Supported Providers                                        | Examples                                         |
| -------------------- | ---------------------------------------------------------- | ------------------------------------------------ |
| **LLM Providers**    | OpenRouter, OpenAI, Anthropic, Ollama, HuggingFace (local) | `grok-4-fast`, `gpt-4`, `claude-3`, `llama3`     |
| **Embedding Models** | Sentence Transformers, OpenAI, HuggingFace (local)         | `intfloat/e5-small-v2`, `text-embedding-3-small` |
| **Vector Databases** | FAISS, Chroma, Qdrant, Weaviate                            | Local file-based, in-memory, or server-based     |

### 2. Document Processing

- **Advanced URL Loader**: Asynchronously fetches and parses web pages. It can extract structural elements (headings), clean HTML content, and resolve relative links for images and other resources.
- **OCR Integration**: Supports multiple OCR engines (`pytesseract`, `easyocr`, `google-cloud-vision`) to extract text from scanned documents or images within PDFs.
- **Content Sanitization**: Includes mechanisms to clean and normalize text extracted from various document formats, improving the quality of the knowledge base.

### 3. RAG Pipeline Configuration

Nearly every aspect of the RAG pipeline can be fine-tuned:

- **Chunking Strategy**: Control the size (`RAG_CHUNK_SIZE`) and overlap (`RAG_CHUNK_OVERLAP`) of text chunks.
- **Retrieval Parameters**: Adjust the number of chunks to retrieve (`RAG_TOP_K`) and the required similarity score (`RAG_SIMILARITY_THRESHOLD`).
- **LLM Generation**: Modify the creativity (`LLM_TEMPERATURE`) and length (`LLM_MAX_TOKENS`) of the generated answers.

### 4. Caching & Performance

- **Redis Integration**: An optional two-tier caching system (in-memory and Redis) can be enabled to store generated answers and embeddings, reducing latency and redundant computations.
- **Asynchronous Architecture**: Built on `asyncio`, the bot handles multiple requests concurrently without blocking, ensuring a responsive user experience.

### 5. Security & Administration

- **User Allowlist**: Restrict bot access to a predefined list of Telegram user IDs.
- **Rate Limiting**: Prevent abuse by limiting the number of requests a user can make within a specific time window.
- **File Size Limits**: Configure the maximum allowed size for uploaded documents.
- **Allowed File Types**: Specify which file extensions are permissible for ingestion.

### 6. Monitoring & Observability

- **Health Checks**: An integrated health check endpoint to monitor the status of the bot and its dependencies.
- **Prometheus Metrics**: Exposes performance metrics (e.g., request latency, error rates) that can be scraped by Prometheus for monitoring and alerting.
- **Structured Logging**: Detailed and structured logs provide deep insight into the application's behavior for easier debugging.

## Getting Started

### Prerequisites

- Python 3.10+
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)
- API keys for any online services you wish to use (e.g., OpenRouter, OpenAI).

### Installation

1.  **Clone the repository and create a virtual environment:**

    ```bash
    git clone <repository-url>
    cd <repository-directory>
    python -m venv .venv
    source .venv/bin/activate  # On Windows, use .\.venv\Scripts\Activate.ps1
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure the application:**

    - Copy `env.example` to a new file named `.env`.
    - Open `.env` and fill in the required values, starting with your `BOT_TOKEN` and `ALLOW_USERS`.
    - Choose your desired `LLM_PROVIDER`, `EMBED_PROVIDER`, and `VECTOR_DB`.

4.  **Run the bot:**
    ```bash
    python main.py
    ```

### Docker Deployment

For a containerized setup, you can use Docker:

```bash
docker compose up --build -d
```

This will build the image and run the bot in a detached container. The `docker-compose.yml` file is pre-configured to mount volumes for data, logs, and model caches, ensuring data persistence across container restarts.

## Basic Bot Commands

- `/start`: Displays a welcome message.
- `/add`: Reply to a document (or send it with the command) to add it to the knowledge base.
- `/ask <your question>`: Ask a question about the ingested documents.
- `/reset`: Clears the entire knowledge base for your user.
- `/help`: Shows a help guide.
- `/config`: Displays the current RAG configuration.

This project provides a powerful, private, and highly customizable solution for building a personal or organizational knowledge assistant. By leveraging the flexibility of its architecture, you can tailor it to your exact needs, whether for research, customer support, or personal knowledge management.
