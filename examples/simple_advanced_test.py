#!/usr/bin/env python3
"""
RAG Telegram Assistant - Simple Advanced Test
تست ساده و سریع قابلیت‌های Advanced Retrieval
"""

import asyncio
import sys
import time
from pathlib import Path

# اضافه کردن مسیر پروژه
sys.path.insert(0, str(Path(__file__).parent))

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import IntegrationService


class SimpleAdvancedTest:
    """تست ساده Advanced Retrieval"""

    def __init__(self):
        self.integration_service = None
        self.rag_service = None
        self.start_time = None

    async def initialize_system(self) -> bool:
        """مقداردهی اولیه سیستم"""
        try:
            logger.info("🚀 شروع مقداردهی سیستم...")
            self.start_time = time.time()

            self.integration_service = IntegrationService()
            await self.integration_service.initialize()
            self.rag_service = self.integration_service.components["rag_service"]

            init_time = time.time() - self.start_time
            logger.info(f"✅ سیستم آماده! ({init_time:.2f}s)")
            return True

        except Exception as e:
            logger.error(f"❌ خطا: {e}")
            return False

    def print_settings(self):
        """نمایش تنظیمات Advanced Retrieval"""
        print("\n" + "=" * 60)
        print("🚀 تنظیمات Advanced Retrieval")
        print("=" * 60)

        print(f"🔄 Reranking: {settings.advanced_retrieval.enable_reranking}")
        print(f"🔍 Hybrid Search: {settings.advanced_retrieval.enable_hybrid_search}")
        print(
            f"📝 Query Expansion: {settings.advanced_retrieval.enable_query_expansion}"
        )
        print(f"🎯 Reranker Model: {settings.advanced_retrieval.reranker_model}")
        print(f"📊 Hybrid Alpha: {settings.advanced_retrieval.hybrid_alpha}")
        print(
            f"🔢 Max Expanded Queries: {settings.advanced_retrieval.max_expanded_queries}"
        )
        print(
            f"⚡ Initial Search Multiplier: {settings.advanced_retrieval.initial_search_multiplier}"
        )
        print(
            f"🎯 Confidence Threshold: {settings.advanced_retrieval.confidence_threshold}"
        )

        print("\n" + "=" * 60)

    async def test_question(self, question: str):
        """تست یک سوال"""
        try:
            print(f"\n📝 سوال: {question}")
            print("-" * 60)

            start_time = time.time()
            result = await self.rag_service.query_documents(question)
            processing_time = time.time() - start_time

            print(f"✅ موفقیت! ({processing_time:.2f}s)")
            print(f"📏 طول پاسخ: {len(result.answer)} کاراکتر")
            print(f"📚 تعداد منابع: {len(result.sources)}")

            print("\n💬 پاسخ:")
            print("=" * 40)
            print(result.answer)
            print("=" * 40)

            if result.sources:
                print("\n📚 منابع:")
                for i, source in enumerate(result.sources, 1):
                    print(f"  {i}. {source}")

            return True

        except Exception as e:
            print(f"❌ خطا: {e}")
            return False

    async def test_query_expansion(self, question: str):
        """تست گسترش پرسش"""
        try:
            print(f"\n🔍 تست گسترش پرسش: {question}")
            print("-" * 60)

            if (
                hasattr(self.rag_service, "advanced_retriever")
                and self.rag_service.advanced_retriever
                and self.rag_service.advanced_retriever.query_expander
            ):
                expanded_queries = await self.rag_service.advanced_retriever.query_expander.expand_query(
                    question
                )

                print(f"✅ گسترش موفق! ({len(expanded_queries)} پرسش)")
                print("\n🔍 پرسش‌های گسترش یافته:")
                for i, query in enumerate(expanded_queries, 1):
                    print(f"  {i}. {query}")

                return True
            else:
                print("⚠️ Query Expander فعال نیست")
                return False

        except Exception as e:
            print(f"❌ خطا: {e}")
            return False

    async def test_performance(self, question: str):
        """تست عملکرد"""
        try:
            print(f"\n⚡ تست عملکرد: {question}")
            print("-" * 60)

            # تست چندباره
            times = []
            for i in range(3):
                start_time = time.time()
                result = await self.rag_service.query_documents(question)
                processing_time = time.time() - start_time
                times.append(processing_time)
                print(f"  تست {i + 1}: {processing_time:.2f}s")

            avg_time = sum(times) / len(times)
            print(f"\n📊 میانگین زمان: {avg_time:.2f}s")
            print(f"📏 طول پاسخ: {len(result.answer)} کاراکتر")
            print(f"📚 تعداد منابع: {len(result.sources)}")

            return True

        except Exception as e:
            print(f"❌ خطا: {e}")
            return False

    def print_summary(self, results: list):
        """نمایش خلاصه"""
        total_time = time.time() - self.start_time
        successful = sum(results)
        failed = len(results) - successful

        print("\n" + "=" * 60)
        print("📊 خلاصه نتایج")
        print("=" * 60)
        print(f"⏱️  کل زمان: {total_time:.2f} ثانیه")
        print(f"✅ موفق: {successful}")
        print(f"❌ ناموفق: {failed}")
        print(f"📝 کل تست‌ها: {len(results)}")
        print("=" * 60)


async def main():
    """تابع اصلی"""
    print("🚀 RAG Telegram Assistant - Simple Advanced Test")
    print("=" * 60)

    # ایجاد instance
    test = SimpleAdvancedTest()

    # مقداردهی سیستم
    if not await test.initialize_system():
        print("❌ خطا در مقداردهی سیستم!")
        return

    # نمایش تنظیمات
    test.print_settings()

    # تست‌ها
    test_questions = [
        "این پروژه RAG Telegram Assistant چه کاری انجام می‌دهد؟",
        "معماری RAG در این پروژه چطور پیاده‌سازی شده؟",
        "چرا از FAISS برای vector storage استفاده شده؟",
        "تنظیمات .env_deepseek چه مزایایی داره؟",
        "سیستم caching در این پروژه چطور کار می‌کنه؟",
    ]

    print(f"\n🧪 شروع {len(test_questions)} تست...")

    # اجرای تست‌ها
    results = []

    # تست سوالات
    for i, question in enumerate(test_questions, 1):
        print(f"\n🔄 تست {i}/{len(test_questions)}...")
        success = await test.test_question(question)
        results.append(success)

    # تست گسترش پرسش
    print("\n🔄 تست گسترش پرسش...")
    success = await test.test_query_expansion("RAG چیست؟")
    results.append(success)

    # تست عملکرد
    print("\n🔄 تست عملکرد...")
    success = await test.test_performance("Advanced Retrieval چه قابلیت‌هایی داره؟")
    results.append(success)

    # نمایش خلاصه
    test.print_summary(results)

    print("\n🎉 تست ساده کامل انجام شد!")


if __name__ == "__main__":
    # اجرای تست
    asyncio.run(main())
