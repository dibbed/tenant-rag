#!/usr/bin/env python3
"""
RAG Telegram Assistant - Comparison Test
مقایسه عملکرد قبل و بعد از Advanced Retrieval
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# اضافه کردن مسیر پروژه
sys.path.insert(0, str(Path(__file__).parent))

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import IntegrationService


class ComparisonTest:
    """تست مقایسه‌ای عملکرد"""

    def __init__(self):
        self.integration_service = None
        self.rag_service = None
        self.start_time = None
        self.results = []

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

    async def test_basic_retrieval(self, question: str) -> Dict[str, Any]:
        """تست جستجوی پایه"""
        try:
            # غیرفعال کردن Advanced Retrieval موقتاً
            original_advanced = settings.advanced_retrieval.enable_reranking
            settings.advanced_retrieval.enable_reranking = False
            settings.advanced_retrieval.enable_hybrid_search = False
            settings.advanced_retrieval.enable_query_expansion = False

            start_time = time.time()
            result = await self.rag_service.query_documents(question)
            processing_time = time.time() - start_time

            # بازگرداندن تنظیمات اصلی
            settings.advanced_retrieval.enable_reranking = original_advanced

            return {
                "type": "basic",
                "question": question,
                "answer": result.answer,
                "sources": result.sources,
                "processing_time": processing_time,
                "answer_length": len(result.answer),
                "source_count": len(result.sources),
                "success": True,
            }

        except Exception as e:
            logger.error(f"❌ خطا در تست پایه: {e}")
            return {
                "type": "basic",
                "question": question,
                "answer": f"خطا: {str(e)}",
                "sources": [],
                "processing_time": 0,
                "answer_length": 0,
                "source_count": 0,
                "success": False,
            }

    async def test_advanced_retrieval(self, question: str) -> Dict[str, Any]:
        """تست جستجوی پیشرفته"""
        try:
            # فعال کردن Advanced Retrieval
            settings.advanced_retrieval.enable_reranking = True
            settings.advanced_retrieval.enable_hybrid_search = True
            settings.advanced_retrieval.enable_query_expansion = True

            start_time = time.time()
            result = await self.rag_service.query_documents(question)
            processing_time = time.time() - start_time

            return {
                "type": "advanced",
                "question": question,
                "answer": result.answer,
                "sources": result.sources,
                "processing_time": processing_time,
                "answer_length": len(result.answer),
                "source_count": len(result.sources),
                "success": True,
            }

        except Exception as e:
            logger.error(f"❌ خطا در تست پیشرفته: {e}")
            return {
                "type": "advanced",
                "question": question,
                "answer": f"خطا: {str(e)}",
                "sources": [],
                "processing_time": 0,
                "answer_length": 0,
                "source_count": 0,
                "success": False,
            }

    async def compare_retrieval(self, question: str) -> Dict[str, Any]:
        """مقایسه جستجوی پایه و پیشرفته"""
        try:
            print(f"\n📝 مقایسه: {question}")
            print("-" * 60)

            # تست جستجوی پایه
            print("🔍 تست جستجوی پایه...")
            basic_result = await self.test_basic_retrieval(question)

            # تست جستجوی پیشرفته
            print("🚀 تست جستجوی پیشرفته...")
            advanced_result = await self.test_advanced_retrieval(question)

            # محاسبه بهبود
            if basic_result["success"] and advanced_result["success"]:
                time_improvement = (
                    (
                        basic_result["processing_time"]
                        - advanced_result["processing_time"]
                    )
                    / basic_result["processing_time"]
                ) * 100
                length_improvement = (
                    (advanced_result["answer_length"] - basic_result["answer_length"])
                    / basic_result["answer_length"]
                ) * 100

                print("✅ مقایسه موفق!")
                print(
                    f"🔍 پایه: {basic_result['processing_time']:.2f}s | {basic_result['answer_length']} chars"
                )
                print(
                    f"🚀 پیشرفته: {advanced_result['processing_time']:.2f}s | {advanced_result['answer_length']} chars"
                )
                print(f"📊 بهبود زمان: {time_improvement:.1f}%")
                print(f"📏 بهبود طول: {length_improvement:.1f}%")

                return {
                    "question": question,
                    "basic": basic_result,
                    "advanced": advanced_result,
                    "improvements": {
                        "time_improvement_percent": time_improvement,
                        "length_improvement_percent": length_improvement,
                        "source_count_difference": advanced_result["source_count"]
                        - basic_result["source_count"],
                    },
                    "success": True,
                }
            else:
                print("❌ خطا در مقایسه")
                return {
                    "question": question,
                    "basic": basic_result,
                    "advanced": advanced_result,
                    "improvements": None,
                    "success": False,
                }

        except Exception as e:
            logger.error(f"❌ خطا در مقایسه: {e}")
            return {
                "question": question,
                "basic": None,
                "advanced": None,
                "improvements": None,
                "success": False,
            }

    def print_system_info(self):
        """نمایش اطلاعات سیستم"""
        print("\n" + "=" * 60)
        print("🔧 اطلاعات سیستم")
        print("=" * 60)

        print(f"🤖 LLM Model: {settings.llm.model}")
        print(f"🔍 Embedding Model: {settings.embedding.model}")
        print(f"📊 Chunk Size: {settings.rag.chunk_size}")
        print(f"🎯 Top K: {settings.rag.top_k}")
        print(f"📏 Similarity Threshold: {settings.rag.similarity_threshold}")

        print("\n🚀 Advanced Retrieval:")
        print(f"  🔄 Reranking: {settings.advanced_retrieval.enable_reranking}")
        print(f"  🔍 Hybrid Search: {settings.advanced_retrieval.enable_hybrid_search}")
        print(
            f"  📝 Query Expansion: {settings.advanced_retrieval.enable_query_expansion}"
        )
        print(f"  🎯 Reranker Model: {settings.advanced_retrieval.reranker_model}")
        print(f"  📊 Hybrid Alpha: {settings.advanced_retrieval.hybrid_alpha}")

        print("=" * 60)

    def print_comparison_summary(self, results: list):
        """نمایش خلاصه مقایسه"""
        total_time = time.time() - self.start_time
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        print("\n" + "=" * 60)
        print("📊 خلاصه مقایسه")
        print("=" * 60)

        print(f"⏱️  کل زمان: {total_time:.2f} ثانیه")
        print(f"✅ موفق: {successful}")
        print(f"❌ ناموفق: {failed}")
        print(f"📝 کل مقایسه‌ها: {len(results)}")

        if successful > 0:
            # محاسبه آمار بهبود
            time_improvements = [
                r["improvements"]["time_improvement_percent"]
                for r in results
                if r["success"]
            ]
            length_improvements = [
                r["improvements"]["length_improvement_percent"]
                for r in results
                if r["success"]
            ]

            avg_time_improvement = sum(time_improvements) / len(time_improvements)
            avg_length_improvement = sum(length_improvements) / len(length_improvements)

            print("\n📊 آمار بهبود:")
            print(f"  ⚡ میانگین بهبود زمان: {avg_time_improvement:.1f}%")
            print(f"  📏 میانگین بهبود طول: {avg_length_improvement:.1f}%")

            # بهترین و بدترین بهبود
            best_time = max(time_improvements)
            worst_time = min(time_improvements)
            best_length = max(length_improvements)
            worst_length = min(length_improvements)

            print("\n🏆 بهترین بهبود:")
            print(f"  ⚡ زمان: {best_time:.1f}%")
            print(f"  📏 طول: {best_length:.1f}%")

            print("\n📉 بدترین بهبود:")
            print(f"  ⚡ زمان: {worst_time:.1f}%")
            print(f"  📏 طول: {worst_length:.1f}%")

        print("=" * 60)

    def save_results(self, results: list):
        """ذخیره نتایج"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = Path(f"comparison_results_{timestamp}.txt")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("📊 نتایج مقایسه RAG\n")
            f.write("=" * 60 + "\n\n")

            for i, result in enumerate(results, 1):
                f.write(f"📝 مقایسه {i}: {result['question']}\n")
                f.write("-" * 60 + "\n")

                if result["success"]:
                    f.write("✅ مقایسه موفق!\n\n")

                    f.write("🔍 جستجوی پایه:\n")
                    f.write(f"  ⏱️  زمان: {result['basic']['processing_time']:.2f}s\n")
                    f.write(
                        f"  📏 طول پاسخ: {result['basic']['answer_length']} کاراکتر\n"
                    )
                    f.write(f"  📚 تعداد منابع: {result['basic']['source_count']}\n\n")

                    f.write("🚀 جستجوی پیشرفته:\n")
                    f.write(
                        f"  ⏱️  زمان: {result['advanced']['processing_time']:.2f}s\n"
                    )
                    f.write(
                        f"  📏 طول پاسخ: {result['advanced']['answer_length']} کاراکتر\n"
                    )
                    f.write(
                        f"  📚 تعداد منابع: {result['advanced']['source_count']}\n\n"
                    )

                    f.write("📊 بهبودها:\n")
                    f.write(
                        f"  ⚡ بهبود زمان: {result['improvements']['time_improvement_percent']:.1f}%\n"
                    )
                    f.write(
                        f"  📏 بهبود طول: {result['improvements']['length_improvement_percent']:.1f}%\n"
                    )
                    f.write(
                        f"  📚 تفاوت منابع: {result['improvements']['source_count_difference']}\n\n"
                    )

                    f.write("💬 پاسخ پیشرفته:\n")
                    f.write("=" * 40 + "\n")
                    f.write(result["advanced"]["answer"] + "\n")
                    f.write("=" * 40 + "\n\n")
                else:
                    f.write("❌ خطا در مقایسه\n\n")

            # خلاصه
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful

            f.write("📊 خلاصه:\n")
            f.write(f"  ✅ موفق: {successful}\n")
            f.write(f"  ❌ ناموفق: {failed}\n")
            f.write(f"  📝 کل مقایسه‌ها: {len(results)}\n")

            if successful > 0:
                time_improvements = [
                    r["improvements"]["time_improvement_percent"]
                    for r in results
                    if r["success"]
                ]
                length_improvements = [
                    r["improvements"]["length_improvement_percent"]
                    for r in results
                    if r["success"]
                ]

                avg_time_improvement = sum(time_improvements) / len(time_improvements)
                avg_length_improvement = sum(length_improvements) / len(
                    length_improvements
                )

                f.write(f"  ⚡ میانگین بهبود زمان: {avg_time_improvement:.1f}%\n")
                f.write(f"  📏 میانگین بهبود طول: {avg_length_improvement:.1f}%\n")

        print(f"💾 نتایج ذخیره شد: {output_file}")


async def main():
    """تابع اصلی"""
    print("🚀 RAG Telegram Assistant - Comparison Test")
    print("=" * 60)

    # ایجاد instance
    test = ComparisonTest()

    # مقداردهی سیستم
    if not await test.initialize_system():
        print("❌ خطا در مقداردهی سیستم!")
        return

    # نمایش اطلاعات سیستم
    test.print_system_info()

    # سوالات تست
    test_questions = [
        "این پروژه RAG Telegram Assistant چه کاری انجام می‌دهد؟",
        "معماری RAG در این پروژه چطور پیاده‌سازی شده؟",
        "چرا از FAISS برای vector storage استفاده شده؟",
        "تنظیمات .env_deepseek چه مزایایی داره؟",
        "سیستم caching در این پروژه چطور کار می‌کنه؟",
        "Advanced Retrieval چه قابلیت‌هایی داره؟",
    ]

    print(f"\n🧪 شروع {len(test_questions)} مقایسه...")

    # اجرای مقایسه‌ها
    results = []
    for i, question in enumerate(test_questions, 1):
        print(f"\n🔄 مقایسه {i}/{len(test_questions)}...")
        result = await test.compare_retrieval(question)
        results.append(result)

    # نمایش خلاصه
    test.print_comparison_summary(results)

    # ذخیره نتایج
    test.save_results(results)

    print("\n🎉 تست مقایسه‌ای کامل انجام شد!")


if __name__ == "__main__":
    # اجرای تست
    asyncio.run(main())
