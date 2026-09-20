# 💡 RAGBot API Usage Examples

This guide provides practical examples for integrating with RAGBot via `curl`, Python (`httpx`), and JavaScript (`fetch`).

---

## 1. System Health Check

Verify all subsystems (vector store, embedders, cache, and LLM) are healthy:

### cURL
```bash
curl -X GET "http://localhost:8000/health"
```

### Python (`httpx`)
```python
import httpx

response = httpx.get("http://localhost:8000/health")
print(response.json())
```

---

## 2. Ingesting Documents

### A. Uploading a File (PDF, DOCX, TXT, etc.)

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -F "file=@./sample_documents/company_policy.pdf"
```

#### Python (`httpx`)
```python
import httpx

files = {"file": open("sample_documents/company_policy.pdf", "rb")}
response = httpx.post("http://localhost:8000/api/v1/documents/upload", files=files)
print(response.json())
```

**Response:**
```json
{
  "success": true,
  "document_id": "doc_8f4b1a2c",
  "title": "company_policy.pdf",
  "source": "company_policy.pdf",
  "chunks_created": 14,
  "processing_time": 1.25,
  "metadata": {
    "source_type": "pdf",
    "pages": 5
  }
}
```

---

### B. Ingesting Plain Text Directly

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/documents/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Remote work policy: Employees may work remotely up to 3 days per week with manager approval.",
    "title": "remote_work_policy",
    "metadata": {"department": "HR", "year": 2026}
  }'
```

#### Python (`httpx`)
```python
import httpx

payload = {
    "text": "Remote work policy: Employees may work remotely up to 3 days per week with manager approval.",
    "title": "remote_work_policy",
    "metadata": {"department": "HR", "year": 2026}
}
response = httpx.post("http://localhost:8000/api/v1/documents/text", json=payload)
print(response.json())
```

---

### C. Ingesting Content from a Web URL

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/documents/url" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
    "title": "RAG Overview"
  }'
```

---

## 3. Querying the Knowledge Base

### A. English Question

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many days can employees work remotely?",
    "language": "en",
    "top_k": 3,
    "similarity_threshold": 0.5
  }'
```

**Response:**
```json
{
  "answer": "According to the company policy, employees are permitted to work remotely up to 3 days per week with manager approval.",
  "sources": [
    "remote_work_policy"
  ],
  "confidence_score": 0.94,
  "processing_time": 0.65,
  "language": "en",
  "retrieved_chunks": 1,
  "metadata": {}
}
```

---

### B. Persian Question (فارسی)

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "سیاست کاری دورکاری به چه صورت است؟",
    "language": "fa",
    "top_k": 3,
    "similarity_threshold": 0.5
  }'
```

**Response:**
```json
{
  "answer": "بر اساس خط‌مشی سازمانی، کارمندان می‌توانند با تایید مدیر تا سقف ۳ روز در هفته به صورت دورکاری فعالیت نمایند.",
  "sources": [
    "remote_work_policy"
  ],
  "confidence_score": 0.92,
  "processing_time": 0.72,
  "language": "fa",
  "retrieved_chunks": 1,
  "metadata": {}
}
```

---

## 4. Resetting the Knowledge Base

Clear all stored vectors and invalidate semantic cache entries:

#### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/documents/reset"
```

**Response:**
```json
{
  "success": true,
  "message": "Vector store and associated caches reset successfully",
  "timestamp": 1726817200.5
}
```
