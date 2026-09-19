"""
Content filtering utilities for detecting and redacting unsafe content.

All log/output strings are in English. Docstrings are in Persian per project rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class ContentType(Enum):
    """انواع محتوا"""

    SAFE = "safe"
    TOXIC = "toxic"
    SPAM = "spam"
    SENSITIVE = "sensitive"
    INAPPROPRIATE = "inappropriate"


@dataclass
class FilterResult:
    """نتیجه فیلتر"""

    is_safe: bool
    content_type: ContentType
    confidence: float
    reasons: List[str]
    filtered_content: Optional[str] = None


class ContentFilter:
    """فیلتر محتوای نامناسب"""

    def __init__(self) -> None:
        """Initialize content filter with simple lexical rules."""

        # Persian toxic words (minimal seed list)
        self.toxic_words_fa = {
            "فحش",
            "زشت",
            "کثیف",
            "احمق",
            "خنگ",
            "بی‌عقل",
        }

        # English toxic words (minimal seed list)
        self.toxic_words_en = {
            "stupid",
            "idiot",
            "dumb",
            "hate",
            "kill",
            "die",
        }

        # Spam patterns
        self.spam_patterns = [
            r"https?://[^\s]+",  # URLs
            r"@\w+",  # mentions
            r"#\w+",  # hashtags
            r"\$\w+",  # crypto tickers
            r"[A-Z]{3,}",  # long uppercase runs
        ]

        # Sensitive words removed to avoid false positives for educational content
        # Keep empty by default; can be populated via runtime config if needed
        self.sensitive_words = set()

    async def filter_content(
        self, text: str, user_id: Optional[str] = None
    ) -> FilterResult:
        """فیلتر محتوای نامناسب

        Args:
            text: متن برای فیلتر
            user_id: شناسه کاربر (اختیاری)

        Returns:
            نتیجه فیلتر
        """

        reasons: List[str] = []
        confidence_scores: List[float] = []

        toxicity_result = await self._check_toxicity(text)
        if toxicity_result["is_toxic"]:
            reasons.append("محتوای سمی")
            confidence_scores.append(float(toxicity_result["confidence"]))

        spam_result = await self._check_spam(text)
        if spam_result["is_spam"]:
            reasons.append("محتوای spam")
            confidence_scores.append(float(spam_result["confidence"]))

        sensitive_result = await self._check_sensitive_content(text)
        if sensitive_result["is_sensitive"]:
            reasons.append("محتوای حساس")
            confidence_scores.append(float(sensitive_result["confidence"]))

        inappropriate_result = await self._check_inappropriate_content(text)
        if inappropriate_result["is_inappropriate"]:
            reasons.append("محتوای نامناسب")
            confidence_scores.append(float(inappropriate_result["confidence"]))

        if toxicity_result["is_toxic"]:
            content_type = ContentType.TOXIC
        elif spam_result["is_spam"]:
            content_type = ContentType.SPAM
        elif sensitive_result["is_sensitive"]:
            content_type = ContentType.SENSITIVE
        elif inappropriate_result["is_inappropriate"]:
            content_type = ContentType.INAPPROPRIATE
        else:
            content_type = ContentType.SAFE

        overall_confidence = max(confidence_scores) if confidence_scores else 0.0
        is_safe = len(reasons) == 0

        filtered_content: Optional[str] = None
        if not is_safe:
            filtered_content = await self._filter_text(text, content_type)

        return FilterResult(
            is_safe=is_safe,
            content_type=content_type,
            confidence=overall_confidence,
            reasons=reasons,
            filtered_content=filtered_content,
        )

    async def _check_toxicity(self, text: str) -> Dict[str, Any]:
        """بررسی محتوای سمی"""

        text_lower = text.lower()
        toxic_count_fa = sum(1 for word in self.toxic_words_fa if word in text_lower)
        toxic_count_en = sum(1 for word in self.toxic_words_en if word in text_lower)
        total_toxic = toxic_count_fa + toxic_count_en
        is_toxic = total_toxic > 0
        confidence = float(min(total_toxic / 3.0, 1.0)) if is_toxic else 0.0
        return {
            "is_toxic": is_toxic,
            "confidence": confidence,
            "toxic_count": total_toxic,
        }

    async def _check_spam(self, text: str) -> Dict[str, Any]:
        """بررسی spam"""

        spam_score = 0.0
        for pattern in self.spam_patterns:
            matches = len(re.findall(pattern, text))
            spam_score += float(matches) * 0.2

        # Character repetition bursts
        char_repeats = len(re.findall(r"(.)\1{3,}", text))
        spam_score += float(char_repeats) * 0.3

        if len(text) > 500:
            spam_score += 0.2

        is_spam = spam_score > 0.5
        confidence = float(min(spam_score, 1.0))
        return {"is_spam": is_spam, "confidence": confidence, "spam_score": spam_score}

    async def _check_sensitive_content(self, text: str) -> Dict[str, Any]:
        """بررسی محتوای حساس"""

        text_lower = text.lower()
        sensitive_count = sum(1 for word in self.sensitive_words if word in text_lower)
        is_sensitive = sensitive_count > 0
        confidence = float(min(sensitive_count / 2.0, 1.0)) if is_sensitive else 0.0
        return {
            "is_sensitive": is_sensitive,
            "confidence": confidence,
            "sensitive_count": sensitive_count,
        }

    async def _check_inappropriate_content(self, text: str) -> Dict[str, Any]:
        """بررسی محتوای نامناسب"""

        inappropriate_patterns = [
            r"[0-9]{4,}",  # long digit sequences (potential phone/card)
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",  # email
            r"\+?[1-9]\d{1,14}",  # phone (E.164-ish)
        ]
        inappropriate_score = 0.0
        for pattern in inappropriate_patterns:
            matches = len(re.findall(pattern, text))
            inappropriate_score += float(matches) * 0.3

        is_inappropriate = inappropriate_score > 0.5
        confidence = float(min(inappropriate_score, 1.0))
        return {
            "is_inappropriate": is_inappropriate,
            "confidence": confidence,
            "inappropriate_score": inappropriate_score,
        }

    async def _filter_text(self, text: str, content_type: ContentType) -> str:
        """فیلتر کردن متن"""

        if content_type == ContentType.TOXIC:
            filtered_text = text
            for word in self.toxic_words_fa | self.toxic_words_en:
                filtered_text = re.sub(
                    re.escape(word),
                    "*" * len(word),
                    filtered_text,
                    flags=re.IGNORECASE,
                )
            return filtered_text

        if content_type == ContentType.SPAM:
            filtered_text = text
            for pattern in self.spam_patterns:
                filtered_text = re.sub(pattern, "[FILTERED]", filtered_text)
            return filtered_text

        return "[محتوای فیلتر شده]"
