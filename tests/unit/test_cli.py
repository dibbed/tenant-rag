"""
Tests for CLI functionality.
"""

import argparse
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from ragbot.cli import (
    _build_parser,
    _get_rag_service,
    cmd_batch_ingest,
    cmd_ingest,
    cmd_performance,
    cmd_query,
    cmd_reset,
    cmd_status,
    main,
)


@pytest.fixture
def mock_rag_service():
    """Mock RAG service for CLI tests."""
    service = AsyncMock()
    
    # Mock health status
    health_status = SimpleNamespace(
        overall_status="healthy",
        uptime=123.45,
        document_count=5
    )
    service.get_health_status.return_value = health_status
    
    # Mock reset
    service.reset_store.return_value = True
    
    # Mock query result
    query_result = SimpleNamespace(
        answer="Test answer",
        sources=["source1.pdf", "source2.txt"],
        confidence_score=0.85,
        processing_time=1.23
    )
    service.query_documents.return_value = query_result
    
    # Mock ingest result
    ingest_result = SimpleNamespace(
        success=True,
        document_id="doc123",
        chunks_created=3,
        processing_time=2.34,
        error_message=None
    )
    service.ingest_document.return_value = ingest_result
    
    # Mock batch ingest result
    batch_result = {
        "total": 2,
        "succeeded": 2,
        "failed": 0,
        "duration": 5.67,
        "results": [
            {
                "success": True,
                "document_id": "doc1",
                "chunks_created": 2,
                "processing_time": 1.0,
                "error": None,
                "source": "file1.pdf"
            },
            {
                "success": True,
                "document_id": "doc2",
                "chunks_created": 3,
                "processing_time": 2.0,
                "error": None,
                "source": "file2.pdf"
            }
        ]
    }
    service.batch_ingest.return_value = batch_result
    
    return service


@pytest.fixture
def mock_integration_service(mock_rag_service):
    """Mock integration service."""
    with patch("ragbot.cli.get_integration_service") as mock_get:
        integration = AsyncMock()
        integration.get_rag_service.return_value = mock_rag_service
        mock_get.return_value = integration
        yield integration


class TestCLIParser:
    """Test CLI argument parser."""
    
    def test_build_parser_basic(self):
        """Test basic parser construction."""
        parser = _build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog in ("tenantrag", "ragbot-cli")
    
    def test_status_command(self):
        """Test status command parsing."""
        parser = _build_parser()
        args = parser.parse_args(["status"])
        assert args.cmd == "status"
        assert args.func == cmd_status
    
    def test_reset_command(self):
        """Test reset command parsing."""
        parser = _build_parser()
        args = parser.parse_args(["reset"])
        assert args.cmd == "reset"
        assert args.func == cmd_reset
    
    def test_query_command(self):
        """Test query command parsing."""
        parser = _build_parser()
        args = parser.parse_args([
            "query", 
            "--question", "What is RAG?",
            "--lang", "en",
            "--top-k", "5",
            "--threshold", "0.8"
        ])
        assert args.cmd == "query"
        assert args.question == "What is RAG?"
        assert args.lang == "en"
        assert args.top_k == 5
        assert args.threshold == 0.8
        assert args.func == cmd_query
    
    def test_query_command_defaults(self):
        """Test query command with defaults."""
        parser = _build_parser()
        args = parser.parse_args(["query", "--question", "test"])
        assert args.lang == "fa"
        assert args.top_k is None
        assert args.threshold is None
    
    def test_ingest_file_command(self):
        """Test ingest file command."""
        parser = _build_parser()
        args = parser.parse_args([
            "ingest", 
            "--file", "test.pdf",
            "--type", "pdf"
        ])
        assert args.cmd == "ingest"
        assert args.file == "test.pdf"
        assert args.type == "pdf"
        assert args.url is None
        assert args.text is None
    
    def test_ingest_url_command(self):
        """Test ingest URL command."""
        parser = _build_parser()
        args = parser.parse_args([
            "ingest",
            "--url", "https://example.com"
        ])
        assert args.url == "https://example.com"
        assert args.file is None
        assert args.text is None
    
    def test_ingest_text_command(self):
        """Test ingest text command."""
        parser = _build_parser()
        args = parser.parse_args([
            "ingest",
            "--text", "Some text content"
        ])
        assert args.text == "Some text content"
        assert args.file is None
        assert args.url is None
    
    def test_batch_ingest_command(self):
        """Test batch ingest command."""
        parser = _build_parser()
        args = parser.parse_args([
            "batch-ingest",
            "--dir", "./docs",
            "--pattern", "*.pdf",
            "--pattern", "*.docx",
            "--include-txt",
            "--include-docx",
            "--no-recursive",
            "--type", "pdf",
            "--max-concurrency", "8",
            "file1.pdf", "file2.pdf"
        ])
        assert args.dir == "./docs"
        assert args.pattern == ["*.pdf", "*.docx"]
        assert args.include_txt is True
        assert args.include_docx is True
        assert args.no_recursive is True
        assert args.type == "pdf"
        assert args.max_concurrency == 8
        assert args.sources == ["file1.pdf", "file2.pdf"]


class TestCLICommands:
    """Test CLI command implementations."""
    
    @pytest.mark.asyncio
    async def test_get_rag_service(self, mock_integration_service, mock_rag_service):
        """Test _get_rag_service function."""
        service = await _get_rag_service()
        assert service == mock_rag_service
        mock_integration_service.get_rag_service.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cmd_status(self, mock_integration_service, capsys):
        """Test status command."""
        args = SimpleNamespace()
        result = await cmd_status(args)
        
        assert result == 0
        captured = capsys.readouterr()
        assert "status: healthy" in captured.out
        assert "uptime: 123.45s" in captured.out
        assert "documents: 5" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_reset_success(self, mock_integration_service, capsys):
        """Test reset command success."""
        args = SimpleNamespace()
        result = await cmd_reset(args)
        
        assert result == 0
        captured = capsys.readouterr()
        assert "reset: success" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_reset_failure(self, mock_integration_service, mock_rag_service, capsys):
        """Test reset command failure."""
        mock_rag_service.reset_store.return_value = False
        
        args = SimpleNamespace()
        result = await cmd_reset(args)
        
        assert result == 1
        captured = capsys.readouterr()
        assert "reset: failed" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_query(self, mock_integration_service, capsys):
        """Test query command."""
        args = SimpleNamespace(
            question="What is RAG?",
            lang="en",
            top_k=4,
            threshold=0.7
        )
        result = await cmd_query(args)
        
        assert result == 0
        captured = capsys.readouterr()
        assert "answer:" in captured.out
        assert "Test answer" in captured.out
        assert "sources:" in captured.out
        assert "source1.pdf" in captured.out
        assert "confidence: 0.85" in captured.out
        assert "processing_time: 1.23s" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_ingest_file(self, mock_integration_service, capsys):
        """Test ingest file command."""
        args = SimpleNamespace(
            file="test.pdf",
            url=None,
            text=None,
            type="pdf"
        )
        result = await cmd_ingest(args)
        
        assert result == 0
        captured = capsys.readouterr()
        assert "success: True" in captured.out
        assert "document_id: doc123" in captured.out
        assert "chunks: 3" in captured.out
        assert "processing_time: 2.34s" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_ingest_url(self, mock_integration_service, mock_rag_service):
        """Test ingest URL command."""
        args = SimpleNamespace(
            file=None,
            url="https://example.com",
            text=None,
            type=None
        )
        result = await cmd_ingest(args)
        
        assert result == 0
        mock_rag_service.ingest_document.assert_called_once_with(
            "https://example.com", "url"
        )
    
    @pytest.mark.asyncio
    async def test_cmd_ingest_text(self, mock_integration_service, mock_rag_service):
        """Test ingest text command."""
        args = SimpleNamespace(
            file=None,
            url=None,
            text="Some text",
            type=None
        )
        result = await cmd_ingest(args)
        
        assert result == 0
        mock_rag_service.ingest_document.assert_called_once_with(
            "Some text", "text"
        )
    
    @pytest.mark.asyncio
    async def test_cmd_ingest_pdf_auto_detect(self, mock_integration_service, mock_rag_service):
        """Test ingest with PDF auto-detection."""
        args = SimpleNamespace(
            file="document.pdf",
            url=None,
            text=None,
            type=None
        )
        result = await cmd_ingest(args)
        
        assert result == 0
        mock_rag_service.ingest_document.assert_called_once_with(
            "document.pdf", "pdf"
        )
    
    @pytest.mark.asyncio
    async def test_cmd_ingest_no_source(self, mock_integration_service, capsys):
        """Test ingest with no source provided."""
        args = SimpleNamespace(
            file=None,
            url=None,
            text=None,
            type=None
        )
        result = await cmd_ingest(args)
        
        assert result == 2
        captured = capsys.readouterr()
        assert "Provide one of --file/--url/--text" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_ingest_failure(self, mock_integration_service, mock_rag_service, capsys):
        """Test ingest command failure."""
        # Mock failed ingest
        failed_result = SimpleNamespace(
            success=False,
            document_id="doc123",
            chunks_created=0,
            processing_time=1.0,
            error_message="Processing failed"
        )
        mock_rag_service.ingest_document.return_value = failed_result
        
        args = SimpleNamespace(
            file="test.pdf",
            url=None,
            text=None,
            type="pdf"
        )
        result = await cmd_ingest(args)
        
        assert result == 1
        captured = capsys.readouterr()
        assert "success: False" in captured.out
        assert "error: Processing failed" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_batch_ingest_with_patterns(self, mock_integration_service, mock_rag_service, capsys):
        """Test batch ingest with custom patterns."""
        args = SimpleNamespace(
            pattern=["*.pdf", "*.docx"],
            include_txt=False,
            include_docx=False,
            sources=["file1.pdf"],
            dir="./docs",
            no_recursive=False,
            type=None,
            max_concurrency=4
        )
        result = await cmd_batch_ingest(args)
        
        assert result == 0
        mock_rag_service.batch_ingest.assert_called_once_with(
            sources=["file1.pdf"],
            directory="./docs",
            patterns=["*.pdf", "*.docx"],
            recursive=True,
            source_type=None,
            max_concurrency=4
        )
        
        captured = capsys.readouterr()
        assert "total: 2" in captured.out
        assert "succeeded: 2" in captured.out
        assert "failed: 0" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_batch_ingest_default_patterns(self, mock_integration_service, mock_rag_service):
        """Test batch ingest with default patterns."""
        args = SimpleNamespace(
            pattern=None,
            include_txt=False,
            include_docx=False,
            sources=[],
            dir="./docs",
            no_recursive=False,
            type=None,
            max_concurrency=4
        )
        await cmd_batch_ingest(args)
        
        mock_rag_service.batch_ingest.assert_called_once_with(
            sources=[],
            directory="./docs",
            patterns=["*.pdf"],
            recursive=True,
            source_type=None,
            max_concurrency=4
        )
    
    @pytest.mark.asyncio
    async def test_cmd_batch_ingest_include_flags(self, mock_integration_service, mock_rag_service):
        """Test batch ingest with include flags."""
        args = SimpleNamespace(
            pattern=None,
            include_txt=True,
            include_docx=True,
            sources=[],
            dir="./docs",
            no_recursive=True,
            type="pdf",
            max_concurrency=8
        )
        await cmd_batch_ingest(args)
        
        mock_rag_service.batch_ingest.assert_called_once_with(
            sources=[],
            directory="./docs",
            patterns=["*.pdf", "*.txt", "*.docx"],
            recursive=False,
            source_type="pdf",
            max_concurrency=8
        )
    
    @pytest.mark.asyncio
    async def test_cmd_batch_ingest_with_failures(self, mock_integration_service, mock_rag_service, capsys):
        """Test batch ingest with some failures."""
        # Mock batch result with failures
        batch_result = {
            "total": 2,
            "succeeded": 1,
            "failed": 1,
            "duration": 3.45,
            "results": [
                {"success": True, "document_id": "doc1", "source": "file1.pdf"},
                {"success": False, "document_id": "doc2", "source": "file2.pdf"}
            ]
        }
        mock_rag_service.batch_ingest.return_value = batch_result
        
        args = SimpleNamespace(
            pattern=None,
            include_txt=False,
            include_docx=False,
            sources=[],
            dir="./docs",
            no_recursive=False,
            type=None,
            max_concurrency=4
        )
        result = await cmd_batch_ingest(args)
        
        assert result == 1  # Should return 1 when there are failures
        captured = capsys.readouterr()
        assert "failed: 1" in captured.out
    
    @pytest.mark.asyncio
    async def test_cmd_batch_ingest_many_results(self, mock_integration_service, mock_rag_service, capsys):
        """Test batch ingest with many results (truncation)."""
        # Create 15 results to test truncation at 10
        results = []
        for i in range(15):
            results.append({
                "success": True,
                "document_id": f"doc{i}",
                "source": f"file{i}.pdf"
            })
        
        batch_result = {
            "total": 15,
            "succeeded": 15,
            "failed": 0,
            "duration": 10.0,
            "results": results
        }
        mock_rag_service.batch_ingest.return_value = batch_result
        
        args = SimpleNamespace(
            pattern=None,
            include_txt=False,
            include_docx=False,
            sources=[],
            dir="./docs",
            no_recursive=False,
            type=None,
            max_concurrency=4
        )
        result = await cmd_batch_ingest(args)
        
        assert result == 0
        captured = capsys.readouterr()
        assert "total: 15" in captured.out
        assert "... (showing first 10)" in captured.out


class TestCLIMain:
    """Test CLI main function."""
    
    def test_main_keyboard_interrupt(self):
        """Test main function with keyboard interrupt."""
        with patch("ragbot.cli._build_parser") as mock_parser:
            with patch("ragbot.cli.asyncio.run") as mock_run:
                # Mock parser and args
                parser = MagicMock()
                args = MagicMock()
                args.func = AsyncMock(side_effect=KeyboardInterrupt())
                parser.parse_args.return_value = args
                mock_parser.return_value = parser
                mock_run.side_effect = KeyboardInterrupt()
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 130
    
    def test_main_exception(self):
        """Test main function with exception."""
        with patch("ragbot.cli._build_parser") as mock_parser:
            with patch("ragbot.cli.asyncio.run") as mock_run:
                # Mock parser and args
                parser = MagicMock()
                args = MagicMock()
                args.func = AsyncMock(side_effect=Exception("Test error"))
                parser.parse_args.return_value = args
                mock_parser.return_value = parser
                mock_run.side_effect = Exception("Test error")
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 1
    
    def test_main_success(self):
        """Test main function success."""
        with patch("ragbot.cli._build_parser") as mock_parser:
            with patch("ragbot.cli.asyncio.run") as mock_run:
                # Mock parser and args
                parser = MagicMock()
                args = MagicMock()
                args.func = AsyncMock(return_value=0)
                parser.parse_args.return_value = args
                mock_parser.return_value = parser
                mock_run.return_value = 0
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0


class TestCLIPerformance:
    """Tests for CLI performance commands."""

    @pytest.mark.asyncio
    async def test_cmd_performance_success(self):
        mock_integration = Mock()
        mock_integration.get_performance_summary = AsyncMock(
            return_value={
                "average_response_time": 0.5,
                "total_requests": 100,
                "error_rate": 0.05,
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "active_connections": 12,
            }
        )
        mock_integration.get_resource_summary = AsyncMock(
            return_value={
                "current": {
                    "cpu_percent": 45.2,
                    "memory_percent": 67.8,
                    "disk_usage": 23.4,
                    "process_count": 156,
                },
                "averages": {"cpu_percent": 42.1, "memory_percent": 65.3},
                "alerts": [
                    {
                        "severity": "warning",
                        "message": "CPU usage is approaching threshold: 78.5%",
                        "timestamp": 1234567890,
                    }
                ],
                "alert_thresholds": {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
            }
        )

        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            result = await cmd_performance(Mock())
            assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_performance_no_data(self):
        mock_integration = Mock()
        mock_integration.get_performance_summary = AsyncMock(
            return_value={"no_data": True}
        )
        mock_integration.get_resource_summary = AsyncMock(
            return_value={"no_data": True}
        )

        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            result = await cmd_performance(Mock())
            assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_performance_performance_error(self):
        mock_integration = Mock()
        mock_integration.get_performance_summary = AsyncMock(
            return_value={"error": "Performance monitoring failed"}
        )
        mock_integration.get_resource_summary = AsyncMock(
            return_value={
                "current": {
                    "cpu_percent": 45.2,
                    "memory_percent": 67.8,
                    "disk_usage": 23.4,
                    "process_count": 156,
                },
                "averages": {"cpu_percent": 42.1, "memory_percent": 65.3},
                "alerts": [],
                "alert_thresholds": {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
            }
        )

        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            result = await cmd_performance(Mock())
            assert result == 1

    @pytest.mark.asyncio
    async def test_cmd_performance_resource_error(self):
        mock_integration = Mock()
        mock_integration.get_performance_summary = AsyncMock(
            return_value={
                "average_response_time": 0.5,
                "total_requests": 100,
                "error_rate": 0.05,
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "active_connections": 12,
            }
        )
        mock_integration.get_resource_summary = AsyncMock(
            return_value={"error": "Resource monitoring failed"}
        )

        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            result = await cmd_performance(Mock())
            assert result == 1

    @pytest.mark.asyncio
    async def test_cmd_performance_with_alerts(self):
        mock_integration = Mock()
        mock_integration.get_performance_summary = AsyncMock(
            return_value={
                "average_response_time": 0.5,
                "total_requests": 100,
                "error_rate": 0.05,
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "active_connections": 12,
            }
        )
        mock_integration.get_resource_summary = AsyncMock(
            return_value={
                "current": {
                    "cpu_percent": 85.2,
                    "memory_percent": 90.8,
                    "disk_usage": 95.4,
                    "process_count": 256,
                },
                "averages": {"cpu_percent": 82.1, "memory_percent": 88.3},
                "alerts": [
                    {
                        "severity": "critical",
                        "message": "Memory usage is high: 90.8%",
                        "timestamp": 1234567890,
                    },
                    {
                        "severity": "warning",
                        "message": "CPU usage is high: 85.2%",
                        "timestamp": 1234567891,
                    },
                ],
                "alert_thresholds": {"cpu": 80.0, "memory": 85.0, "disk": 90.0},
            }
        )

        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            result = await cmd_performance(Mock())
            assert result == 0

    @pytest.mark.asyncio
    async def test_cmd_performance_exception_handling(self):
        mock_integration = Mock()
        mock_integration.get_performance_summary = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        with patch("ragbot.cli.get_integration_service", return_value=mock_integration):
            result = await cmd_performance(Mock())
            assert result == 1


class TestCLIPerformanceIntegration:
    """Integration tests for CLI performance command."""

    @pytest.mark.asyncio
    async def test_cli_performance_command_exists(self):
        parser = _build_parser()
        args = parser.parse_args(["performance"])
        assert args.cmd == "performance"
        assert args.func == cmd_performance

    @pytest.mark.asyncio
    async def test_cli_performance_help(self):
        parser = _build_parser()
        help_text = parser.format_help()
        assert "performance" in help_text

    @pytest.mark.asyncio
    async def test_cli_performance_with_real_integration(self):
        parser = _build_parser()
        args = parser.parse_args(["performance"])
        assert args.func == cmd_performance
        assert callable(args.func)

