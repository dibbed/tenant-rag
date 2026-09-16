"""
Prompt building system for RAG-based question answering.

This module provides comprehensive prompt building functionality with
multi-language support, context formatting, and customizable templates.
"""

from typing import Any, List, Optional, Union

from ragbot.outputs.logger import logger
from ragbot.rag.store.base import VectorDocument


class PromptBuilder:
    """
    Prompt builder for RAG-based question answering.

    This class provides flexible prompt building with support for multiple
    languages, custom templates, and various context formatting options.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize prompt builder.

        Args:
            **kwargs: Configuration options including:
                - max_context_length: Maximum context length
                - include_sources: Whether to include source information
                - custom_templates: Custom prompt templates
        """
        self.max_context_length = kwargs.get("max_context_length", 3000)
        self.include_sources = kwargs.get("include_sources", True)
        self.custom_templates = kwargs.get("custom_templates", {})

        # Default prompt templates
        self.templates = {
            "qa_system_en": """You are a helpful AI assistant that answers questions based on provided context.
Follow these guidelines:
1. Answer based only on the provided context
2. If the context doesn't contain enough information, say so clearly
3. Keep your answer concise and relevant
4. Cite sources when possible
5. Be accurate and factual""",
            "qa_system_fa": """شما یک دستیار هوشمند هستید که بر اساس متن‌های ارائه شده به سوالات پاسخ می‌دهید.
این دستورالعمل‌ها را دنبال کنید:
۱. فقط بر اساس متن‌های ارائه شده پاسخ دهید
۲. اگر اطلاعات کافی در متن‌ها وجود ندارد، این موضوع را به صراحت بیان کنید
۳. پاسخ خود را مختصر و مرتبط نگه دارید
۴. در صورت امکان منابع را ذکر کنید
۵. دقیق و واقعی باشید""",
            "qa_user_en": """Context:
{context}

Question: {question}

Answer:""",
            "qa_user_fa": """متن:
{context}

سوال: {question}

پاسخ:""",
            "no_context_en": "I don't have enough information in the provided context to answer this question accurately.",
            "no_context_fa": "اطلاعات کافی در متن‌های ارائه شده برای پاسخ دقیق به این سوال وجود ندارد.",
        }

        # Update with custom templates
        self.templates.update(self.custom_templates)

        logger.debug("Prompt builder initialized")

    def build_qa_prompt(
        self,
        context_or_question: Union[
            List[str], str
        ],  # First parameter - can be context or question
        question_or_context: Optional[
            Union[List[str], str]
        ] = None,  # Second parameter - can be question or context
        language: str = "en",
        **kwargs: Any,
    ) -> str:
        """
        Build a QA prompt with context documents or strings.

        This method supports both parameter orders for backward compatibility:
        - build_qa_prompt(context, question, language) - test format
        - build_qa_prompt(question, context_documents, language) - new format

        Args:
            context_or_question: Context list or question string
            question_or_context: Question string or context list
            language: Response language ("en", "fa")
            **kwargs: Additional options

        Returns:
            str: Formatted prompt for LLM
        """
        try:
            # Determine parameter order based on types
            if isinstance(context_or_question, list):
                # Test format: build_qa_prompt(context, question, language)
                context_documents = context_or_question
                question = question_or_context
            else:
                # New format: build_qa_prompt(question, context_documents, language)
                question = context_or_question
                context_documents = question_or_context or []

            # Convert strings to VectorDocument objects if needed
            if context_documents and isinstance(context_documents[0], str):
                vector_docs = [
                    VectorDocument(
                        id=f"context_{i}",
                        content=text,
                        embedding=[],
                        metadata={"source": f"context_{i}"},
                    )
                    for i, text in enumerate(context_documents)
                ]
            else:
                vector_docs = context_documents or []

            # Format context from documents
            context_text = self._format_context_documents(
                vector_docs, language, **kwargs
            )

            # Handle empty context
            if not context_text.strip():
                no_context_prompt = self._build_no_context_prompt(question, language)
                logger.warning(
                    f"No context available for question: '{question[:50]}...'",
                    question_length=len(question),
                    language=language,
                    prompt_length=len(no_context_prompt),
                    prompt_preview=no_context_prompt[:200] + "..."
                    if len(no_context_prompt) > 200
                    else no_context_prompt,
                )
                return no_context_prompt

            # Build full prompt
            if kwargs.get("use_system_prompt", True):
                final_prompt = self._build_system_user_prompt(
                    question, context_text, language
                )
            else:
                final_prompt = self._build_single_prompt(
                    question, context_text, language
                )

            # Log the generated prompt for debugging
            logger.info(
                f"Generated prompt for question: '{question[:50]}...'",
                question_length=len(question),
                context_length=len(context_text),
                prompt_length=len(final_prompt),
                language=language,
                document_count=len(vector_docs),
                use_system_prompt=kwargs.get("use_system_prompt", True),
                prompt_preview=final_prompt[:200] + "..."
                if len(final_prompt) > 200
                else final_prompt,
            )

            return final_prompt

        except Exception as e:
            logger.error(f"Error building QA prompt: {e}")
            return self._build_fallback_prompt(
                question or str(context_or_question), language
            )

    def _format_context_documents(
        self, documents: List[VectorDocument], language: str, **kwargs: Any
    ) -> str:
        """Format context documents into a single text."""
        if not documents:
            return ""

        context_parts = []
        total_length = 0

        for i, doc in enumerate(documents, 1):
            # Prepare document text
            doc_text = doc.content.strip()

            # Add source information if enabled
            if self.include_sources and doc.metadata:
                source = doc.metadata.get("source", doc.id)
                if language == "fa":
                    doc_header = f"منبع {i} ({source}):"
                else:
                    doc_header = f"Source {i} ({source}):"

                formatted_doc = f"{doc_header}\n{doc_text}"
            else:
                if language == "fa":
                    formatted_doc = f"منبع {i}:\n{doc_text}"
                else:
                    formatted_doc = f"Source {i}:\n{doc_text}"

            # Check length constraints
            if total_length + len(formatted_doc) > self.max_context_length:
                # Try to fit partial content
                remaining_length = self.max_context_length - total_length - 50  # Buffer
                if remaining_length > 100:
                    truncated_text = doc_text[:remaining_length] + "..."
                    if self.include_sources and doc.metadata:
                        source = doc.metadata.get("source", doc.id)
                        if language == "fa":
                            formatted_doc = f"منبع {i} ({source}):\n{truncated_text}"
                        else:
                            formatted_doc = f"Source {i} ({source}):\n{truncated_text}"
                    else:
                        if language == "fa":
                            formatted_doc = f"منبع {i}:\n{truncated_text}"
                        else:
                            formatted_doc = f"Source {i}:\n{truncated_text}"

                    context_parts.append(formatted_doc)
                break

            context_parts.append(formatted_doc)
            total_length += len(formatted_doc)

        return "\n\n".join(context_parts)

    def _build_system_user_prompt(
        self, question: str, context: str, language: str
    ) -> str:
        """Build prompt with system and user messages."""
        system_template = f"qa_system_{language}"
        user_template = f"qa_user_{language}"

        system_prompt = self.templates.get(
            system_template, self.templates["qa_system_en"]
        )
        user_prompt = self.templates.get(user_template, self.templates["qa_user_en"])

        # Format user prompt
        formatted_user = user_prompt.format(context=context, question=question)

        # Combine system and user prompts
        return f"{system_prompt}\n\n{formatted_user}"

    def _build_single_prompt(self, question: str, context: str, language: str) -> str:
        """Build a single comprehensive prompt."""
        if language == "fa":
            return f"""بر اساس متن‌های زیر به سوال پاسخ دهید. پاسخ باید دقیق، مفصل و بر اساس اطلاعات ارائه شده باشد.

متن‌های مرجع:
{context}

سوال: {question}

پاسخ:"""
        else:
            return f"""Answer the question based on the following context. Your answer should be accurate, detailed, and based on the provided information.

Context:
{context}

Question: {question}

Answer:"""

    def _build_no_context_prompt(self, question: str, language: str) -> str:
        """Build prompt when no context is available."""
        no_context_msg = self.templates.get(
            f"no_context_{language}", self.templates["no_context_en"]
        )

        if language == "fa":
            return f"""متن:
هیچ متن مناسبی یافت نشد.

سوال: {question}

پاسخ: {no_context_msg}"""
        else:
            return f"""Context:
No relevant context found.

Question: {question}

Answer: {no_context_msg}"""

    def _build_fallback_prompt(self, question: str, language: str) -> str:
        """Build fallback prompt in case of errors."""
        if language == "fa":
            return f"سوال: {question}\n\nپاسخ: متاسفانه نمی‌توانم به این سوال پاسخ دهم."
        else:
            return (
                f"Question: {question}\n\nAnswer: I'm unable to answer this question."
            )

    def build_custom_prompt(self, template_name: str, **kwargs: Any) -> str:
        """
        Build a prompt using a custom template.

        Args:
            template_name: Name of the template to use
            **kwargs: Variables to substitute in the template

        Returns:
            str: Formatted prompt
        """
        template = self.templates.get(template_name)
        if not template:
            logger.warning(f"Template '{template_name}' not found")
            return ""

        try:
            return template.format(**kwargs)
        except Exception as e:
            logger.error(f"Error formatting template '{template_name}': {e}")
            return template

    def add_template(self, name: str, template: str) -> None:
        """Add a custom template."""
        self.templates[name] = template
        logger.debug(f"Added custom template: {name}")

    def get_template(self, name: str) -> Optional[str]:
        """Get a template by name."""
        return self.templates.get(name)

    def list_templates(self) -> List[str]:
        """List all available template names."""
        return list(self.templates.keys())

    def _to_persian_numeral(self, number: int) -> str:
        """Convert Arabic numerals to Persian numerals."""
        persian_numerals = {
            "1": "۱",
            "2": "۲",
            "3": "۳",
            "4": "۴",
            "5": "۵",
            "6": "۶",
            "7": "۷",
            "8": "۸",
            "9": "۹",
            "0": "۰",
        }
        return "".join(persian_numerals.get(d, d) for d in str(number))
