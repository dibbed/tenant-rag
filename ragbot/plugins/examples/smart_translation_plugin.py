"""
Smart Translation Plugin

This plugin provides intelligent translation capabilities between Persian and English,
with context-aware translation and multilingual support.
"""

from typing import Dict, Any, Optional, List
import asyncio
import json
from datetime import datetime

from ragbot.plugins.base_plugin import (
    BasePlugin,
    PluginContext,
    PluginResult,
    PluginType,
    PluginStatus,
    HookType,
)
from ragbot.outputs.logger import logger

try:
    from googletrans import Translator

    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    logger.warning("googletrans not found. Translation features limited.")


class SmartTranslationPlugin(BasePlugin):
    """
    Smart Translation Plugin for multilingual support

    Provides:
    - Automatic language detection
    - Context-aware translation
    - Query translation for better results
    - Response translation
    - Translation caching
    """

    def __init__(self, plugin_id: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(plugin_id, config)

        # Default configuration
        self.default_config = {
            "source_languages": ["fa", "en", "ar", "tr"],  # Supported languages
            "target_language": "en",  # Default target for responses
            "auto_detect": True,  # Automatic language detection
            "cache_translations": True,  # Cache translation results
            "confidence_threshold": 0.7,  # Minimum confidence for auto-translation
            "preserve_formatting": True,  # Preserve markdown formatting
            "translate_queries": True,  # Translate user queries
            "translate_responses": True,  # Translate bot responses
        }

        # Merge with provided config
        self.config.update(self.default_config)

        # Translation cache
        self.translation_cache: Dict[str, str] = {}

        # Initialize translator if available
        self.translator = None
        if TRANSLATION_AVAILABLE:
            try:
                self.translator = Translator()
                logger.info("Google Translator initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Google Translator: {e}")

    @property
    def plugin_name(self) -> str:
        return "Smart Translation Plugin"

    @property
    def plugin_version(self) -> str:
        return "1.0.0"

    @property
    def plugin_description(self) -> str:
        return (
            "Intelligent translation plugin with automatic language detection, "
            "context-aware translation, and multilingual query support"
        )

    @property
    def plugin_type(self) -> PluginType:
        return PluginType.INTEGRATION_PLUGIN

    @property
    def plugin_author(self) -> str:
        return "RAG Bot Translation Team"

    async def initialize(self, context: PluginContext) -> bool:
        """Initialize the plugin"""
        try:
            logger.info("Initializing Smart Translation Plugin...")

            # Test translator if available
            if self.translator:
                try:
                    test_result = await self._translate_text("سلام دنیا", "fa", "en")
                    if test_result:
                        logger.info("Translation test successful")
                    else:
                        logger.warning("Translation test failed")
                except Exception as e:
                    logger.error(f"Translation test error: {e}")
                    return False

            # Register hooks for automatic translation
            self.register_hook(HookType.PRE_QUERY, self._translate_user_query)
            self.register_hook(HookType.POST_RESPONSE, self._translate_bot_response)
            self.register_hook(
                HookType.PRE_DOCUMENT_INGEST, self._translate_document_content
            )

            logger.info("Smart Translation Plugin initialized successfully")
            self.set_status(PluginStatus.ACTIVE)
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Smart Translation Plugin: {e}")
            self.set_status(PluginStatus.ERROR)
            return False

    async def execute(self, context: PluginContext) -> PluginResult:
        """Execute main translation functionality"""
        try:
            start_time = asyncio.get_event_loop().time()

            # Get text and target language from context
            text = context.data.get("text", "") if context.data else ""
            target_lang = (
                context.data.get("target_language", self.config["target_language"])
                if context.data
                else self.config["target_language"]
            )
            source_lang = (
                context.data.get("source_language", None) if context.data else None
            )

            if not text:
                return PluginResult(
                    success=False, error_message="No text provided for translation"
                )

            # Translate text
            translated_text = await self._translate_text(text, source_lang, target_lang)

            if translated_text:
                execution_time = asyncio.get_event_loop().time() - start_time

                return PluginResult(
                    success=True,
                    data={
                        "original_text": text,
                        "translated_text": translated_text,
                        "source_language": source_lang,
                        "target_language": target_lang,
                        "translation_time": execution_time,
                        "cached": text in self.translation_cache,
                    },
                    metadata={
                        "plugin_id": self.plugin_id,
                        "execution_time": execution_time,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            else:
                return PluginResult(success=False, error_message="Translation failed")

        except Exception as e:
            logger.error(f"Translation execution error: {e}")
            return PluginResult(
                success=False, error_message=f"Translation execution error: {str(e)}"
            )

    async def cleanup(self) -> bool:
        """Cleanup plugin resources"""
        try:
            logger.info("Cleaning up Smart Translation Plugin...")

            # Clear translation cache if not persisting
            if not self.config.get("cache_translations", True):
                self.translation_cache.clear()

            logger.info("Smart Translation Plugin cleanup completed")
            return True

        except Exception as e:
            logger.error(f"Plugin cleanup error: {e}")
            return False

    async def translate_query(self, context: PluginContext) -> PluginResult:
        """Translate user query for better search results"""
        try:
            if not self.config.get("translate_queries", True):
                return PluginResult(success=True, data={"translated": False})

            query = context.data.get("query", "") if context.data else ""
            if not query:
                return PluginResult(success=False, error_message="No query provided")

            # Detect language and translate to English if needed
            detected_lang = await self._detect_language(query)

            if detected_lang and detected_lang != "en":
                translated_query = await self._translate_text(
                    query, detected_lang, "en"
                )
                return PluginResult(
                    success=True,
                    data={
                        "original_query": query,
                        "translated_query": translated_query,
                        "detected_language": detected_lang,
                        "translation_applied": True,
                    },
                )
            else:
                return PluginResult(
                    success=True,
                    data={
                        "original_query": query,
                        "translated_query": query,
                        "detected_language": detected_lang,
                        "translation_applied": False,
                    },
                )

        except Exception as e:
            logger.error(f"Query translation error: {e}")
            return PluginResult(
                success=False, error_message=f"Query translation error: {str(e)}"
            )

    async def translate_response(self, context: PluginContext) -> PluginResult:
        """Translate bot response to user's preferred language"""
        try:
            if not self.config.get("translate_responses", True):
                return PluginResult(success=True, data={"translated": False})

            response = context.data.get("response", "") if context.data else ""
            target_lang = (
                context.data.get("user_language", self.config["target_language"])
                if context.data
                else self.config["target_language"]
            )

            if not response:
                return PluginResult(success=False, error_message="No response provided")

            # Translate response to user's language
            translated_response = await self._translate_text(
                response, "en", target_lang
            )

            if translated_response:
                return PluginResult(
                    success=True,
                    data={
                        "original_response": response,
                        "translated_response": translated_response,
                        "target_language": target_lang,
                        "translation_applied": True,
                    },
                )
            else:
                return PluginResult(success=True, data={"translation_applied": False})

        except Exception as e:
            logger.error(f"Response translation error: {e}")
            return PluginResult(
                success=False, error_message=f"Response translation error: {str(e)}"
            )

    async def _translate_text(
        self, text: str, source_lang: Optional[str], target_lang: str
    ) -> Optional[str]:
        """Internal method to translate text"""
        try:
            if not self.translator:
                logger.warning("Translator not available")
                return None

            # Check cache first
            cache_key = f"{text}_{source_lang}_{target_lang}"
            if cache_key in self.translation_cache:
                logger.debug("Translation cache hit")
                return self.translation_cache[cache_key]

            # Perform translation
            result = self.translator.translate(text, dest=target_lang, src=source_lang)

            if result and result.text:
                translated_text = result.text

                # Cache the result
                if self.config.get("cache_translations", True):
                    self.translation_cache[cache_key] = translated_text

                logger.debug(f"Translated: '{text}' -> '{translated_text}'")
                return translated_text
            else:
                logger.warning(f"Translation failed for text: {text}")
                return None

        except Exception as e:
            logger.error(f"Translation error: {e}")
            return None

    async def _detect_language(self, text: str) -> Optional[str]:
        """Detect language of text"""
        try:
            if not self.translator:
                return None

            result = self.translator.detect(text)

            if (
                result
                and hasattr(result, "confidence")
                and result.confidence >= self.config.get("confidence_threshold", 0.7)
            ):
                logger.debug(
                    f"Detected language: {result.lang} (confidence: {result.confidence})"
                )
                return result.lang
            else:
                logger.warning(
                    f"Language detection confidence too low: {getattr(result, 'confidence', 0)}"
                )
                return None

        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return None

    async def _translate_user_query(self, context: PluginContext) -> List[PluginResult]:
        """Hook: Translate user query before processing"""
        return [await self.translate_query(context)]

    async def _translate_bot_response(
        self, context: PluginContext
    ) -> List[PluginResult]:
        """Hook: Translate bot response before sending"""
        return [await self.translate_response(context)]

    async def _translate_document_content(
        self, context: PluginContext
    ) -> List[PluginResult]:
        """Hook: Translate document content during ingestion"""
        try:
            if not self.config.get("auto_detect", True):
                return [PluginResult(success=True)]

            content = context.data.get("content", "") if context.data else ""
            if not content:
                return [PluginResult(success=True)]

            # Simple implementation - could be enhanced
            detected_lang = await self._detect_language(
                content[:500]
            )  # Sample for detection

            return [
                PluginResult(
                    success=True,
                    data={
                        "document_language": detected_lang,
                        "content_length": len(content),
                    },
                )
            ]

        except Exception as e:
            logger.error(f"Document translation hook error: {e}")
            return [PluginResult(success=False, error_message=str(e))]

    def get_translation_stats(self) -> Dict[str, Any]:
        """Get translation statistics"""
        return {
            "cache_size": len(self.translation_cache),
            "supported_languages": self.config["source_languages"],
            "default_target": self.config["target_language"],
            "translator_available": self.translator is not None,
            "auto_detect_enabled": self.config["auto_detect"],
            "cache_enabled": self.config["cache_translations"],
        }
