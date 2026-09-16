import pytest

from ragbot.security.content_filter import ContentFilter, ContentType


class TestContentFilter:
    @pytest.mark.asyncio
    async def test_toxic_content_detection(self):
        cf = ContentFilter()
        result = await cf.filter_content("این شخص احمق است")
        assert result.is_safe is False
        assert result.content_type == ContentType.TOXIC
        assert any("سمی" in r for r in result.reasons)

    @pytest.mark.asyncio
    async def test_spam_detection(self):
        cf = ContentFilter()
        text = "خرید کنید! https://example.com @user #tag"
        result = await cf.filter_content(text)
        assert result.is_safe is False
        assert result.content_type == ContentType.SPAM

    @pytest.mark.asyncio
    async def test_safe_content(self):
        cf = ContentFilter()
        result = await cf.filter_content("سلام وقت بخیر")
        assert result.is_safe is True
        assert result.content_type == ContentType.SAFE
