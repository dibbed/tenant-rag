#!/usr/bin/env python3
"""
RAG Telegram Assistant - Complete Test Script
این اسکریپت تمام مراحل RAG را انجام می‌دهد و خروجی کامل ارائه می‌دهد
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# اضافه کردن مسیر پروژه
sys.path.insert(0, str(Path(__file__).parent))

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger
from ragbot.services.integration_service import IntegrationService


class CompleteRAGTest:
    """کلاس کامل برای تست RAG"""

    def __init__(self):
        self.integration_service = None
        self.rag_service = None
        self.start_time = None
        self.output_dir = Path("rag_test_outputs")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    async def initialize_system(self) -> bool:
        """مقداردهی اولیه سیستم"""
        try:
            logger.info("🚀 شروع مقداردهی سیستم RAG...")
            self.start_time = time.time()

            # مقداردهی Integration Service
            self.integration_service = IntegrationService()
            await self.integration_service.initialize()

            # دریافت RAG Service
            self.rag_service = self.integration_service.components["rag_service"]

            init_time = time.time() - self.start_time
            logger.info(f"✅ سیستم RAG با موفقیت مقداردهی شد! ({init_time:.2f}s)")

            return True

        except Exception as e:
            logger.error(f"❌ خطا در مقداردهی سیستم: {e}")
            return False

    async def process_question(self, question: str) -> Dict[str, Any]:
        """پردازش کامل یک سوال"""
        try:
            logger.info(f"📝 پردازش سوال: {question}")
            question_start = time.time()

            # پردازش سوال
            result = await self.rag_service.query_documents(question)

            question_time = time.time() - question_start

            # تحلیل نتیجه
            analysis = {
                "question": question,
                "answer": result.answer,
                "sources": result.sources,
                "processing_time": question_time,
                "answer_length": len(result.answer),
                "source_count": len(result.sources),
                "success": True,
            }

            logger.info(f"✅ سوال پردازش شد! ({question_time:.2f}s)")
            return analysis

        except Exception as e:
            logger.error(f"❌ خطا در پردازش سوال: {e}")
            return {
                "question": question,
                "answer": f"خطا در پردازش: {str(e)}",
                "sources": [],
                "processing_time": 0,
                "answer_length": 0,
                "source_count": 0,
                "success": False,
            }

    def print_system_info(self):
        """نمایش اطلاعات سیستم"""
        print("\n" + "=" * 80)
        print("🔧 اطلاعات سیستم RAG")
        print("=" * 80)

        print(f"🤖 LLM Model: {settings.llm.model}")
        print(f"🔍 Embedding Model: {settings.embedding.model}")
        print(f"📊 Chunk Size: {settings.rag.chunk_size}")
        print(f"🎯 Top K: {settings.rag.top_k}")
        print(f"📏 Similarity Threshold: {settings.rag.similarity_threshold}")
        print(f"⚡ Batch Size: {settings.embedding.batch_size}")
        print(f"🔄 Cache TTL: {settings.cache_ttl}")
        print(f"🚀 Redis Enabled: {settings.enable_redis}")
        print(f"🐛 Debug Mode: {settings.debug}")

        print("\n" + "=" * 80)

    def create_output_directory(self):
        """ایجاد پوشه خروجی"""
        self.output_dir.mkdir(exist_ok=True)
        print(f"📁 پوشه خروجی: {self.output_dir}")

    def save_system_info(self):
        """ذخیره اطلاعات سیستم"""
        system_file = self.output_dir / f"system_info_{self.timestamp}.txt"

        with open(system_file, "w", encoding="utf-8") as f:
            f.write("🔧 اطلاعات سیستم RAG\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"🤖 LLM Model: {settings.llm.model}\n")
            f.write(f"🔍 Embedding Model: {settings.embedding.model}\n")
            f.write(f"📊 Chunk Size: {settings.rag.chunk_size}\n")
            f.write(f"🎯 Top K: {settings.rag.top_k}\n")
            f.write(f"📏 Similarity Threshold: {settings.rag.similarity_threshold}\n")
            f.write(f"⚡ Batch Size: {settings.embedding.batch_size}\n")
            f.write(f"🔄 Cache TTL: {settings.cache_ttl}\n")
            f.write(f"🚀 Redis Enabled: {settings.enable_redis}\n")
            f.write(f"🐛 Debug Mode: {settings.debug}\n")
            f.write(f"⏰ زمان تست: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print(f"💾 اطلاعات سیستم ذخیره شد: {system_file}")

    def save_question_result(self, result: Dict[str, Any], question_num: int):
        """ذخیره نتیجه یک سوال"""
        question_file = (
            self.output_dir / f"question_{question_num:02d}_{self.timestamp}.txt"
        )

        with open(question_file, "w", encoding="utf-8") as f:
            f.write(f"📝 سوال {question_num}: {result['question']}\n")
            f.write("-" * 80 + "\n\n")

            if result["success"]:
                f.write(f"✅ موفقیت! ({result['processing_time']:.2f}s)\n")
                f.write(f"📊 طول پاسخ: {result['answer_length']} کاراکتر\n")
                f.write(f"📚 تعداد منابع: {result['source_count']}\n\n")

                f.write("💬 پاسخ:\n")
                f.write("=" * 40 + "\n")
                f.write(result["answer"] + "\n")
                f.write("=" * 40 + "\n\n")

                if result["sources"]:
                    f.write("📚 منابع:\n")
                    for i, source in enumerate(result["sources"], 1):
                        f.write(f"  {i}. {source}\n")
            else:
                f.write("❌ خطا در پردازش\n")
                f.write(f"💬 پیام خطا: {result['answer']}\n")

        print(f"💾 سوال {question_num} ذخیره شد: {question_file}")

    def save_summary(self, results: List[Dict[str, Any]]):
        """ذخیره خلاصه نتایج"""
        summary_file = self.output_dir / f"summary_{self.timestamp}.txt"

        total_time = time.time() - self.start_time
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("📊 خلاصه نتایج\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"⏱️  کل زمان: {total_time:.2f} ثانیه\n")
            f.write(f"✅ موفق: {successful}\n")
            f.write(f"❌ ناموفق: {failed}\n")
            f.write(f"📝 کل سوالات: {len(results)}\n\n")

            if successful > 0:
                avg_time = (
                    sum(r["processing_time"] for r in results if r["success"])
                    / successful
                )
                avg_length = (
                    sum(r["answer_length"] for r in results if r["success"])
                    / successful
                )
                f.write(f"⚡ میانگین زمان پردازش: {avg_time:.2f} ثانیه\n")
                f.write(f"📏 میانگین طول پاسخ: {avg_length:.0f} کاراکتر\n\n")

            f.write("📋 لیست سوالات:\n")
            f.write("-" * 40 + "\n")
            for i, result in enumerate(results, 1):
                status = "✅" if result["success"] else "❌"
                f.write(f"{i:2d}. {status} {result['question']}\n")
                if result["success"]:
                    f.write(
                        f"    ⏱️  {result['processing_time']:.2f}s | 📏 {result['answer_length']} chars\n"
                    )
                else:
                    f.write(f"    ❌ خطا: {result['answer']}\n")

        print(f"💾 خلاصه ذخیره شد: {summary_file}")

    def print_question_result(self, result: Dict[str, Any]):
        """نمایش نتیجه سوال"""
        print(f"\n📝 سوال: {result['question']}")
        print("-" * 80)

        if result["success"]:
            print(f"✅ موفقیت! ({result['processing_time']:.2f}s)")
            print(f"📊 طول پاسخ: {result['answer_length']} کاراکتر")
            print(f"📚 تعداد منابع: {result['source_count']}")

            print("\n💬 پاسخ:")
            print(result["answer"])

            if result["sources"]:
                print("\n📚 منابع:")
                for i, source in enumerate(result["sources"], 1):
                    print(f"  {i}. {source}")
        else:
            print("❌ خطا در پردازش")
            print(f"💬 پیام خطا: {result['answer']}")

        print("-" * 80)

    def print_summary(self, results: List[Dict[str, Any]]):
        """نمایش خلاصه نتایج"""
        total_time = time.time() - self.start_time
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        print("\n" + "=" * 80)
        print("📊 خلاصه نتایج")
        print("=" * 80)

        print(f"⏱️  کل زمان: {total_time:.2f} ثانیه")
        print(f"✅ موفق: {successful}")
        print(f"❌ ناموفق: {failed}")
        print(f"📝 کل سوالات: {len(results)}")

        if successful > 0:
            avg_time = (
                sum(r["processing_time"] for r in results if r["success"]) / successful
            )
            avg_length = (
                sum(r["answer_length"] for r in results if r["success"]) / successful
            )
            print(f"⚡ میانگین زمان پردازش: {avg_time:.2f} ثانیه")
            print(f"📏 میانگین طول پاسخ: {avg_length:.0f} کاراکتر")

        print("=" * 80)


async def main():
    """تابع اصلی"""
    print("🚀 RAG Telegram Assistant - Complete Test")
    print("=" * 80)

    # ایجاد instance
    test = CompleteRAGTest()

    # ایجاد پوشه خروجی
    test.create_output_directory()

    # مقداردهی سیستم
    if not await test.initialize_system():
        print("❌ خطا در مقداردهی سیستم!")
        return

    # نمایش و ذخیره اطلاعات سیستم
    test.print_system_info()
    test.save_system_info()

    # سوالات تست
    test_questions = [
        "این پروژه RAG Telegram Assistant چه کاری انجام می‌دهد؟",
        "معماری RAG در این پروژه چطور پیاده‌سازی شده؟",
        "چرا از FAISS برای vector storage استفاده شده؟",
        "تنظیمات .env_deepseek چه مزایایی داره؟",
        "سیستم caching در این پروژه چطور کار می‌کنه؟",
    ]

    print(f"\n📝 شروع پردازش {len(test_questions)} سوال...")

    # پردازش سوالات
    results = []
    for i, question in enumerate(test_questions, 1):
        print(f"\n🔄 پردازش سوال {i}/{len(test_questions)}...")
        result = await test.process_question(question)
        results.append(result)
        test.print_question_result(result)
        test.save_question_result(result, i)

    # نمایش و ذخیره خلاصه
    test.print_summary(results)
    test.save_summary(results)

    print("\n🎉 تست کامل انجام شد!")
    print(f"📁 تمام فایل‌ها در پوشه {test.output_dir} ذخیره شدند")


if __name__ == "__main__":
    # اجرای تست
    asyncio.run(main())
