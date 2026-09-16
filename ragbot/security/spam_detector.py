"""
Heuristic spam detector.

All logs in English; docstrings in Persian per rules.
"""

from __future__ import annotations

import re
from typing import Any, Dict


class SpamDetector:
    """تشخیص spam بر اساس الگوهای ساده"""

    def __init__(self) -> None:
        self.patterns = [
            r"https?://[^\s]+",
            r"@\w+",
            r"#\w+",
            r"\$\w+",
        ]

    async def analyze(self, text: str) -> Dict[str, Any]:
        """تحلیل spam"""

        score = 0.0
        for p in self.patterns:
            score += 0.2 * len(re.findall(p, text))

        # Character repetition
        score += 0.3 * len(re.findall(r"(.)\1{3,}", text))

        if len(text) > 500:
            score += 0.2

        is_spam = score > 0.5
        return {
            "is_spam": is_spam,
            "confidence": float(min(score, 1.0)),
            "score": score,
        }
