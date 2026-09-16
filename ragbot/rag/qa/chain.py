"""
Question-Answering chain with RAG context for generating grounded answers.

This module provides comprehensive QA functionality with context retrieval,
prompt building, and LLM integration for generating accurate answers.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from openai import AsyncOpenAI, OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import importlib.util

    INSTRUCTOR_AVAILABLE = importlib.util.find_spec("instructor") is not None
except ImportError:
    INSTRUCTOR_AVAILABLE = False

try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.outputs.metrics import metrics_manager, quality_evaluator
from ragbot.rag.exceptions import LLMError
from ragbot.rag.qa.prompting import PromptBuilder
from ragbot.rag.retrieve.retriever import DocumentRetriever
from ragbot.rag.store.base import VectorDocument
from ragbot.utils.debug_helpers import log_pydantic_error


class QAChain:
    """
    Question-Answering chain with RAG context.

    This class orchestrates the complete QA pipeline including document
    retrieval, context building, prompt generation, and answer synthesis.
    """

    def __init__(
        self,
        retriever: Optional[DocumentRetriever] = None,
        llm_provider: str = "openai",
        **kwargs: Any,
    ) -> None:
        """
        Initialize QA chain.

        Args:
            retriever: Document retriever for context (optional)
            llm_provider: LLM provider ("openai", "anthropic", etc.)
            **kwargs: Configuration options including:
                - model_name: LLM model name
                - max_tokens: Maximum tokens in response
                - temperature: LLM temperature
                - api_key: API key override
        """
        self.retriever = retriever
        self.llm_provider = llm_provider

        # LLM configuration
        self.model_name = kwargs.get("model_name", settings.llm.model)
        self.max_tokens = kwargs.get("max_tokens", settings.llm.max_tokens)
        self.temperature = kwargs.get("temperature", settings.llm.temperature)
        self.api_key = kwargs.get("api_key")

        # Initialize prompt builder
        self.prompt_builder = PromptBuilder()

        # Initialize LLM client
        self._initialize_llm_client()

        # Cache for HuggingFace pipeline to prevent memory leaks
        self._hf_pipeline = None
        self._hf_pipeline_lock = asyncio.Lock()

        logger.info(
            "QA chain initialized",
            llm_provider=self.llm_provider,
            model_name=self.model_name,
            max_tokens=self.max_tokens,
        )

    async def _get_hf_pipeline(self):
        """Get or create HuggingFace pipeline with caching."""
        async with self._hf_pipeline_lock:
            if self._hf_pipeline is None:
                try:
                    from transformers import pipeline

                    model_id = getattr(self, "hf_model", None) or self.model_name
                    device = getattr(self, "hf_device", "auto")

                    logger.info(
                        f"Initializing HuggingFace pipeline for model: {model_id}"
                    )

                    self._hf_pipeline = pipeline(
                        task="text-generation",
                        model=model_id,
                        device_map=device,
                        trust_remote_code=True,
                    )

                    logger.info("HuggingFace pipeline initialized successfully")
                except Exception as e:
                    logger.error(f"Failed to initialize HuggingFace pipeline: {e}")
                    raise LLMError(
                        f"Failed to initialize HuggingFace pipeline: {str(e)}",
                        provider="hf_local",
                        model=self.model_name,
                        details=str(e),
                    ) from e

            return self._hf_pipeline

    async def cleanup(self):
        """Cleanup resources."""
        try:
            # Cleanup HuggingFace pipeline
            if self._hf_pipeline is not None:
                del self._hf_pipeline
                self._hf_pipeline = None
                logger.info("HuggingFace pipeline cleaned up")

            # Cleanup OpenAI clients
            if hasattr(self, "async_client") and self.async_client:
                try:
                    await self.async_client.close()
                    logger.info("OpenAI async client closed")
                except Exception as e:
                    logger.warning(f"Error closing async client: {e}")

            if hasattr(self, "sync_client") and self.sync_client:
                try:
                    self.sync_client.close()
                    logger.info("OpenAI sync client closed")
                except Exception as e:
                    logger.warning(f"Error closing sync client: {e}")

        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    def _initialize_llm_client(self) -> None:
        """Initialize the LLM client based on provider."""
        if self.llm_provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "openai is required for OpenAI provider. Install with: pip install openai"
                )

            api_key = self.api_key or settings.openai_api_key
            if not api_key:
                raise LLMError(
                    "OpenAI API key is required",
                    provider="openai",
                    model=self.model_name,
                )

            self.async_client = AsyncOpenAI(api_key=api_key)
            self.sync_client = OpenAI(api_key=api_key)
        elif self.llm_provider == "openrouter":
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "openai client is required for OpenRouter provider. Install with: pip install openai"
                )
            base_url = settings.llm.base_url or "https://openrouter.ai/api/v1"
            api_key = (
                settings.openrouter_api_key or self.api_key or settings.openai_api_key
            )
            if not api_key:
                raise LLMError("OpenRouter API key is required", provider="openrouter")
            self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            self.sync_client = OpenAI(api_key=api_key, base_url=base_url)
        elif self.llm_provider == "ollama":
            if not OLLAMA_AVAILABLE:
                raise ImportError(
                    "ollama is required for Ollama provider. Install with: pip install ollama"
                )
            # Ollama client will be initialized when needed
            self.ollama_base_url = settings.llm.base_url or "http://localhost:11434"
        elif self.llm_provider == "hf_local":
            # Lazy-load transformers in generation method
            self.hf_model = settings.llm.hf_model or self.model_name
            self.hf_device = settings.llm.hf_device or "auto"
        else:
            raise LLMError(
                f"Unsupported LLM provider: {self.llm_provider}",
                provider=self.llm_provider,
            )

    async def answer(
        self,
        question: str,
        language: str = "en",
        context_docs: Optional[List[VectorDocument]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate an answer to a question using RAG context.

        Args:
            question: User question
            language: Response language ("en", "fa")
            context_docs: Pre-retrieved context documents (optional)
            **kwargs: Additional options

        Returns:
            Dict[str, Any]: Answer response with metadata

        Raises:
            LLMError: If answer generation fails
        """
        try:
            start_time = time.time()

            # Retrieve context documents if not provided
            if context_docs is None and self.retriever is not None:
                context_docs = await self.retriever.retrieve(
                    question, top_k=kwargs.get("top_k"), filters=kwargs.get("filters")
                )
            elif context_docs is None:
                # No retriever available, use empty context
                context_docs = []

            # Clamp context by token budget (best-effort) when used stand-alone
            try:
                max_ctx_tokens = int(
                    getattr(getattr(settings, "rag", object()), "max_context_tokens", 0)
                )
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(f"Failed to get max_context_tokens from settings: {e}")
                max_ctx_tokens = 0

            if max_ctx_tokens and context_docs:
                try:
                    import tiktoken as _tk  # type: ignore

                    enc = None
                    try:
                        enc = _tk.get_encoding("cl100k_base")
                        logger.debug("Successfully initialized tiktoken encoder")
                    except Exception as e:
                        logger.warning(f"Failed to get cl100k_base encoding: {e}")
                        try:
                            names = _tk.list_encoding_names()
                            if names:
                                enc = _tk.get_encoding(names[0])
                                logger.debug(f"Using fallback encoding: {names[0]}")
                            else:
                                logger.warning("No tiktoken encodings available")
                        except Exception as e2:
                            logger.error(f"Failed to get any tiktoken encoding: {e2}")
                            enc = None

                    budget = max_ctx_tokens
                    total = 0
                    trimmed_docs: List[VectorDocument] = []

                    # Create a copy to avoid modifying original list during iteration
                    docs_to_process = list(context_docs)

                    for d in docs_to_process:
                        try:
                            text = getattr(d, "content", "") or ""
                            if not text:
                                continue

                            # Token counting with fallback
                            if enc:
                                try:
                                    # Handle encoding issues for non-ASCII characters
                                    toks = len(enc.encode(text, errors="replace"))
                                except Exception as e:
                                    logger.warning(
                                        f"Token encoding failed, using word count: {e}"
                                    )
                                    toks = len(text.split())
                            else:
                                toks = len(text.split())

                            if total + toks > budget:
                                remain = budget - total
                                if remain > 10:
                                    words = text.split()
                                    new_text = " ".join(words[:remain])
                                    d_short = VectorDocument(
                                        id=d.id,
                                        content=new_text,
                                        embedding=getattr(d, "embedding", []) or [],
                                        metadata=getattr(d, "metadata", {}) or {},
                                    )
                                    trimmed_docs.append(d_short)
                                    total = budget
                                break
                            trimmed_docs.append(d)
                            total += toks
                        except Exception as e:
                            logger.warning(
                                f"Error processing document {getattr(d, 'id', 'unknown')}: {e}"
                            )
                            continue

                    if trimmed_docs:
                        context_docs = trimmed_docs
                        logger.info(
                            "QA context trimmed to token budget",
                            tokens=total,
                            budget=budget,
                            original_count=len(context_docs),
                            trimmed_count=len(trimmed_docs),
                        )
                except ImportError:
                    logger.warning(
                        "tiktoken not available, skipping token-based trimming"
                    )
                except Exception as e:
                    logger.error(f"Error during token trimming: {e}")
                    # Continue with original context_docs

            # Build human-friendly references for prompt and response
            references: List[str] = []
            try:
                for d in context_docs:
                    meta = getattr(d, "metadata", {}) or {}
                    src = (
                        meta.get("source")
                        or meta.get("source_path")
                        or meta.get("file_name")
                        or d.id
                    )
                    pg = meta.get("page")
                    sl = meta.get("slide")
                    if pg:
                        ref = f"{src} (page {pg})"
                    elif sl:
                        ref = f"{src} (slide {sl})"
                    else:
                        ref = str(src)
                    if ref not in references:
                        references.append(ref)
            except Exception:
                references = []

            # Build prompt with context (+sources footer to encourage grounded citations)
            prompt = self.prompt_builder.build_qa_prompt(
                question=question,
                context_documents=context_docs,
                language=language,
                **kwargs,
            )
            if references:
                try:
                    refs_block = "\n".join(f"- {r}" for r in references[:10])
                    prompt = f"{prompt}\n\nSources (for grounding):\n{refs_block}"
                except Exception:
                    pass

            # Generate answer using LLM
            llm_start_time = time.time()
            answer_text = await self._generate_answer(prompt, **kwargs)
            llm_duration = time.time() - llm_start_time

            # Prepare response
            total_duration = time.time() - start_time
            response = {
                "answer": answer_text,
                "question": question,
                "language": language,
                "context_documents": context_docs,
                "sources": [doc.metadata.get("source", doc.id) for doc in context_docs],
                "processing_time": total_duration,
                "llm_time": llm_duration,
                "model_used": self.model_name,
                "context_count": len(context_docs),
                "references": references,
            }

            # Record metrics
            metrics_manager.record_query_processing(
                language, "success", total_duration, llm_duration=llm_duration
            )

            # Record quality metrics
            self._record_quality_metrics(
                question=question,
                answer_text=answer_text,
                context_docs=context_docs,
                model_name=self.model_name,
                response_data=response,
            )

            logger.info(
                "Generated answer for question",
                question_length=len(question),
                answer_length=len(answer_text),
                context_count=len(context_docs),
                language=language,
                duration=total_duration,
            )

            return response

        except Exception as e:
            metrics_manager.record_error("qa_generation", self.llm_provider)
            logger.error(f"Error generating answer: {e}")

            # Return error response
            error_message = self._get_error_message(language)
            return {
                "answer": error_message,
                "question": question,
                "language": language,
                "error": str(e),
                "context_documents": context_docs or [],
                "sources": [],
                "processing_time": time.time() - start_time,
                "model_used": self.model_name,
                "context_count": len(context_docs) if context_docs else 0,
            }

    async def _generate_answer(self, prompt: str, **kwargs: Any) -> str:
        """Generate answer using the configured LLM."""
        try:
            if self.llm_provider == "openai":
                return await self._generate_openai_answer(prompt, **kwargs)
            elif self.llm_provider == "openrouter":
                return await self._generate_openrouter_answer(prompt, **kwargs)
            elif self.llm_provider == "ollama":
                return await self._generate_ollama_answer(prompt, **kwargs)
            elif self.llm_provider == "hf_local":
                return await self._generate_hf_local_answer(prompt, **kwargs)
            else:
                raise LLMError(
                    f"Unsupported LLM provider: {self.llm_provider}",
                    provider=self.llm_provider,
                )

        except Exception as e:
            # Check if it's a pydantic-related error
            if "pydantic" in str(e).lower() or "__pydantic" in str(e):
                log_pydantic_error(
                    e,
                    context="qa_chain_generate_answer",
                    provider=self.llm_provider,
                    model=self.model_name,
                    prompt_length=len(prompt),
                )
            else:
                logger.error_with_traceback(
                    f"Error generating LLM answer: {e}",
                    exc_info=True,
                    provider=self.llm_provider,
                    model=self.model_name,
                    prompt_length=len(prompt),
                    error_type=type(e).__name__,
                    error_details=str(e),
                )

            raise LLMError(
                f"Failed to generate answer: {str(e)}",
                provider=self.llm_provider,
                model=self.model_name,
                prompt_length=len(prompt),
                details=str(e),
            ) from e

    async def _make_api_request(self, prompt: str, provider: str, **kwargs: Any) -> str:
        """Make API request with unified logic for OpenAI-compatible providers."""
        try:
            # Prepare request parameters
            request_params = {
                "model": kwargs.get("model", self.model_name),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": kwargs.get("temperature", self.temperature),
            }

            # Only add max_tokens if it's not None
            max_tokens = kwargs.get("max_tokens", self.max_tokens)
            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens

            # Log the API request details
            logger.info(
                f"Sending request to {provider} API",
                model=request_params["model"],
                max_tokens=max_tokens,
                temperature=request_params["temperature"],
                prompt_length=len(prompt),
                prompt_preview=prompt[:200] + "..." if len(prompt) > 200 else prompt,
            )

            # Make API request with retry logic
            max_retries = getattr(settings.llm, "max_retries", 3)
            retry_delay = getattr(settings.llm, "retry_delay", 1.0)
            retry_backoff = getattr(settings.llm, "retry_backoff", 2.0)

            for attempt in range(max_retries):
                try:
                    response = await self.async_client.chat.completions.create(
                        **request_params
                    )
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    logger.warning(
                        f"{provider} API request failed (attempt {attempt + 1}), retrying in {retry_delay}s: {e}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= retry_backoff

            # Extract answer with safety check
            if not response.choices:
                logger.error(f"Empty choices in {provider} response")
                return "No answer generated."

            answer = response.choices[0].message.content
            if answer:
                logger.info(
                    f"Received response from {provider} API",
                    model=request_params["model"],
                    answer_length=len(answer),
                    answer_preview=answer[:200] + "..."
                    if len(answer) > 200
                    else answer,
                    usage_tokens=getattr(response, "usage", {}).get(
                        "total_tokens", "N/A"
                    ),
                )
                return answer.strip()
            else:
                logger.warning(
                    f"Empty response from {provider} API",
                    model=request_params["model"],
                    prompt_length=len(prompt),
                )
                return "No answer generated."

        except Exception as e:
            logger.error(f"{provider} API error: {e}")
            raise LLMError(
                f"{provider} API error: {str(e)}",
                provider=provider,
                model=self.model_name,
                details=str(e),
            ) from e

    async def _generate_openai_answer(self, prompt: str, **kwargs: Any) -> str:
        """Generate answer using OpenAI API."""
        return await self._make_api_request(prompt, "OpenAI", **kwargs)

    async def _generate_openrouter_answer(self, prompt: str, **kwargs: Any) -> str:
        """Generate answer using OpenRouter (OpenAI-compatible chat API)."""
        return await self._make_api_request(prompt, "OpenRouter", **kwargs)

    async def _generate_ollama_answer(self, prompt: str, **kwargs: Any) -> str:
        """Generate answer using Ollama local LLM."""
        try:
            import asyncio

            max_tokens = kwargs.get("max_tokens", self.max_tokens)
            temperature = kwargs.get("temperature", self.temperature)

            def _run() -> str:
                try:
                    response = ollama.generate(
                        model=self.model_name,
                        prompt=prompt,
                        options={
                            "temperature": temperature,
                            "num_predict": max_tokens if max_tokens else 512,
                        },
                    )
                    return response.get("response", "")
                except Exception as e:
                    raise LLMError(
                        f"Ollama generation failed: {str(e)}",
                        provider="ollama",
                        model=self.model_name,
                    ) from e

            # Run in thread pool to avoid blocking
            answer = await asyncio.to_thread(_run)
            return answer

        except Exception as e:
            raise LLMError(
                f"Ollama answer generation failed: {str(e)}",
                provider="ollama",
                model=self.model_name,
            ) from e

    async def _generate_hf_local_answer(self, prompt: str, **kwargs: Any) -> str:
        """Generate answer locally with transformers pipeline (HF)."""
        try:
            import asyncio

            max_new_tokens = kwargs.get("max_tokens", self.max_tokens)
            temperature = kwargs.get("temperature", self.temperature)

            def _run() -> str:
                try:
                    # Get cached pipeline
                    pipe = self._hf_pipeline
                    if pipe is None:
                        raise RuntimeError("HuggingFace pipeline not initialized")

                    # Generate with proper parameters
                    out = pipe(
                        prompt,
                        max_new_tokens=max_new_tokens,
                        do_sample=True if temperature and temperature > 0 else False,
                        temperature=max(0.1, float(temperature))
                        if temperature
                        else 0.1,
                        pad_token_id=getattr(pipe.tokenizer, "eos_token_id", None),
                        return_full_text=False,  # Don't return the prompt
                    )

                    # Extract generated text
                    if isinstance(out, list) and len(out) > 0:
                        text = out[0].get("generated_text", "")
                    else:
                        text = str(out) if out else ""

                    return text.strip()

                except Exception as e:
                    logger.error(f"Error in HuggingFace generation: {e}")
                    raise

            return await asyncio.to_thread(_run)
        except Exception as e:
            logger.error(f"HF local generation error: {e}")
            raise LLMError(
                f"HF local generation error: {str(e)}",
                provider="hf_local",
                model=self.model_name,
                details=str(e),
            ) from e

    def _get_error_message(self, language: str) -> str:
        """Get error message in the specified language."""
        if language == "fa":
            return "متاسفانه خطایی رخ داد، لطفا دوباره تلاش کنید."
        else:
            return "An error occurred, please try again."

    def answer_sync(
        self,
        question: str,
        language: str = "en",
        context_docs: Optional[List[VectorDocument]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Synchronous version of answer method.

        Args:
            question: User question
            language: Response language
            context_docs: Pre-retrieved context documents
            **kwargs: Additional options

        Returns:
            Dict[str, Any]: Answer response with metadata
        """
        import asyncio

        return asyncio.run(self.answer(question, language, context_docs, **kwargs))

    async def batch_answer(
        self, questions: List[str], language: str = "en", **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Generate answers for multiple questions.

        Args:
            questions: List of questions
            language: Response language
            **kwargs: Additional options

        Returns:
            List[Dict[str, Any]]: List of answer responses
        """
        answers = []

        for question in questions:
            try:
                answer = await self.answer(question, language, **kwargs)
                answers.append(answer)
            except Exception as e:
                logger.error(f"Error answering question '{question}': {e}")
                error_answer = {
                    "answer": self._get_error_message(language),
                    "question": question,
                    "language": language,
                    "error": str(e),
                    "context_documents": [],
                    "sources": [],
                    "model_used": self.model_name,
                    "context_count": 0,
                }
                answers.append(error_answer)

        return answers

    def get_chain_info(self) -> Dict[str, Any]:
        """Get information about the QA chain configuration."""
        return {
            "llm_provider": self.llm_provider,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "retriever_info": self.retriever.get_retriever_info(),
        }

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the QA chain."""
        try:
            # Test retriever
            retriever_health = await self.retriever.health_check()

            # Test LLM with simple question
            test_response = await self.answer(
                "What is the capital of France?", language="en"
            )

            return {
                "status": "healthy",
                "chain_type": "QAChain",
                "llm_provider": self.llm_provider,
                "model_name": self.model_name,
                "retriever_status": retriever_health.get("status", "unknown"),
                "test_successful": "error" not in test_response,
                "test_answer_length": len(test_response.get("answer", "")),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "chain_type": "QAChain",
                "llm_provider": self.llm_provider,
                "error": str(e),
                "test_successful": False,
            }

    def _record_quality_metrics(
        self,
        question: str,
        answer_text: str,
        context_docs: List[VectorDocument],
        model_name: str,
        response_data: Dict[str, Any],
    ) -> None:
        """
        Record quality metrics for the generated response.

        Args:
            question: Original user question
            answer_text: Generated answer text
            context_docs: Context documents used
            model_name: Name of the LLM model
            response_data: Complete response data
        """
        try:
            # Calculate quality scores
            quality_scores = self._calculate_quality_scores(
                question=question,
                answer_text=answer_text,
                context_docs=context_docs,
                response_data=response_data,
            )

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                answer_text=answer_text,
                context_docs=context_docs,
                quality_scores=quality_scores,
            )

            # Extract context text for utilization calculation
            context_texts = []
            for doc in context_docs:
                if hasattr(doc, "content") and doc.content:
                    context_texts.append(doc.content)

            # Record to quality evaluator
            quality_evaluator.record_response_quality(
                query=question,
                response=answer_text,
                confidence_score=confidence_score,
                model_name=model_name,
                context_used=context_texts,
                quality_scores=quality_scores,
            )

            # Record to Prometheus metrics
            quality_data = {
                "confidence_score": confidence_score,
                "model_name": model_name,
                "quality_scores": quality_scores,
                "response_length": len(answer_text.split()),
                "context_utilization": len(context_texts) / max(len(context_texts), 1),
                "is_high_quality": confidence_score > 0.8
                and np.mean(list(quality_scores.values())) > 0.7,
                "is_low_confidence": confidence_score < 0.7,
            }

            quality_evaluator.record_evaluation_metrics(metrics_manager, quality_data)

            logger.debug(
                "Quality metrics recorded",
                confidence_score=confidence_score,
                avg_quality=np.mean(list(quality_scores.values())),
                model_name=model_name,
            )

        except Exception as e:
            logger.warning(f"Failed to record quality metrics: {e}")

    def _calculate_quality_scores(
        self,
        question: str,
        answer_text: str,
        context_docs: List[VectorDocument],
        response_data: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        Calculate quality scores for the response.

        Args:
            question: Original question
            answer_text: Generated answer
            context_docs: Context documents
            response_data: Response metadata

        Returns:
            Dictionary of quality scores
        """
        scores = {}

        try:
            # Accuracy score based on response completeness
            scores["accuracy"] = self._calculate_accuracy_score(answer_text, question)

            # Relevance score based on context utilization
            scores["relevance"] = self._calculate_relevance_score(
                answer_text, context_docs
            )

            # Completeness score based on answer length and detail
            scores["completeness"] = self._calculate_completeness_score(
                answer_text, question
            )

            # Coherence score based on text structure
            scores["coherence"] = self._calculate_coherence_score(answer_text)

            # Factual accuracy score (simplified heuristic)
            scores["factual_accuracy"] = self._calculate_factual_accuracy_score(
                answer_text, context_docs
            )

        except Exception as e:
            logger.warning(f"Error calculating quality scores: {e}")
            # Return default scores
            scores = {
                "accuracy": 0.5,
                "relevance": 0.5,
                "completeness": 0.5,
                "coherence": 0.5,
                "factual_accuracy": 0.5,
            }

        return scores

    def _calculate_accuracy_score(self, answer_text: str, question: str) -> float:
        """Calculate accuracy score based on answer completeness."""
        if not answer_text or not question:
            return 0.0

        # Simple heuristic: longer answers to longer questions tend to be more accurate
        answer_words = len(answer_text.split())
        question_words = len(question.split())

        # Normalize based on question complexity
        if question_words < 5:
            expected_length = 20
        elif question_words < 10:
            expected_length = 50
        else:
            expected_length = 100

        length_score = min(answer_words / expected_length, 1.0)

        # Check for common accuracy indicators
        accuracy_indicators = [
            "according to",
            "based on",
            "as mentioned",
            "the document",
            "the source",
        ]

        indicator_score = sum(
            1
            for indicator in accuracy_indicators
            if indicator.lower() in answer_text.lower()
        ) / len(accuracy_indicators)

        return length_score * 0.7 + indicator_score * 0.3

    def _calculate_relevance_score(
        self, answer_text: str, context_docs: List[VectorDocument]
    ) -> float:
        """Calculate relevance score based on context utilization."""
        if not answer_text or not context_docs:
            return 0.0

        # Extract key terms from context
        context_text = " ".join(
            [
                doc.content
                for doc in context_docs
                if hasattr(doc, "content") and doc.content
            ]
        )
        context_words = set(context_text.lower().split())
        answer_words = set(answer_text.lower().split())

        # Calculate word overlap
        if not context_words:
            return 0.0

        overlap = len(context_words.intersection(answer_words))
        relevance_score = overlap / len(context_words)

        return min(relevance_score, 1.0)

    def _calculate_completeness_score(self, answer_text: str, question: str) -> float:
        """Calculate completeness score based on answer detail."""
        if not answer_text or not question:
            return 0.0

        # Check for question words to determine expected completeness
        question_words = question.lower().split()

        if any(
            word in question_words
            for word in ["what", "how", "why", "when", "where", "who"]
        ):
            # Wh-questions expect detailed answers
            expected_length = 50
        elif any(word in question_words for word in ["explain", "describe", "tell"]):
            # Explanation questions expect longer answers
            expected_length = 100
        else:
            # Other questions
            expected_length = 30

        answer_length = len(answer_text.split())
        completeness_score = min(answer_length / expected_length, 1.0)

        return completeness_score

    def _calculate_coherence_score(self, answer_text: str) -> float:
        """Calculate coherence score based on text structure."""
        if not answer_text:
            return 0.0

        # Check for coherent structure indicators
        coherence_indicators = [
            "first",
            "second",
            "third",
            "finally",
            "however",
            "therefore",
            "moreover",
            "additionally",
            "in conclusion",
            "to summarize",
        ]

        indicator_count = sum(
            1
            for indicator in coherence_indicators
            if indicator.lower() in answer_text.lower()
        )

        # Check sentence structure
        sentences = answer_text.split(".")
        avg_sentence_length = sum(len(s.split()) for s in sentences) / max(
            len(sentences), 1
        )

        # Coherence score based on structure indicators and sentence flow
        structure_score = min(indicator_count / 5, 1.0)
        flow_score = min(avg_sentence_length / 20, 1.0)

        return structure_score * 0.6 + flow_score * 0.4

    def _calculate_factual_accuracy_score(
        self, answer_text: str, context_docs: List[VectorDocument]
    ) -> float:
        """Calculate factual accuracy score (simplified heuristic)."""
        if not answer_text or not context_docs:
            return 0.0

        # Extract facts from context
        context_facts = []
        for doc in context_docs:
            if hasattr(doc, "content") and doc.content:
                # Simple fact extraction (numbers, dates, names)
                import re

                facts = re.findall(
                    r"\b\d{4}\b|\b\d+\.\d+\b|\b[A-Z][a-z]+ [A-Z][a-z]+\b", doc.content
                )
                context_facts.extend(facts)

        # Check if answer contains context facts
        if not context_facts:
            return 0.5  # Neutral score if no facts to verify

        answer_facts = []
        import re

        facts = re.findall(
            r"\b\d{4}\b|\b\d+\.\d+\b|\b[A-Z][a-z]+ [A-Z][a-z]+\b", answer_text
        )
        answer_facts.extend(facts)

        # Calculate fact overlap
        fact_overlap = len(set(context_facts).intersection(set(answer_facts)))
        accuracy_score = fact_overlap / len(context_facts)

        return min(accuracy_score, 1.0)

    def _calculate_confidence_score(
        self,
        answer_text: str,
        context_docs: List[VectorDocument],
        quality_scores: Dict[str, float],
    ) -> float:
        """
        Calculate confidence score for the response.

        Args:
            answer_text: Generated answer
            context_docs: Context documents used
            quality_scores: Calculated quality scores

        Returns:
            Confidence score between 0.0 and 1.0
        """
        try:
            # Base confidence from quality scores
            avg_quality = (
                np.mean(list(quality_scores.values())) if quality_scores else 0.0
            )

            # Context availability factor
            context_factor = min(
                len(context_docs) / 5, 1.0
            )  # More context = higher confidence

            # Answer length factor (very short or very long answers may be less confident)
            answer_length = len(answer_text.split())
            if answer_length < 5:
                length_factor = 0.3
            elif answer_length > 200:
                length_factor = 0.8
            else:
                length_factor = 1.0

            # Uncertainty indicators (lower confidence)
            uncertainty_words = [
                "maybe",
                "perhaps",
                "might",
                "could",
                "possibly",
                "unclear",
                "unknown",
            ]
            uncertainty_count = sum(
                1 for word in uncertainty_words if word.lower() in answer_text.lower()
            )
            uncertainty_factor = max(0.5, 1.0 - (uncertainty_count * 0.1))

            # Confidence calculation
            confidence = (
                avg_quality * 0.4
                + context_factor * 0.3
                + length_factor * 0.2
                + uncertainty_factor * 0.1
            )

            return max(0.0, min(1.0, confidence))

        except Exception as e:
            logger.warning(f"Error calculating confidence score: {e}")
            return 0.5

    async def generate_structured_answer(
        self,
        question: str,
        response_model: Any,
        language: str = "en",
        context_docs: Optional[List[VectorDocument]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate structured answer using instructor for Pydantic models.

        Args:
            question: User question
            response_model: Pydantic model for structured response
            language: Response language
            context_docs: Optional context documents
            **kwargs: Additional parameters

        Returns:
            Dictionary containing structured response and metadata
        """
        if not INSTRUCTOR_AVAILABLE:
            raise LLMError(
                "instructor is required for structured outputs. Install with: pip install instructor",
                provider=self.llm_provider,
                model=self.model_name,
            )

        try:
            import instructor

            # Get context if not provided
            if context_docs is None:
                context_docs = await self.retriever.retrieve(question, top_k=5)

            # Build prompt
            prompt = self.prompt_builder.build_prompt(
                question=question,
                context_docs=context_docs,
                language=language,
            )

            # Generate structured response
            if self.llm_provider == "openai":
                client = instructor.from_openai(self.async_client)
                structured_response = await client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_model=response_model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
            else:
                # For other providers, fall back to regular generation
                answer_text = await self._generate_answer(prompt, **kwargs)
                # Parse response into model (basic implementation)
                try:
                    structured_response = response_model.model_validate_json(
                        answer_text
                    )
                except Exception:
                    # Fallback: create model with text field
                    structured_response = response_model(text=answer_text)

            return {
                "structured_response": structured_response,
                "question": question,
                "context_count": len(context_docs),
                "model_used": self.model_name,
                "provider": self.llm_provider,
            }

        except Exception as e:
            logger.error(f"Error generating structured answer: {e}")
            raise LLMError(
                f"Structured answer generation failed: {str(e)}",
                provider=self.llm_provider,
                model=self.model_name,
            ) from e  # Default neutral confidence
