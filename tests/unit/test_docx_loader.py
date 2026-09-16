from pathlib import Path
from typing import Any

import pytest

from ragbot.rag import DOCXLoader


class _Run:
    def __init__(self, pt: float):
        class _Font:
            def __init__(self, pt: float):
                self.size = type("_Sz", (), {"pt": pt})()

        self.font = _Font(pt)


class _Para:
    def __init__(
        self,
        text: str,
        style_name: str | None = None,
        runs_pt: list[float] | None = None,
    ):
        self.text = text
        self.style = (
            type("_Style", (), {"name": style_name})()
            if style_name
            else type("_Style", (), {"name": ""})()
        )
        self._p = type("_P", (), {"pPr": None})()
        self.runs = [_Run(pt) for pt in (runs_pt or [])]


class _Table:
    def __init__(self, rows: list[list[str]]):
        class _Cell:
            def __init__(self, text: str):
                self.text = text

        class _Row:
            def __init__(self, texts: list[str]):
                self.cells = [_Cell(t) for t in texts]

        self.rows = [_Row(r) for r in rows]


class _Doc:
    def __init__(self, paragraphs: list[_Para], tables: list[_Table]):
        self.paragraphs = paragraphs
        self.tables = tables
        self.part = type("_Part", (), {"rels": {}})()
        self.inline_shapes = []
        self.core_properties = type(
            "_CP",
            (),
            {
                "title": "Sample",
                "author": "Tester",
                "subject": "Test",
                "created": None,
                "modified": None,
            },
        )()


@pytest.mark.asyncio
async def test_docx_headings_markers_and_table(
    monkeypatch: Any, tmp_path: Path
) -> None:
    # Build a mock DOCX with Heading styles + a table
    paras = [
        _Para("Title", style_name="Heading 1"),
        _Para("SubTitle", style_name="Heading 2"),
        _Para("Body paragraph."),
        _Para("Font heading", style_name=None, runs_pt=[20.0]),
    ]
    tables = [_Table([["c1", "c2"], ["v1", "v2"]])]
    doc = _Doc(paras, tables)

    # Patch DocxDocument to return our mock
    import ragbot.rag.loaders.docx as docx_mod

    monkeypatch.setattr(docx_mod, "DocxDocument", lambda p: doc)

    # Bypass filesystem
    monkeypatch.setattr(Path, "exists", lambda self: True)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(Path, "suffix", ".docx")

    class _Stat:
        st_size = 1

    monkeypatch.setattr(Path, "stat", lambda self: _Stat())

    loader = DOCXLoader()
    document = await loader.load(str(tmp_path / "sample.docx"))

    text = document.text
    # Markers for heading 1 and 2, plus font-based heading
    assert "# Title" in text
    assert "## SubTitle" in text
    assert "# Font heading" in text or "## Font heading" in text

    headings = document.metadata.get("headings") or []
    assert len(headings) >= 3
    assert any(h.get("level") == 1 and h.get("text") == "Title" for h in headings)
    assert any(h.get("level") == 2 and h.get("text") == "SubTitle" for h in headings)

    # Tables joined by tabs (with spaces around tab in current implementation)
    assert "c1 \t c2" in text


"""
Tests for DOCX loader functionality.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ragbot.rag.exceptions import DocumentProcessingError
from ragbot.rag import Document


class TestDOCXLoaderBasic:
    """Test basic DOCX loader functionality."""

    def test_init(self):
        """Test DOCXLoader initialization."""
        loader = DOCXLoader()
        assert isinstance(loader, DOCXLoader)
        assert loader.config == {}

    def test_init_with_config(self):
        """Test DOCXLoader initialization with config."""
        config = {"test_param": "test_value"}
        loader = DOCXLoader(**config)
        assert loader.config == config

    def test_get_supported_extensions(self):
        """Test get_supported_extensions method."""
        loader = DOCXLoader()
        extensions = loader.get_supported_extensions()
        assert extensions == [".docx"]

    def test_validate_source_valid_file(self, tmp_path):
        """Test validate_source with valid DOCX file."""
        # Create a test file
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        loader = DOCXLoader()
        assert loader.validate_source(str(test_file)) is True

    def test_validate_source_invalid_extension(self, tmp_path):
        """Test validate_source with invalid extension."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake content")

        loader = DOCXLoader()
        assert loader.validate_source(str(test_file)) is False

    def test_validate_source_nonexistent_file(self):
        """Test validate_source with nonexistent file."""
        loader = DOCXLoader()
        assert loader.validate_source("/nonexistent/file.docx") is False

    def test_validate_source_directory(self, tmp_path):
        """Test validate_source with directory."""
        test_dir = tmp_path / "test.docx"
        test_dir.mkdir()

        loader = DOCXLoader()
        assert loader.validate_source(str(test_dir)) is False

    def test_validate_source_invalid_input(self):
        """Test validate_source with invalid input types."""
        loader = DOCXLoader()
        assert loader.validate_source(None) is False
        assert loader.validate_source(123) is False
        assert loader.validate_source([]) is False


class TestDOCXLoaderLoad:
    """Test DOCX loader load functionality."""

    @pytest.mark.asyncio
    async def test_load_docx_not_available(self, tmp_path):
        """Test load when python-docx is not available."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", False):
            loader = DOCXLoader()

            with pytest.raises(ImportError, match="python-docx is required"):
                await loader.load(str(test_file))

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self):
        """Test load with nonexistent file."""
        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            loader = DOCXLoader()

            with pytest.raises(DocumentProcessingError, match="Invalid DOCX file path"):
                await loader.load("/nonexistent/file.docx")

    @pytest.mark.asyncio
    async def test_load_invalid_extension(self, tmp_path):
        """Test load with invalid file extension."""
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"fake content")

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            loader = DOCXLoader()

            with pytest.raises(DocumentProcessingError, match="Invalid DOCX file path"):
                await loader.load(str(test_file))

    @pytest.mark.asyncio
    async def test_load_file_too_large(self, tmp_path):
        """Test load with file that exceeds size limit."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                mock_settings.security.max_file_size_mb = 0.000001  # Very small limit

                with patch("docx.Document") as mock_docx:
                    mock_docx.side_effect = Exception("Should not reach here")

                    loader = DOCXLoader()

                    with pytest.raises(DocumentProcessingError, match="DOCX too large"):
                        await loader.load(str(test_file))

    @pytest.mark.asyncio
    async def test_load_successful_simple_document(self, tmp_path):
        """Test successful load of simple DOCX document."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock DocxDocument
        mock_doc = MagicMock()

        # Mock paragraphs
        mock_para1 = MagicMock()
        mock_para1.text = "First paragraph"
        mock_para2 = MagicMock()
        mock_para2.text = "Second paragraph"
        mock_para3 = MagicMock()
        mock_para3.text = ""  # Empty paragraph should be skipped

        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_doc.tables = []  # No tables

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()
                    result = await loader.load(str(test_file))

                    assert isinstance(result, Document)
                    assert result.content == "First paragraph\nSecond paragraph"
                    assert result.source == str(test_file)
                    assert result.document_type == "docx"
                    assert result.metadata["file_name"] == "test.docx"
                    assert result.metadata["loader"] == "DOCXLoader"

    @pytest.mark.asyncio
    async def test_load_document_with_tables(self, tmp_path):
        """Test load of DOCX document with tables."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock DocxDocument
        mock_doc = MagicMock()

        # Mock paragraphs
        mock_para = MagicMock()
        mock_para.text = "Document with table"
        mock_doc.paragraphs = [mock_para]

        # Mock table
        mock_cell1 = MagicMock()
        mock_cell1.text = "Cell 1"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Cell 2"
        mock_cell3 = MagicMock()
        mock_cell3.text = ""  # Empty cell

        mock_row = MagicMock()
        mock_row.cells = [mock_cell1, mock_cell2, mock_cell3]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc.tables = [mock_table]

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()
                    result = await loader.load(str(test_file))

                    expected_content = "Document with table\nCell 1 \t Cell 2"
                    assert result.content == expected_content

    @pytest.mark.asyncio
    async def test_load_empty_document(self, tmp_path):
        """Test load of empty DOCX document."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock empty DocxDocument
        mock_doc = MagicMock()
        mock_doc.paragraphs = []
        mock_doc.tables = []

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()
                    result = await loader.load(str(test_file))

                    assert result.content == ""
                    assert result.metadata["approx_chars"] == 0

    @pytest.mark.asyncio
    async def test_load_document_processing_error(self, tmp_path):
        """Test load with document processing error."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document") as mock_docx:
                mock_docx.side_effect = DocumentProcessingError(
                    "Test error", document_type="docx"
                )

                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()

                    with pytest.raises(DocumentProcessingError, match="Test error"):
                        await loader.load(str(test_file))

    @pytest.mark.asyncio
    async def test_load_generic_exception(self, tmp_path):
        """Test load with generic exception."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document") as mock_docx:
                mock_docx.side_effect = Exception("Generic error")

                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    with patch("ragbot.rag.loaders.docx.logger") as mock_logger:
                        loader = DOCXLoader()

                        with pytest.raises(
                            DocumentProcessingError, match="Generic error"
                        ):
                            await loader.load(str(test_file))

                        mock_logger.error.assert_called_once_with(
                            "Failed to read DOCX: Generic error"
                        )

    @pytest.mark.asyncio
    async def test_load_with_cell_without_text_attribute(self, tmp_path):
        """Test load with table cells that don't have text attribute."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock DocxDocument
        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        # Mock cell without text attribute
        mock_cell_no_text = MagicMock()
        del mock_cell_no_text.text  # Remove text attribute

        mock_cell_with_text = MagicMock()
        mock_cell_with_text.text = "Valid cell"

        mock_row = MagicMock()
        mock_row.cells = [mock_cell_no_text, mock_cell_with_text]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_doc.tables = [mock_table]

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()
                    result = await loader.load(str(test_file))

                    # Should only include the cell with text
                    assert result.content == "Valid cell"

    @pytest.mark.asyncio
    async def test_load_metadata_content(self, tmp_path):
        """Test that metadata contains expected fields."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock DocxDocument
        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_para.text = "Test content"
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = []

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()
                    result = await loader.load(str(test_file))

                    # Check metadata fields
                    assert result.metadata["file_name"] == "test.docx"
                    assert result.metadata["file_ext"] == ".docx"
                    assert result.metadata["source_path"] == str(test_file)
                    assert result.metadata["loader"] == "DOCXLoader"
                    assert result.metadata["approx_chars"] == len("Test content")

    @pytest.mark.asyncio
    async def test_load_size_check_exception(self, tmp_path):
        """Test load when size check raises exception."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock DocxDocument
        mock_doc = MagicMock()
        mock_para = MagicMock()
        mock_para.text = "Test content"
        mock_doc.paragraphs = [mock_para]
        mock_doc.tables = []

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    # Mock Path.stat() to raise exception
                    with patch.object(
                        Path, "stat", side_effect=Exception("Stat error")
                    ):
                        loader = DOCXLoader()
                        # Should not raise exception, just continue
                        result = await loader.load(str(test_file))
                        assert result.content == "Test content"


class TestDOCXLoaderEdgeCases:
    """Test edge cases for DOCX loader."""

    @pytest.mark.asyncio
    async def test_load_with_whitespace_only_paragraphs(self, tmp_path):
        """Test load with paragraphs containing only whitespace."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock DocxDocument
        mock_doc = MagicMock()

        # Mock paragraphs with various whitespace
        mock_para1 = MagicMock()
        mock_para1.text = "   "  # Only spaces
        mock_para2 = MagicMock()
        mock_para2.text = "\t\n"  # Tabs and newlines
        mock_para3 = MagicMock()
        mock_para3.text = "Valid content"
        mock_para4 = MagicMock()
        mock_para4.text = None  # None text

        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3, mock_para4]
        mock_doc.tables = []

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()
                    result = await loader.load(str(test_file))

                    # Should only include valid content
                    assert result.content == "Valid content"

    @pytest.mark.asyncio
    async def test_load_with_complex_table_structure(self, tmp_path):
        """Test load with complex table structure."""
        test_file = tmp_path / "test.docx"
        test_file.write_bytes(b"fake docx content")

        # Mock DocxDocument
        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        # Mock complex table with multiple rows and cells
        mock_cells_row1 = []
        for i in range(3):
            cell = MagicMock()
            cell.text = f"Row1 Cell{i + 1}"
            mock_cells_row1.append(cell)

        mock_cells_row2 = []
        for i in range(3):
            cell = MagicMock()
            cell.text = f"Row2 Cell{i + 1}"
            mock_cells_row2.append(cell)

        mock_row1 = MagicMock()
        mock_row1.cells = mock_cells_row1
        mock_row2 = MagicMock()
        mock_row2.cells = mock_cells_row2

        mock_table = MagicMock()
        mock_table.rows = [mock_row1, mock_row2]

        mock_doc.tables = [mock_table]

        with patch("ragbot.rag.loaders.docx.DOCX_AVAILABLE", True):
            with patch("docx.Document", return_value=mock_doc):
                with patch("ragbot.rag.loaders.docx.settings") as mock_settings:
                    mock_settings.security.max_file_size_mb = 50

                    loader = DOCXLoader()
                    result = await loader.load(str(test_file))

                    expected_lines = [
                        "Row1 Cell1 \t Row1 Cell2 \t Row1 Cell3",
                        "Row2 Cell1 \t Row2 Cell2 \t Row2 Cell3",
                    ]
                    expected_content = "\n".join(expected_lines)
                    assert result.content == expected_content
