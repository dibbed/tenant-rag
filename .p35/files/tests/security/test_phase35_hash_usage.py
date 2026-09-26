"""Phase 3.5 regression tests: every MD5 use is classified (Bandit B324).

docs/security/PHASE3_5_SECURITY_HARDENING.md has the table.

Security-sensitive uses (keys of caches that every tenant shares, and file
names of the plugin marketplace cache) use SHA-256. The remaining MD5 uses are
stable identifiers without a security property: they pass
usedforsecurity=False and keep their values, because stored chunk ids,
document ids and fallback vectors depend on them.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[2]
SHA256_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
WEAK = {"md5", "sha1", "md4", "md2"}

# (file, function): number of MD5 calls that stay, and why they stay.
NON_SECURITY_MD5 = {
    ("ragbot/caching/semantic_cache.py", "_get_query_embedding"): (1, "seed of a deterministic fallback vector"),
    ("ragbot/rag/chunkers/semantic_chunker.py", "_generate_chunk_id"): (1, "stored chunk id"),
    ("ragbot/rag/chunkers/token_chunker.py", "_generate_chunk_id"): (1, "stored chunk id"),
    ("ragbot/rag/store/faiss_store.py", "_generate_deterministic_embeddings"): (1, "deterministic fallback vector"),
    ("ragbot/services/document_service.py", "load_document_with_multi_format"): (1, "stored document id"),
    ("ragbot/services/document_service.py", "generate_document_id"): (1, "readable id prefix"),
}


def _weak_hash_calls() -> Iterator[tuple[str, str, str, ast.Call]]:
    for path in sorted((ROOT / "ragbot").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            func = node.func
            if not (isinstance(func.value, ast.Name) and func.value.id == "hashlib"):
                continue
            name = func.attr
            if name == "new" and node.args and isinstance(node.args[0], ast.Constant):
                name = str(node.args[0].value).lower()
            if name not in WEAK:
                continue
            owner: Any = node
            while owner in parents and not isinstance(owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owner = parents[owner]
            yield path.relative_to(ROOT).as_posix(), getattr(owner, "name", "<module>"), name, node


def test_every_weak_hash_is_a_reviewed_non_security_use() -> None:
    found: dict[tuple[str, str], int] = {}
    for relative, function, name, node in _weak_hash_calls():
        location = (relative, function)
        assert name == "md5", (location, name)
        flags = {keyword.arg: keyword.value for keyword in node.keywords}
        flag = flags.get("usedforsecurity")
        assert isinstance(flag, ast.Constant) and flag.value is False, location
        found[location] = found.get(location, 0) + 1
    assert found == {location: count for location, (count, _) in NON_SECURITY_MD5.items()}


def test_shared_cache_keys_use_sha256() -> None:
    from ragbot.caching.base import CacheKey

    assert CacheKey.embedding("abc", "model-x") == f"embedding:model-x:{SHA256_ABC}"
    assert CacheKey.query_result("abc", "ctx", "llm", "en") == f"query:llm:en:{SHA256_ABC}:ctx"
    assert CacheKey.document_chunks("abc", 512, 64) == f"chunks:512:64:{SHA256_ABC}"


def test_the_embedding_cache_keys_use_sha256() -> None:
    from ragbot.rag.embeddings.base import BaseEmbedder
    from ragbot.rag.embeddings.st_embedder import _embedding_cache_key

    assert _embedding_cache_key("abc") == SHA256_ABC
    embedder = SimpleNamespace(model_name="m")
    assert BaseEmbedder.get_cache_key(embedder, "abc") == hashlib.sha256(b"m|abc|[]").hexdigest()


async def test_the_marketplace_search_cache_is_named_with_sha256_and_read_back(tmp_path: Path) -> None:
    from ragbot.plugins.base_plugin import PluginType
    from ragbot.plugins.plugin_marketplace import MarketplacePlugin, PluginMarketplace

    marketplace = PluginMarketplace(marketplace_url="https://marketplace.invalid", local_cache_dir=str(tmp_path / "cache"))
    plugin = MarketplacePlugin(
        id="p1",
        name="Plugin 1",
        version="1.0.0",
        description="test plugin",
        author="tester",
        plugin_type=next(iter(PluginType)),
        downloads=3,
        rating=4.5,
        tags=[],
        dependencies=[],
        download_url="https://marketplace.invalid/download/p1",
    )
    await marketplace._cache_search_results("abc", [plugin])
    assert (tmp_path / "cache" / f"search_{SHA256_ABC}.json").exists()
    cached = await marketplace._get_cached_search_results("abc")
    assert [item.id for item in cached] == ["p1"]


def test_stored_chunk_ids_keep_their_md5_values() -> None:
    from ragbot.rag.chunkers.semantic_chunker import SemanticChunker
    from ragbot.rag.chunkers.token_chunker import TokenChunker

    token = SimpleNamespace(chunk_size=512, chunk_overlap=64)
    expected = hashlib.md5(b"doc-1_3_512_64", usedforsecurity=False).hexdigest()[:12]
    assert TokenChunker._generate_chunk_id(token, "doc-1", 3) == expected
    semantic = SimpleNamespace(similarity_threshold=0.75)
    expected = hashlib.md5(b"doc-1_semantic_3_0.75", usedforsecurity=False).hexdigest()[:12]
    assert SemanticChunker._generate_chunk_id(semantic, "doc-1", 3) == expected


def test_document_ids_keep_their_md5_values() -> None:
    from ragbot.services.document_service import DocumentService

    service = DocumentService.__new__(DocumentService)
    prefix, digest, timestamp = DocumentService.generate_document_id(service, "abc", "text").split("_")
    # RFC 1321 test vector: MD5("abc") = 900150983cd24fb0d6963f7d28e17f72
    assert (prefix, digest) == ("text", "90015098")
    assert timestamp.isdigit()


def test_the_deterministic_fallback_vector_is_unchanged() -> None:
    from ragbot.rag.store.faiss_store import _generate_deterministic_embeddings

    digest = hashlib.md5(b"hello_0", usedforsecurity=False).digest()
    expected = [int.from_bytes(digest[index : index + 4], "big") / (2**32 - 1) * 2 - 1 for index in range(0, 16, 4)]
    vector = _generate_deterministic_embeddings(["hello"])[0]
    assert len(vector) == 768
    assert vector[:4] == expected
    assert vector[4:] == [0.0] * 764
