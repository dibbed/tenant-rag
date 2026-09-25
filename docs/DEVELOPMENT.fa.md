# 🔧 راهنمای توسعه

## راه‌اندازی محیط توسعه

### پیش‌نیازها
- Python 3.11+
- Git
- IDE (VS Code توصیه می‌شود)

### نصب ابزارهای توسعه
```bash
# کلون پروژه
git clone https://github.com/dibbed/tenant-rag.git
cd tenant-rag

# ایجاد محیط مجازی
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# نصب وابستگی‌های توسعه
pip install -e ".[dev]"

# نصب pre-commit hooks
pre-commit install
```

## کیفیت کد

### اشاره‌های نوع (Type Hints)
```python
from typing import List, Optional, Dict, Any

class DocumentProcessor:
    def __init__(self, chunk_size: int = 512) -> None:
        self.chunk_size = chunk_size

    async def process(self, text: str) -> List[Dict[str, Any]]:
        """پردازش متن و تولید chunks"""
        chunks = self._split_text(text)
        return [{"content": chunk, "index": i} for i, chunk in enumerate(chunks)]
```

### مستندات (Docstrings)
```python
def calculate_similarity(vector1: List[float], vector2: List[float]) -> float:
    """محاسبه شباهت کسینوسی بین دو بردار.

    Args:
        vector1: بردار اول
        vector2: بردار دوم

    Returns:
        مقدار شباهت بین 0 و 1

    Raises:
        ValueError: اگر طول بردارها متفاوت باشد

    Example:
        >>> similarity = calculate_similarity([1, 0, 0], [0, 1, 0])
        >>> print(similarity)
        0.0
    """
    if len(vector1) != len(vector2):
        raise ValueError("طول بردارها باید یکسان باشد")

    # محاسبه شباهت کسینوسی
    dot_product = sum(a * b for a, b in zip(vector1, vector2))
    magnitude1 = sum(a * a for a in vector1) ** 0.5
    magnitude2 = sum(b * b for b in vector2) ** 0.5

    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0

    return dot_product / (magnitude1 * magnitude2)
```

### Linting و فرمت
```bash
# بررسی کد با ruff
ruff check .

# فرمت کردن کد
ruff format .

# بررسی نوع با mypy
mypy ragbot

# بررسی امنیت با bandit
bandit -r ragbot
```

## معماری و الگوهای طراحی

### Dependency Injection
```python
from abc import ABC, abstractmethod
from typing import Protocol

class Embedder(Protocol):
    async def embed(self, texts: List[str]) -> List[List[float]]:
        ...

class VectorStore(Protocol):
    async def add(self, vectors: List[List[float]], metadata: List[Dict]) -> None:
        ...

    async def search(self, query_vector: List[float], k: int) -> List[Dict]:
        ...

class RAGService:
    def __init__(self, embedder: Embedder, store: VectorStore):
        self.embedder = embedder
        self.store = store

    async def add_document(self, text: str) -> None:
        chunks = self._chunk_text(text)
        vectors = await self.embedder.embed(chunks)
        metadata = [{"content": chunk} for chunk in chunks]
        await self.store.add(vectors, metadata)
```

### Factory Pattern
```python
class EmbedderFactory:
    @staticmethod
    def create(config: Dict[str, Any]) -> Embedder:
        embedder_type = config.get("type", "openai")

        if embedder_type == "openai":
            return OpenAIEmbedder(
                api_key=config["api_key"],
                model=config.get("model", "text-embedding-ada-002")
            )
        elif embedder_type == "huggingface":
            return HuggingFaceEmbedder(
                model_name=config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
            )
        else:
            raise ValueError(f"نوع embedder پشتیبانی نمی‌شود: {embedder_type}")
```

### Repository Pattern
```python
class DocumentRepository:
    def __init__(self, store: VectorStore):
        self.store = store

    async def save_document(self, document: Document) -> str:
        """ذخیره سند و بازگشت ID"""
        doc_id = generate_id()
        await self.store.add(
            vectors=[document.vector],
            metadata=[{"id": doc_id, "content": document.content}]
        )
        return doc_id

    async def find_similar(self, query_vector: List[float], limit: int = 5) -> List[Document]:
        """جستجوی اسناد مشابه"""
        results = await self.store.search(query_vector, limit)
        return [Document.from_metadata(result) for result in results]
```

## تست‌نویسی

### تست واحد
```python
import pytest
from unittest.mock import Mock, AsyncMock

class TestRAGService:
    @pytest.fixture
    def mock_embedder(self):
        embedder = Mock()
        embedder.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
        return embedder

    @pytest.fixture
    def mock_store(self):
        store = Mock()
        store.add = AsyncMock()
        store.search = AsyncMock(return_value=[{"content": "test"}])
        return store

    @pytest.fixture
    def rag_service(self, mock_embedder, mock_store):
        return RAGService(mock_embedder, mock_store)

    @pytest.mark.asyncio
    async def test_add_document(self, rag_service, mock_embedder, mock_store):
        await rag_service.add_document("test document")

        mock_embedder.embed.assert_called_once()
        mock_store.add.assert_called_once()
```

### تست ادغام
```python
@pytest.mark.integration
class TestRAGIntegration:
    @pytest.fixture
    async def real_embedder(self):
        return OpenAIEmbedder(api_key="test-key")

    @pytest.fixture
    async def real_store(self, tmp_path):
        return FAISSStore(str(tmp_path / "test_index"))

    @pytest.mark.asyncio
    async def test_full_pipeline(self, real_embedder, real_store):
        service = RAGService(real_embedder, real_store)

        # اضافه کردن سند
        await service.add_document("این یک سند تست است")

        # جستجو
        results = await service.search("سند تست")
        assert len(results) > 0
```

## اضافه کردن ویژگی جدید

### 1. ایجاد Loader جدید
```python
# ragbot/rag/loaders/docx.py
from typing import List
from .base import DocumentLoader, Document

class DOCXLoader(DocumentLoader):
    """بارگذار فایل‌های Word"""

    async def load(self, file_path: str) -> List[Document]:
        """بارگذاری فایل DOCX"""
        try:
            import docx
        except ImportError:
            raise ImportError("برای استفاده از DOCXLoader، python-docx را نصب کنید")

        doc = docx.Document(file_path)
        content = "\n".join([paragraph.text for paragraph in doc.paragraphs])

        return [Document(
            content=content,
            metadata={"source": file_path, "type": "docx"}
        )]
```

### 2. ثبت در Factory
```python
# ragbot/rag/loaders/__init__.py
from .docx import DOCXLoader

class LoaderFactory:
    @staticmethod
    def create(file_type: str) -> DocumentLoader:
        loaders = {
            "pdf": PDFLoader,
            "txt": TextLoader,
            "docx": DOCXLoader,  # اضافه شده
        }

        if file_type not in loaders:
            raise ValueError(f"نوع فایل پشتیبانی نمی‌شود: {file_type}")

        return loaders[file_type]()
```

### 3. اضافه کردن تست
```python
# tests/unit/test_docx_loader.py
import pytest
from ragbot.rag.loaders.docx import DOCXLoader

class TestDOCXLoader:
    @pytest.mark.asyncio
    async def test_load_docx_file(self, sample_docx_file):
        loader = DOCXLoader()
        documents = await loader.load(sample_docx_file)

        assert len(documents) == 1
        assert documents[0].content
        assert documents[0].metadata["type"] == "docx"
```

## بهترین تمرین‌ها

### مدیریت خطا
```python
from ragbot.rag.exceptions import RAGException, EmbeddingError

class DocumentProcessor:
    async def process(self, text: str) -> List[str]:
        try:
            chunks = self._split_text(text)
            if not chunks:
                raise ValueError("متن خالی یا نامعتبر")
            return chunks
        except Exception as e:
            logger.error(f"خطا در پردازش سند: {e}")
            raise RAGException(f"پردازش سند ناموفق: {e}") from e
```

### لاگ‌گیری
```python
import logging
from ragbot.outputs.logger import get_logger

logger = get_logger(__name__)

class EmbeddingService:
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        logger.info(f"تولید embedding برای {len(texts)} متن")

        try:
            embeddings = await self._call_api(texts)
            logger.debug(f"embedding تولید شد: {len(embeddings)} بردار")
            return embeddings
        except Exception as e:
            logger.error(f"خطا در تولید embedding: {e}")
            raise
```

### پیکربندی
```python
from pydantic import BaseSettings, Field

class RAGSettings(BaseSettings):
    chunk_size: int = Field(512, description="اندازه chunk متن")
    overlap_size: int = Field(50, description="اندازه overlap بین chunks")
    max_chunks: int = Field(100, description="حداکثر تعداد chunks")

    class Config:
        env_prefix = "RAG_"
        case_sensitive = False
```

## CI/CD

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### GitHub Actions
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run linting
        run: |
          ruff check .
          mypy ragbot

      - name: Run tests
        run: |
          pytest --cov=ragbot --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## اجرای سرور و تست‌ها

### ۱. اجرای سرور API محلی
```bash
python main.py
# یا:
uvicorn ragbot.api.app:app --host 0.0.0.0 --port 8000 --reload
```

### ۲. اجرای تست‌ها با ایزولاسیون پردازنده (CPU Isolation)
برای جلوگیری از خطاهای کرش یا فریز شدن کارت گرافیک (CUDA OOM)، تست‌ها باید حتماً روی CPU اجرا شوند:

```powershell
# در ویندوز (PowerShell):
$env:CUDA_VISIBLE_DEVICES = ""
$env:TORCH_DEVICE = "cpu"
.\venv\Scripts\pytest.exe -o addopts='' -q

# در لینوکس یا مک:
export CUDA_VISIBLE_DEVICES=""
export TORCH_DEVICE="cpu"
pytest -o addopts='' -q
```
