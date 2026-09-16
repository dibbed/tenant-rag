"""
Lightweight toxicity detector utilities.

All logs/prints in English. Docstrings in Persian per project rules.
"""

from __future__ import annotations

from typing import Any, Dict


class ToxicityDetector:
    """تشخیص ساده محتوای سمی بر اساس لیست واژگان"""

    def __init__(self) -> None:
        self.words_fa = {"احمق", "خنگ", "فحش", "لعنتی"}
        self.words_en = {"stupid", "idiot", "dumb", "hate"}

    async def analyze(self, text: str) -> Dict[str, Any]:
        """تحلیل سمی بودن متن"""

        lowered = text.lower()
        fa_hits = [w for w in self.words_fa if w in lowered]
        en_hits = [w for w in self.words_en if w in lowered]
        total_hits = len(fa_hits) + len(en_hits)
        is_toxic = total_hits > 0
        confidence = min(total_hits / 3.0, 1.0) if is_toxic else 0.0
        return {
            "is_toxic": is_toxic,
            "confidence": float(confidence),
            "hits": list(fa_hits + en_hits),
        }
