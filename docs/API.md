# API Documentation

## Overview

The RAG Telegram Assistant provides a comprehensive API for document ingestion, query processing, and system management. This document covers all available interfaces, including Telegram bot commands, internal APIs, and extension points.

## Telegram Bot API

### Commands

#### `/start`

**Description**: Initialize bot interaction and display welcome message

**Usage**: `/start`

**Response**: Welcome message with bot capabilities and available commands

**Example**:

```
User: /start
Bot: 🤖 سلام! من دستیار RAG هستم...
```

#### `/add`

**Description**: Add documents to the knowledge base

**Usage**:

- `/add <text>` - Add plain text
- `/add` + file attachment (PDF/DOCX/TXT/HTML/MD/PPTX/XLSX/Images[OCR])
- `/add <URL>` - Add content from URL

**Parameters**:

- `content` (string): Text content, URL, or file attachment
- File types supported (dynamic): PDF, DOCX, TXT, HTML/HTM, MD, PPTX, XLSX, PNG/JPG/JPEG/TIFF/BMP (OCR)
- Max file size: 50MB
- URL timeout: 30 seconds

**Response**: Confirmation with processing statistics

**Examples**:

```
# Add text
User: /add This is important information about machine learning.
Bot: ✅ متن با موفقیت اضافه شد. (1 chunk ایجاد شد)

# Add URL
User: /add https://example.com/article.pdf
Bot: ✅ سند از URL دریافت و اضافه شد. (5 chunks ایجاد شد)

# Add file (attach PDF)
User: /add [PDF/DOCX attachment]
Bot: ✅ فایل (PDF/DOCX) پردازش و اضافه شد. (12 chunks ایجاد شد)
```

**Error Responses**:

- Invalid URL: `❌ URL نامعتبر است`
- File too large: `❌ حجم فایل بیش از حد مجاز است`
- Processing error: `❌ خطا در پردازش سند`

###

# `/ask`

**Description**: Query the knowledge base

**Usage**: `/ask <question>`

**Parameters**:

- `question` (string, required): The question to ask
- Language: Auto-detected (Persian/English)
- Max question length: 500 characters

**Response**: Answer with source references

**Example**:

```
User: /ask What are the benefits of machine learning?
Bot: 🤖 بر اساس اسناد موجود:

یادگیری ماشین مزایای زیر را دارد:
1. خودکارسازی فرآیندها
2. تشخیص الگوهای پیچیده
3. بهبود دقت پیش‌بینی‌ها

📚 منابع: document_1.pdf (صفحه 3), article_2.txt
```

**Error Responses**:

- Empty question: `❌ لطفاً سوال خود را بنویسید`
- No relevant documents: `❌ اطلاعات مرتبطی یافت نشد`
- Processing error: `❌ خطا در پردازش سوال`

#### `/reset`

**Description**: Clear all stored documents from knowledge base

**Usage**: `/reset`

**Response**: Confirmation of reset operation

**Example**:

```
User: /reset
Bot: ✅ تمام اسناد ذخیره شده پاک شدند.
```

#### `/help`

**Description**: Display help information and available commands

**Usage**: `/help`

**Response**: List of all commands with descriptions

#### `/status`

**Description**: Display system status and statistics

**Usage**: `/status`

**Response**: System health information

**Example**:

````
User: /status
Bot: 📊 وضعیت سیستم:
✅ ربات: فعال
✅ OpenAI API: متصل
✅ Vector Store: آماده
📄 اسناد ذخیره شده: 15
🧩 Chunks: 127
⏱️ آخرین بروزرسانی: 2 دقیقه پیش
```## Intern
al APIs

### RAG Service API

#### `RAGService.ingest_document()`
```python
async def ingest_document(
    self,
    source: str,
    source_type: Literal["text", "url", "file"]
) -> IngestResult
````

**Parameters**:

- `source`: Content source (text, URL, or file path)
- `source_type`: Type of source content

**Returns**: `IngestResult` with processing statistics

**Example**:

```python
service = RAGService()
result = await service.ingest_document(
    source="https://example.com/doc.pdf",
    source_type="url"
)
print(f"Created {result.chunks_created} chunks")
```

#### `RAGService.query_documents()`

```python
async def query_documents(
    self,
    question: str,
    lang: str = "auto"
) -> QueryResult
```

**Parameters**:

- `question`: User question
- `lang`: Response language ("fa", "en", or "auto")

**Returns**: `QueryResult` with answer and sources

**Example**:

```python
result = await service.query_documents(
    question="What is machine learning?",
    lang="en"
)
print(result.answer)
```

### Document Service API

#### `DocumentService.process_pdf()`

```python
async def process_pdf(self, file_path: str) -> Document
```

**Parameters**:

- `file_path`: Path to PDF file

**Returns**: `Document` object with extracted content

#### `DocumentService.process_url()`

```python
async def process_url(self, url: str) -> Document
```

**Parameters**:

- `url`: URL to process

**Returns**: `Document` object with extracted content### Vecto
r Store API

#### `VectorStore.add_documents()`

```python
async def add_documents(self, documents: List[Document]) -> List[str]
```

**Parameters**:

- `documents`: List of documents to add

**Returns**: List of document IDs

#### `VectorStore.similarity_search()`

```python
async def similarity_search(
    self,
    query: str,
    k: int = 4
) -> List[Document]
```

**Parameters**:

- `query`: Search query
- `k`: Number of results to return

**Returns**: List of similar documents

## Data Models

### IngestResult

```python
@dataclass
class IngestResult:
    success: bool
    document_id: str
    chunks_created: int
    processing_time: float
    error_message: Optional[str] = None
```

### QueryResult

```python
@dataclass
class QueryResult:
    answer: str
    sources: List[str]
    confidence_score: float
    processing_time: float
    language: str
```

### Document

```python
@dataclass
class Document:
    content: str
    metadata: Dict[str, Any]
    source: str
    document_type: str
```

### HealthStatus

````python
@dataclass
class HealthStatus:
    overall_status: str
    components: Dict[str, ComponentHealth]
    timestamp: datetime
    uptime: float
```#
# Configuration API

### Settings
All configuration is managed through environment variables and the `Settings` class:

```python
from ragbot.configs.settings import settings

# Access configuration
print(settings.bot_token)
print(settings.openai_api_key)
print(settings.default_lang)
````

### Environment Variables

| Variable         | Type | Default                    | Description                |
| ---------------- | ---- | -------------------------- | -------------------------- |
| `BOT_TOKEN`      | str  | Required                   | Telegram bot token         |
| `OPENAI_API_KEY` | str  | Required                   | OpenAI API key             |
| `DEFAULT_LANG`   | str  | `"fa"`                     | Default response language  |
| `VECTOR_DB`      | str  | `"faiss"`                  | Vector database type       |
| `EMBED_MODEL`    | str  | `"text-embedding-ada-002"` | Embedding model            |
| `CHUNK_SIZE`     | int  | `512`                      | Text chunk size            |
| `CHUNK_OVERLAP`  | int  | `50`                       | Chunk overlap size         |
| `TOP_K`          | int  | `4`                        | Number of retrieved chunks |
| `CACHE_TTL`      | int  | `3600`                     | Cache TTL in seconds       |
| `MAX_FILE_SIZE`  | int  | `52428800`                 | Max file size (50MB)       |
| `ALLOW_USERS`    | str  | `""`                       | Comma-separated user IDs   |
| `LOG_LEVEL`      | str  | `"INFO"`                   | Logging level              |

## Extension Points

### Custom Loaders

Implement the `BaseLoader` interface to add support for new document types:

```python
from ragbot.rag import BaseLoader

class CustomLoader(BaseLoader):
    async def load(self, source: str) -> Document:
        # Your implementation here
        pass
```

### Custom Embedders

Implement the `BaseEmbedder` interface for custom embedding providers:

```python
from ragbot.rag import BaseEmbedder

class CustomEmbedder(BaseEmbedder):
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Your implementation here
        pass
```

### Custom Vector Stores

Implement the `BaseVectorStore` interface for custom vector databases:

````python
from ragbot.rag import BaseVectorStore

class CustomVectorStore(BaseVectorStore):
    async def add_documents(self, documents: List[Document]) -> List[str]:
        # Your implementation here
        pass
```##
Error Handling

### Exception Hierarchy
```python
RAGBotException
├── DocumentProcessingError
├── EmbeddingError
├── VectorStoreError
├── ConfigurationError
└── AuthenticationError
````

### Error Responses

All API methods return structured error information:

```python
try:
    result = await service.ingest_document(source, source_type)
except DocumentProcessingError as e:
    print(f"Processing failed: {e.message}")
    print(f"Error code: {e.error_code}")
```

## Authentication & Authorization

### User Allowlist

Configure allowed users via environment variable:

```env
ALLOW_USERS=123456789,987654321
```

### Middleware Implementation

```python
from ragbot.app.middleware.auth import AuthMiddleware

# Authentication is automatically applied to all handlers
# Users not in allowlist receive "Access denied" message
```

## Monitoring & Metrics

### Health Checks

```python
from ragbot.outputs.health import HealthChecker

checker = HealthChecker()
status = await checker.get_overall_health()
```

### Metrics Collection

```python
from ragbot.outputs.metrics import MetricsCollector

metrics = MetricsCollector()
metrics.record_request_duration("query", 1.5)
metrics.increment_request_counter("ingest", "success")
```
