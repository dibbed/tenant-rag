import pytest

from ragbot.rag.loaders.base import BaseLoader, Document


def test_document_validation_and_loader_info():
    d = Document(content="x", metadata={"a": 1}, source="src", document_type="txt")
    assert d.content == "x"
    with pytest.raises(ValueError):
        Document(content="x", metadata="not-dict")  # type: ignore

    class L(BaseLoader):
        async def load(self, source: str):  # pragma: no cover - not executed
            return Document(content="", metadata={}, source=source)

        def validate_source(self, source: str) -> bool:  # pragma: no cover
            return True

    loader = L()
    info = loader.get_loader_info()
    assert info["name"] == "L"
    assert info["supported_extensions"] == []

