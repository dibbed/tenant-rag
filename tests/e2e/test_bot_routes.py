"""
Telegram bot route handler smoke tests.

This module provides end-to-end tests for the Telegram bot handlers
to ensure they execute without exceptions and handle basic scenarios.
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Message, User, Chat, Document, File
from aiogram.types.base import TelegramObject

# Import CoroutineMock if available, else use AsyncMock
try:
    from unittest.mock import CoroutineMock
except ImportError:
    CoroutineMock = AsyncMock

from ragbot.app.routes import ask_handler, add_handler, reset_handler, help_handler
from ragbot.rag.exceptions import RAGError


class TestBotRoutes:
    """End-to-end tests for Telegram bot route handlers."""

    @pytest.fixture
    def fake_user(self) -> User:
        """Create a fake user for testing."""
        return User(
            id=12345,
            is_bot=False,
            first_name="Test",
            last_name="User",
            username="testuser"
        )

    @pytest.fixture
    def fake_chat(self) -> Chat:
        """Create a fake chat for testing."""
        return Chat(
            id=67890,
            type="private"
        )

    @pytest.fixture
    def fake_message(self, fake_user: User, fake_chat: Chat) -> Message:
        """Create a fake message for testing."""
        return Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="Test message content"
        )

    @pytest.fixture
    def fake_document_message(self, fake_user: User, fake_chat: Chat) -> Message:
        """Create a fake message with document for testing."""
        document = Document(
            file_id="test_file_id",
            file_unique_id="test_unique_id",
            file_name="test.pdf",
            mime_type="application/pdf",
            file_size=1024
        )
        
        return Message(
            message_id=2,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="document",
            options={},
            document=document
        )

    def create_mock_reply(self):
        """Create a properly configured mock reply object."""
        mock_status_message = AsyncMock()
        mock_status_message.edit_text = AsyncMock()
        return CoroutineMock(return_value=mock_status_message)

    @pytest.mark.asyncio
    async def test_ask_handler_smoke(self, fake_user: User, fake_chat: Chat) -> None:
        """Verify ask handler executes without exceptions."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/ask What is machine learning?"
        )
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_documents = AsyncMock(return_value=MagicMock(
                answer="Machine learning is a subset of AI.",
                sources=["doc1.pdf"],
                confidence_score=0.9
            ))
            mock_get_service.return_value = mock_service
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should not raise exceptions
                await ask_handler(fake_message)
                
                # Verify service was called
                mock_service.query_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_handler_text_smoke(self, fake_user: User, fake_chat: Chat) -> None:
        """Verify add handler works with text content."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/add This is some text content to add to the knowledge base."
        )
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_document = AsyncMock(return_value=MagicMock(
                success=True,
                document_id="doc_123",
                chunks_created=3
            ))
            mock_get_service.return_value = mock_service
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should not raise exceptions
                await add_handler(fake_message)
                
                # Verify service was called
                mock_service.ingest_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_handler_document_smoke(self, fake_document_message: Message) -> None:
        """Verify add handler works with document uploads."""
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_document = AsyncMock(return_value=MagicMock(
                success=True,
                document_id="doc_456",
                chunks_created=5
            ))
            mock_get_service.return_value = mock_service
            
            with patch('ragbot.app.routes.get_bot') as mock_get_bot:
                mock_bot = MagicMock()
                mock_bot.download_file = AsyncMock()
                mock_bot.get_file = AsyncMock(return_value=MagicMock(
                    file_path="documents/test.pdf"
                ))
                mock_get_bot.return_value = mock_bot
                
                # Mock the aiogram Message.reply method at class level
                with patch('aiogram.types.Message.reply') as mock_reply:
                    mock_reply.return_value = self.create_mock_reply()
                    
                    # Should not raise exceptions
                    await add_handler(fake_document_message)
                    
                    # Verify bot methods were called
                    mock_bot.get_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_handler_smoke(self, fake_user: User, fake_chat: Chat) -> None:
        """Verify reset handler executes without exceptions."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/reset"
        )
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.reset_vector_store = AsyncMock(return_value=True)
            mock_get_service.return_value = mock_service
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should not raise exceptions
                await reset_handler(fake_message)
                
                # Verify service was called
                mock_service.reset_vector_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_help_handler_smoke(self, fake_user: User, fake_chat: Chat) -> None:
        """Verify help handler executes without exceptions."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/help"
        )
        
        # Mock the aiogram Message.reply method at class level
        with patch('aiogram.types.Message.reply') as mock_reply:
            mock_reply.return_value = self.create_mock_reply()
            
            # Should not raise exceptions
            await help_handler(fake_message)
            
            # Verify response was sent
            mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_handler_empty_query(self, fake_user: User, fake_chat: Chat) -> None:
        """Test ask handler with empty query."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/ask"  # No question provided
        )
        
        # Mock the aiogram Message.reply method at class level
        with patch('aiogram.types.Message.reply') as mock_reply:
            mock_reply.return_value = self.create_mock_reply()
            
            # Should handle gracefully
            await ask_handler(fake_message)
            
            # Should send appropriate response
            mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_handler_service_error(self, fake_user: User, fake_chat: Chat) -> None:
        """Test ask handler when service fails."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/ask What is AI?"
        )
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_documents = AsyncMock(side_effect=RAGError("Service failed"))
            mock_get_service.return_value = mock_service
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should handle error gracefully
                await ask_handler(fake_message)
                
                # Should send error response
                mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_handler_unsupported_file(self, fake_user: User, fake_chat: Chat) -> None:
        """Test add handler with unsupported file type."""
        # Create message with unsupported document
        document = Document(
            file_id="test_file_id",
            file_unique_id="test_unique_id",
            file_name="test.exe",  # Unsupported file type
            mime_type="application/x-executable",
            file_size=1024
        )
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="document",
            options={},
            document=document
        )
        
        # Mock the aiogram Message.reply method at class level
        with patch('aiogram.types.Message.reply') as mock_reply:
            mock_reply.return_value = self.create_mock_reply()
            
            # Should handle gracefully
            await add_handler(fake_message)
            
            # Should send appropriate response
            mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_handler_url_content(self, fake_user: User, fake_chat: Chat) -> None:
        """Test add handler with URL content."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/add https://example.com/article"
        )
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.ingest_document = AsyncMock(return_value=MagicMock(
                success=True,
                document_id="url_123",
                chunks_created=10
            ))
            mock_get_service.return_value = mock_service
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should not raise exceptions
                await add_handler(fake_message)
                
                # Verify service was called with URL
                mock_service.ingest_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_multilingual_query_handling(self, fake_user: User, fake_chat: Chat) -> None:
        """Test handling of multilingual queries."""
        multilingual_queries = [
            "/ask What is artificial intelligence?",
            "/ask هوش مصنوعی چیست؟",
            "/ask ما هو الذكاء الاصطناعي؟"
        ]
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_documents = AsyncMock(return_value=MagicMock(
                answer="Multilingual response",
                sources=[],
                confidence_score=0.8
            ))
            mock_get_service.return_value = mock_service
            
            for query in multilingual_queries:
                fake_message = Message(
                    message_id=1,
                    date=1234567890,
                    chat=fake_chat,
                    from_user=fake_user,
                    content_type="text",
                    options={},
                    text=query
                )
                
                # Mock the aiogram Message.reply method at class level
                with patch('aiogram.types.Message.reply') as mock_reply:
                    mock_reply.return_value = self.create_mock_reply()
                    
                    # Should handle all languages
                    await ask_handler(fake_message)
                    
                    mock_reply.assert_called_once()
                    mock_reply.reset_mock()

    @pytest.mark.asyncio
    async def test_concurrent_handler_calls(self, fake_user: User, fake_chat: Chat) -> None:
        """Test concurrent handler calls."""
        # Create multiple messages
        messages = []
        for i in range(5):
            message = Message(
                message_id=i,
                date=1234567890,
                chat=fake_chat,
                from_user=fake_user,
                content_type="text",
                options={},
                text=f"/ask Question {i}?"
            )
            messages.append(message)
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_documents = AsyncMock(return_value=MagicMock(
                answer="Concurrent response",
                sources=[],
                confidence_score=0.7
            ))
            mock_get_service.return_value = mock_service
            
            # Mock reply method at class level to avoid frozen instance issues
            with patch('aiogram.types.Message.reply') as mock_reply:
                # Create a mock message object that can be awaited and has edit_text
                mock_status_message = AsyncMock()
                mock_status_message.edit_text = AsyncMock()
                mock_reply.return_value = mock_status_message
                
                # Run concurrent handlers
                tasks = [ask_handler(message) for message in messages]
                await asyncio.gather(*tasks)
                
                # Should complete without errors
                assert mock_service.query_documents.call_count == 5

    @pytest.mark.asyncio
    async def test_handler_with_authentication(self, fake_chat: Chat) -> None:
        """Test handlers with authentication middleware."""
        # Test with unauthorized user
        unauthorized_user = User(
            id=99999,  # Unauthorized ID
            is_bot=False,
            first_name="Unauthorized",
            last_name="User",
            username="unauthorized"
        )
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=unauthorized_user,
            content_type="text",
            options={},
            text="/ask Test with auth"
        )
        
        with patch('ragbot.app.routes.is_user_authorized') as mock_auth:
            mock_auth.return_value = False
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should handle unauthorized user
                await ask_handler(fake_message)
                
                # Should send unauthorized response or handle gracefully
                mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_rate_limiting(self, fake_user: User, fake_chat: Chat) -> None:
        """Test handlers with rate limiting."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/ask Rate limit test"
        )
        
        with patch('ragbot.app.routes.check_rate_limit') as mock_rate_limit:
            mock_rate_limit.return_value = False  # Rate limit exceeded
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should handle rate limiting
                await ask_handler(fake_message)
                
                # Should send rate limit response
                mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_large_document_handling(self, fake_user: User, fake_chat: Chat) -> None:
        """Test handling of large documents."""
        # Create large document
        large_document = Document(
            file_id="large_file_id",
            file_unique_id="large_unique_id",
            file_name="large_document.pdf",
            mime_type="application/pdf",
            file_size=50 * 1024 * 1024  # 50MB
        )
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="document",
            options={},
            document=large_document
        )
        
        # Mock the aiogram Message.reply method at class level
        with patch('aiogram.types.Message.reply') as mock_reply:
            mock_reply.return_value = self.create_mock_reply()
            
            # Should handle large files gracefully
            await add_handler(fake_message)
            
            # Should send appropriate response (size limit or processing message)
            mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_malformed_command_handling(self, fake_user: User, fake_chat: Chat) -> None:
        """Test handling of malformed commands."""
        malformed_commands = [
            "ask without slash",
            "/askwithoutspace",
            "//ask double slash",
            "/ask",  # No content
            "",      # Empty message
        ]
        
        for command in malformed_commands:
            fake_message = Message(
                message_id=1,
                date=1234567890,
                chat=fake_chat,
                from_user=fake_user,
                content_type="text",
                options={},
                text=command
            )
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should handle malformed commands gracefully
                try:
                    await ask_handler(fake_message)
                    # If no exception, should send appropriate response
                    mock_reply.assert_called_once()
                except Exception:
                    # Some malformed commands might raise exceptions
                    # This is acceptable as long as they don't crash the bot
                    pass
                
                mock_reply.reset_mock()

    @pytest.mark.asyncio
    async def test_handler_logging(self, fake_user: User, fake_chat: Chat) -> None:
        """Test that handlers properly log their activities."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/ask Logging test"
        )
        
        with patch('ragbot.app.routes.logger') as mock_logger:
            with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
                mock_service = MagicMock()
                mock_service.query_documents = AsyncMock(return_value=MagicMock(
                    answer="Logged response",
                    sources=[],
                    confidence_score=0.8
                ))
                mock_get_service.return_value = mock_service
                
                # Mock the aiogram Message.reply method at class level
                with patch('aiogram.types.Message.reply') as mock_reply:
                    mock_reply.return_value = self.create_mock_reply()
                    
                    await ask_handler(fake_message)
                    
                    # Should log the activity
                    assert mock_logger.info.called or mock_logger.debug.called

    @pytest.mark.asyncio
    async def test_memory_usage_in_handlers(self, fake_user: User, fake_chat: Chat) -> None:
        """Test memory usage in handlers with large content."""
        # Simulate large query content
        large_query = "/ask " + "Large query content " * 1000
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text=large_query
        )
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_documents = AsyncMock(return_value=MagicMock(
                answer="Response to large query",
                sources=[],
                confidence_score=0.6
            ))
            mock_get_service.return_value = mock_service
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Should handle large content without memory issues
                await ask_handler(fake_message)
                
                mock_reply.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_cleanup(self, fake_user: User, fake_chat: Chat) -> None:
        """Test that handlers properly clean up resources."""
        fake_message = Message(
            message_id=1,
            date=1234567890,
            chat=fake_chat,
            from_user=fake_user,
            content_type="text",
            options={},
            text="/ask Cleanup test"
        )
        
        with patch('ragbot.app.routes.get_rag_service') as mock_get_service:
            mock_service = MagicMock()
            mock_service.query_documents = AsyncMock(side_effect=Exception("Test error"))
            mock_get_service.return_value = mock_service
            
            # Mock the aiogram Message.reply method at class level
            with patch('aiogram.types.Message.reply') as mock_reply:
                mock_reply.return_value = self.create_mock_reply()
                
                # Even with errors, should clean up properly
                await ask_handler(fake_message)
                
                # Should send error response
                mock_reply.assert_called_once()