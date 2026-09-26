# Contributing to TenantRAG

Thank you for your interest in contributing to TenantRAG. We welcome contributions that improve reliability, extend vector store and LLM provider support, and harden multi-tenant operations.

---

## 1. Development Setup

### Prerequisites
- Python 3.10, 3.11, or 3.12
- Git
- Virtual environment tool (`venv` or `conda`)

### Local Setup
```bash
# Clone the repository
git clone https://github.com/dibbed/tenant-rag.git
cd tenant-rag

# Create and activate virtual environment
python -m venv venv
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"

# Copy environment configuration
cp env.example .env
```

---

## 2. Running Tests

Always run the test suite before submitting pull requests:

```bash
# Run all unit, integration, and security tests
pytest

# Run tests with verbose output
pytest -v

# Run a specific test module
pytest tests/security/test_tenant_auth_security.py
```

Before you open a pull request, run the checks of the Verification Pipeline:

```bash
make verify            # every check; the container check needs Docker
make verify-security   # Security Regression Suite; needs Redis and TEST_REDIS_URL=redis://localhost:6379/15
```

If you add, rename or remove a security test, run `make security-manifest` and commit `tests/security/suite_manifest.json` with the change. A pull request that removes a security test must explain why. Details: `docs/features/security-verification-pipeline/README.md`.

---

## 3. Code Conventions & Standards

- **Formatting & Linting:** We use `ruff` for linting and code formatting.
  ```bash
  ruff check .
  ruff format .
  ```
- **Type Annotations:** Use Python type annotations (`typing`) on all new functions and methods.
- **Import Namespace:** Do not alter the internal package namespace. Core internal imports continue to resolve through `from ragbot...`.
- **Async Concurrency:** Any operations reading or mutating shared indices must respect async lock patterns (`async with self.async_lock:`).
- **Error Handling:** Avoid bare `except:`. Wrap failures with domain exceptions from `ragbot.rag.exceptions` or return structured API error responses.

---

## 4. Extending TenantRAG

### Adding a Vector Store
1. Create a store adapter inheriting from `BaseVectorStore` in `ragbot/rag/store/`.
2. Implement required methods: `add_documents`, `search`, `delete_documents`, `reset`, `get_document_count`.
3. Register the store in `VectorStoreFactory._store_registry` in `ragbot/rag/store/factory.py`.
4. Add integration tests under `tests/integration/`.

### Adding an LLM Provider
1. Add provider configuration options to `LLMSettings` in `ragbot/configs/settings.py`.
2. Implement client initialization and inference branching in `QAChain` (`ragbot/rag/qa/chain.py`).
3. Add tests verifying mock response parsing and error handling in `tests/unit/test_prompting.py`.

### Adding Plugin Hooks
1. Define new lifecycle hook types in `ragbot/plugins/base_plugin.py` (`HookType` enum).
2. Wire hook execution points in `ragbot/services/rag_service.py` using `await self.plugin_manager.execute_hooks(...)`.
3. Ensure all plugin invocations remain exception-contained so failures do not interrupt the core RAG pipeline.

---

## 5. Pull Request Expectations

- **Test Coverage:** All new features or bug fixes must include corresponding tests in `tests/`.
- **Verification Pipeline:** All Blocking Checks must pass: Tests and Security Regression Suite on Python 3.10, 3.11 and 3.12, Dependency Vulnerability Check, Container Build Check and Verification Summary. Do not skip security tests. A new HIGH or CRITICAL dependency advisory must be fixed, or the dependency must leave the default installation.
- **Clean Git History:** Write descriptive, imperative commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
- **No Performance Hype:** Do not add unverified performance assertions or quantitative benchmark claims to documentation without reproducible scripts in `benchmarks/`.
