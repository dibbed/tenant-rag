"""
Content filter quick example.

This script demonstrates how ContentFilter behaves on toxic, spam, and safe texts.
All prints are in English.
"""

from __future__ import annotations

import asyncio

from ragbot.security.content_filter import ContentFilter


async def run_demo() -> None:
    cf = ContentFilter()

    samples = {
        "toxic": "این آدم احمق است و من متنفرم",
        "spam": "Check this link https://example.com @user #promo !!!",
        "safe": "سلام! این یک پیام معمولی است.",
    }

    for label, text in samples.items():
        result = await cf.filter_content(text)
        print("==== Sample:", label, "====")
        print("is_safe:", result.is_safe)
        print("content_type:", result.content_type.value)
        print("reasons:", ", ".join(result.reasons) if result.reasons else "-")
        if not result.is_safe:
            print("filtered_content:", result.filtered_content)
        print()


if __name__ == "__main__":
    asyncio.run(run_demo())
