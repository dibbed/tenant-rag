"""
Configuration migration utilities for vector-store settings.

Usage programmatically or via CLI: generate a migrated .env with new keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

ENV_MAPPINGS: Dict[str, str] = {
    # Provider
    "VECTOR_STORE_DEFAULT_STORE": "VECTOR_DB",
    # Chroma
    "VECTOR_STORE_CHROMA_PERSIST_DIRECTORY": "STORE_CHROMA_PERSIST_DIRECTORY",
    "VECTOR_STORE_CHROMA_COLLECTION_NAME": "STORE_CHROMA_COLLECTION_NAME",
    "VECTOR_STORE_CHROMA_DISTANCE_FUNCTION": "STORE_CHROMA_DISTANCE_FUNCTION",
    # Qdrant
    "VECTOR_STORE_QDRANT_URL": "STORE_QDRANT_URL",
    "VECTOR_STORE_QDRANT_PATH": "STORE_QDRANT_PATH",
    "VECTOR_STORE_QDRANT_COLLECTION_NAME": "STORE_QDRANT_COLLECTION_NAME",
    "VECTOR_STORE_QDRANT_VECTOR_SIZE": "STORE_QDRANT_VECTOR_SIZE",
    "VECTOR_STORE_QDRANT_TIMEOUT": "STORE_QDRANT_TIMEOUT",
    # Weaviate
    "VECTOR_STORE_WEAVIATE_URL": "STORE_WEAVIATE_URL",
    "VECTOR_STORE_WEAVIATE_API_KEY": "STORE_WEAVIATE_API_KEY",
    "VECTOR_STORE_WEAVIATE_CLASS_NAME": "STORE_WEAVIATE_CLASS_NAME",
    "VECTOR_STORE_WEAVIATE_VECTOR_SIZE": "STORE_WEAVIATE_VECTOR_SIZE",
    "VECTOR_STORE_WEAVIATE_TIMEOUT": "STORE_WEAVIATE_TIMEOUT",
}


def migrate_env_content(content: str) -> Tuple[str, int]:
    """Return migrated .env content and number of keys changed."""
    changed = 0
    lines = content.splitlines()
    out_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        if "=" not in line:
            out_lines.append(line)
            continue
        k, v = line.split("=", 1)
        k2 = ENV_MAPPINGS.get(k.strip(), k.strip())
        if k2 != k.strip():
            changed += 1
        out_lines.append(f"{k2}={v}")
    return ("\n".join(out_lines) + ("\n" if content.endswith("\n") else ""), changed)


def migrate_env_file(in_path: str, out_path: str) -> Dict[str, int | str]:
    """Migrate an env file writing output to out_path and return a summary."""
    src = Path(in_path)
    dst = Path(out_path)
    text = src.read_text(encoding="utf-8")
    out_text, changed = migrate_env_content(text)
    dst.write_text(out_text, encoding="utf-8")
    return {"input": str(src), "output": str(dst), "changed_keys": changed}
