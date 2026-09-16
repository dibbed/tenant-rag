#!/usr/bin/env python3
"""
RAG Telegram Assistant - Advanced Test Script
این اسکریپت تمام مراحل RAG پیشرفته را انجام می‌دهد و خروجی کامل ارائه می‌دهد
شامل تست: Reranking, Hybrid Search, Query Expansion, Performance Analysis
"""

import asyncio
import json
import statistics
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


class AdvancedRAGTest:
    """کلاس پیشرفته برای تست RAG با قابلیت‌های جدید"""

    def __init__(self):
        self.integration_service = None
        self.rag_service = None
        self.start_time = None
        self.output_dir = Path("advanced_rag_test_outputs")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.test_results = []
        self.performance_metrics = {}

    async def initialize_system(self) -> bool:
        """مقداردهی اولیه سیستم"""
        try:
            logger.info("🚀 شروع مقداردهی سیستم RAG پیشرفته...")
            self.start_time = time.time()

            # مقداردهی Integration Service
            self.integration_service = IntegrationService()
            await self.integration_service.initialize()

            # دریافت RAG Service
            self.rag_service = self.integration_service.components["rag_service"]

            init_time = time.time() - self.start_time
            logger.info(
                f"✅ سیستم RAG پیشرفته با موفقیت مقداردهی شد! ({init_time:.2f}s)"
            )

            return True

        except Exception as e:
            logger.error(f"❌ خطا در مقداردهی سیستم: {e}")
            return False

    async def test_basic_retrieval(self, question: str) -> Dict[str, Any]:
        """تست جستجوی پایه"""
        try:
            logger.info(f"🔍 تست جستجوی پایه: {question}")
            start_time = time.time()

            # جستجوی پایه
            result = await self.rag_service.query_documents(question)

            processing_time = time.time() - start_time

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
            logger.error(f"❌ خطا در تست جستجوی پایه: {e}")
            return {
                "type": "basic",
                "question": question,
                "answer": f"خطا در پردازش: {str(e)}",
                "sources": [],
                "processing_time": 0,
                "answer_length": 0,
                "source_count": 0,
                "success": False,
            }

    async def test_advanced_retrieval(self, question: str) -> Dict[str, Any]:
        """تست جستجوی پیشرفته با Advanced Retrieval"""
        try:
            logger.info(f"🚀 تست جستجوی پیشرفته: {question}")
            start_time = time.time()

            # بررسی وجود Advanced Retriever
            if (
                hasattr(self.rag_service, "advanced_retriever")
                and self.rag_service.advanced_retriever
            ):
                logger.info("✅ Advanced Retriever فعال است")

                # تست با Advanced Retrieval
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
                    "advanced_features": {
                        "reranking_enabled": settings.advanced_retrieval.enable_reranking,
                        "hybrid_search_enabled": settings.advanced_retrieval.enable_hybrid_search,
                        "query_expansion_enabled": settings.advanced_retrieval.enable_query_expansion,
                    },
                }
            else:
                logger.warning("⚠️ Advanced Retriever فعال نیست")
                return await self.test_basic_retrieval(question)

        except Exception as e:
            logger.error(f"❌ خطا در تست جستجوی پیشرفته: {e}")
            return {
                "type": "advanced",
                "question": question,
                "answer": f"خطا در پردازش: {str(e)}",
                "sources": [],
                "processing_time": 0,
                "answer_length": 0,
                "source_count": 0,
                "success": False,
            }

    async def test_performance_comparison(self, question: str) -> Dict[str, Any]:
        """تست مقایسه عملکرد"""
        try:
            logger.info(f"⚡ تست مقایسه عملکرد: {question}")

            # تست جستجوی پایه
            basic_result = await self.test_basic_retrieval(question)

            # تست جستجوی پیشرفته
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

                return {
                    "type": "comparison",
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
                return {
                    "type": "comparison",
                    "question": question,
                    "basic": basic_result,
                    "advanced": advanced_result,
                    "improvements": None,
                    "success": False,
                }

        except Exception as e:
            logger.error(f"❌ خطا در تست مقایسه عملکرد: {e}")
            return {
                "type": "comparison",
                "question": question,
                "basic": None,
                "advanced": None,
                "improvements": None,
                "success": False,
            }

    async def test_query_expansion(self, question: str) -> Dict[str, Any]:
        """تست گسترش پرسش"""
        try:
            logger.info(f"🔍 تست گسترش پرسش: {question}")

            # بررسی وجود Query Expander
            if (
                hasattr(self.rag_service, "advanced_retriever")
                and self.rag_service.advanced_retriever
                and self.rag_service.advanced_retriever.query_expander
            ):
                # تست گسترش پرسش
                expanded_queries = await self.rag_service.advanced_retriever.query_expander.expand_query(
                    question
                )

                return {
                    "type": "query_expansion",
                    "original_question": question,
                    "expanded_queries": expanded_queries,
                    "expansion_count": len(expanded_queries),
                    "success": True,
                }
            else:
                return {
                    "type": "query_expansion",
                    "original_question": question,
                    "expanded_queries": [],
                    "expansion_count": 0,
                    "success": False,
                    "error": "Query Expander فعال نیست",
                }

        except Exception as e:
            logger.error(f"❌ خطا در تست گسترش پرسش: {e}")
            return {
                "type": "query_expansion",
                "original_question": question,
                "expanded_queries": [],
                "expansion_count": 0,
                "success": False,
                "error": str(e),
            }

    def print_system_info(self):
        """نمایش اطلاعات سیستم"""
        print("\n" + "=" * 80)
        print("🔧 اطلاعات سیستم RAG پیشرفته")
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

        # اطلاعات Advanced Retrieval
        print("\n🚀 Advanced Retrieval Settings:")
        print(f"  🔄 Reranking: {settings.advanced_retrieval.enable_reranking}")
        print(f"  🔍 Hybrid Search: {settings.advanced_retrieval.enable_hybrid_search}")
        print(
            f"  📝 Query Expansion: {settings.advanced_retrieval.enable_query_expansion}"
        )
        print(f"  🎯 Reranker Model: {settings.advanced_retrieval.reranker_model}")
        print(f"  📊 Hybrid Alpha: {settings.advanced_retrieval.hybrid_alpha}")
        print(
            f"  🔢 Max Expanded Queries: {settings.advanced_retrieval.max_expanded_queries}"
        )

        print("\n" + "=" * 80)

    def create_output_directory(self):
        """ایجاد پوشه خروجی"""
        self.output_dir.mkdir(exist_ok=True)
        print(f"📁 پوشه خروجی: {self.output_dir}")

    def save_system_info(self):
        """ذخیره اطلاعات سیستم"""
        system_file = self.output_dir / f"system_info_{self.timestamp}.txt"

        with open(system_file, "w", encoding="utf-8") as f:
            f.write("🔧 اطلاعات سیستم RAG پیشرفته\n")
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

            f.write("\n🚀 Advanced Retrieval Settings:\n")
            f.write(f"  🔄 Reranking: {settings.advanced_retrieval.enable_reranking}\n")
            f.write(
                f"  🔍 Hybrid Search: {settings.advanced_retrieval.enable_hybrid_search}\n"
            )
            f.write(
                f"  📝 Query Expansion: {settings.advanced_retrieval.enable_query_expansion}\n"
            )
            f.write(
                f"  🎯 Reranker Model: {settings.advanced_retrieval.reranker_model}\n"
            )
            f.write(f"  📊 Hybrid Alpha: {settings.advanced_retrieval.hybrid_alpha}\n")
            f.write(
                f"  🔢 Max Expanded Queries: {settings.advanced_retrieval.max_expanded_queries}\n"
            )

            f.write(f"\n⏰ زمان تست: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

        print(f"💾 اطلاعات سیستم ذخیره شد: {system_file}")

    def save_test_result(self, result: Dict[str, Any], test_num: int):
        """ذخیره نتیجه یک تست"""
        test_file = self.output_dir / f"test_{test_num:02d}_{self.timestamp}.txt"

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(f"🧪 تست {test_num}: {result['type']}\n")
            f.write("-" * 80 + "\n\n")

            if result["type"] == "comparison":
                f.write(f"📝 سوال: {result['question']}\n\n")

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
                    f.write("=" * 40 + "\n")
                else:
                    f.write("❌ خطا در مقایسه\n")

            elif result["type"] == "query_expansion":
                f.write(f"📝 سوال اصلی: {result['original_question']}\n\n")

                if result["success"]:
                    f.write(f"✅ گسترش موفق! ({result['expansion_count']} پرسش)\n\n")
                    f.write("🔍 پرسش‌های گسترش یافته:\n")
                    for i, query in enumerate(result["expanded_queries"], 1):
                        f.write(f"  {i}. {query}\n")
                else:
                    f.write("❌ خطا در گسترش\n")
                    f.write(f"💬 پیام خطا: {result.get('error', 'نامشخص')}\n")

            else:
                f.write(f"📝 سوال: {result['question']}\n\n")

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

        print(f"💾 تست {test_num} ذخیره شد: {test_file}")

    def save_performance_analysis(self, results: List[Dict[str, Any]]):
        """ذخیره تحلیل عملکرد"""
        analysis_file = self.output_dir / f"performance_analysis_{self.timestamp}.json"

        # محاسبه آمار
        basic_times = [
            r["processing_time"]
            for r in results
            if r["type"] == "basic" and r["success"]
        ]
        advanced_times = [
            r["processing_time"]
            for r in results
            if r["type"] == "advanced" and r["success"]
        ]
        comparison_results = [
            r for r in results if r["type"] == "comparison" and r["success"]
        ]

        analysis = {
            "timestamp": self.timestamp,
            "total_tests": len(results),
            "successful_tests": sum(1 for r in results if r["success"]),
            "failed_tests": sum(1 for r in results if not r["success"]),
            "performance_metrics": {
                "basic_retrieval": {
                    "count": len(basic_times),
                    "avg_time": statistics.mean(basic_times) if basic_times else 0,
                    "min_time": min(basic_times) if basic_times else 0,
                    "max_time": max(basic_times) if basic_times else 0,
                },
                "advanced_retrieval": {
                    "count": len(advanced_times),
                    "avg_time": statistics.mean(advanced_times)
                    if advanced_times
                    else 0,
                    "min_time": min(advanced_times) if advanced_times else 0,
                    "max_time": max(advanced_times) if advanced_times else 0,
                },
                "comparison": {
                    "count": len(comparison_results),
                    "avg_time_improvement": statistics.mean(
                        [
                            r["improvements"]["time_improvement_percent"]
                            for r in comparison_results
                        ]
                    )
                    if comparison_results
                    else 0,
                    "avg_length_improvement": statistics.mean(
                        [
                            r["improvements"]["length_improvement_percent"]
                            for r in comparison_results
                        ]
                    )
                    if comparison_results
                    else 0,
                },
            },
            "advanced_features_status": {
                "reranking_enabled": settings.advanced_retrieval.enable_reranking,
                "hybrid_search_enabled": settings.advanced_retrieval.enable_hybrid_search,
                "query_expansion_enabled": settings.advanced_retrieval.enable_query_expansion,
            },
            "test_results": results,
        }

        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

        print(f"💾 تحلیل عملکرد ذخیره شد: {analysis_file}")

    def print_test_result(self, result: Dict[str, Any]):
        """نمایش نتیجه تست"""
        print(f"\n🧪 تست: {result['type']}")
        print("-" * 80)

        if result["type"] == "comparison":
            print(f"📝 سوال: {result['question']}")

            if result["success"]:
                print("✅ مقایسه موفق!")
                print(
                    f"🔍 پایه: {result['basic']['processing_time']:.2f}s | {result['basic']['answer_length']} chars"
                )
                print(
                    f"🚀 پیشرفته: {result['advanced']['processing_time']:.2f}s | {result['advanced']['answer_length']} chars"
                )
                print(
                    f"📊 بهبود زمان: {result['improvements']['time_improvement_percent']:.1f}%"
                )
                print(
                    f"📏 بهبود طول: {result['improvements']['length_improvement_percent']:.1f}%"
                )
            else:
                print("❌ خطا در مقایسه")

        elif result["type"] == "query_expansion":
            print(f"📝 سوال اصلی: {result['original_question']}")

            if result["success"]:
                print(f"✅ گسترش موفق! ({result['expansion_count']} پرسش)")
                for i, query in enumerate(result["expanded_queries"], 1):
                    print(f"  {i}. {query}")
            else:
                print("❌ خطا در گسترش")
                print(f"💬 پیام خطا: {result.get('error', 'نامشخص')}")

        else:
            print(f"📝 سوال: {result['question']}")

            if result["success"]:
                print(f"✅ موفقیت! ({result['processing_time']:.2f}s)")
                print(f"📊 طول پاسخ: {result['answer_length']} کاراکتر")
                print(f"📚 تعداد منابع: {result['source_count']}")
                print(f"\n💬 پاسخ: {result['answer'][:200]}...")
            else:
                print("❌ خطا در پردازش")
                print(f"💬 پیام خطا: {result['answer']}")

        print("-" * 80)

    def print_performance_summary(self, results: List[Dict[str, Any]]):
        """نمایش خلاصه عملکرد"""
        total_time = time.time() - self.start_time
        successful = sum(1 for r in results if r["success"])
        failed = len(results) - successful

        print("\n" + "=" * 80)
        print("📊 خلاصه عملکرد RAG پیشرفته")
        print("=" * 80)

        print(f"⏱️  کل زمان: {total_time:.2f} ثانیه")
        print(f"✅ موفق: {successful}")
        print(f"❌ ناموفق: {failed}")
        print(f"📝 کل تست‌ها: {len(results)}")

        # آمار تفصیلی
        basic_times = [
            r["processing_time"]
            for r in results
            if r["type"] == "basic" and r["success"]
        ]
        advanced_times = [
            r["processing_time"]
            for r in results
            if r["type"] == "advanced" and r["success"]
        ]
        comparison_results = [
            r for r in results if r["type"] == "comparison" and r["success"]
        ]

        if basic_times:
            print("\n🔍 جستجوی پایه:")
            print(f"  ⚡ میانگین زمان: {statistics.mean(basic_times):.2f}s")
            print(f"  📊 تعداد تست: {len(basic_times)}")

        if advanced_times:
            print("\n🚀 جستجوی پیشرفته:")
            print(f"  ⚡ میانگین زمان: {statistics.mean(advanced_times):.2f}s")
            print(f"  📊 تعداد تست: {len(advanced_times)}")

        if comparison_results:
            avg_time_improvement = statistics.mean(
                [
                    r["improvements"]["time_improvement_percent"]
                    for r in comparison_results
                ]
            )
            avg_length_improvement = statistics.mean(
                [
                    r["improvements"]["length_improvement_percent"]
                    for r in comparison_results
                ]
            )
            print("\n📊 مقایسه عملکرد:")
            print(f"  ⚡ بهبود زمان: {avg_time_improvement:.1f}%")
            print(f"  📏 بهبود طول: {avg_length_improvement:.1f}%")
            print(f"  📊 تعداد مقایسه: {len(comparison_results)}")

        print("=" * 80)


async def main():
    """تابع اصلی"""
    print("🚀 RAG Telegram Assistant - Advanced Test")
    print("=" * 80)

    # ایجاد instance
    test = AdvancedRAGTest()

    # ایجاد پوشه خروجی
    test.create_output_directory()

    # مقداردهی سیستم
    if not await test.initialize_system():
        print("❌ خطا در مقداردهی سیستم!")
        return

    # نمایش و ذخیره اطلاعات سیستم
    test.print_system_info()
    test.save_system_info()

    # تست‌های مختلف
    test_scenarios = [
        {
            "name": "تست جستجوی پایه",
            "questions": [
                "این پروژه RAG Telegram Assistant چه کاری انجام می‌دهد؟",
                "معماری RAG در این پروژه چطور پیاده‌سازی شده؟",
            ],
            "test_func": test.test_basic_retrieval,
        },
        {
            "name": "تست جستجوی پیشرفته",
            "questions": [
                "چرا از FAISS برای vector storage استفاده شده؟",
                "تنظیمات .env_deepseek چه مزایایی داره؟",
            ],
            "test_func": test.test_advanced_retrieval,
        },
        {
            "name": "تست مقایسه عملکرد",
            "questions": [
                "سیستم caching در این پروژه چطور کار می‌کنه؟",
                "Advanced Retrieval چه قابلیت‌هایی داره؟",
            ],
            "test_func": test.test_performance_comparison,
        },
        {
            "name": "تست گسترش پرسش",
            "questions": [
                "RAG چیست؟",
                "vector database چطور کار می‌کنه؟",
            ],
            "test_func": test.test_query_expansion,
        },
    ]

    print(f"\n🧪 شروع {len(test_scenarios)} نوع تست...")

    # اجرای تست‌ها
    all_results = []
    test_counter = 1

    for scenario in test_scenarios:
        print(f"\n🔄 {scenario['name']}...")

        for question in scenario["questions"]:
            print(f"\n  📝 تست {test_counter}: {question[:50]}...")
            result = await scenario["test_func"](question)
            all_results.append(result)
            test.print_test_result(result)
            test.save_test_result(result, test_counter)
            test_counter += 1

    # نمایش و ذخیره خلاصه
    test.print_performance_summary(all_results)
    test.save_performance_analysis(all_results)

    print("\n🎉 تست پیشرفته کامل انجام شد!")
    print(f"📁 تمام فایل‌ها در پوشه {test.output_dir} ذخیره شدند")
    print(f"📊 {len(all_results)} تست انجام شد")


if __name__ == "__main__":
    # اجرای تست
    asyncio.run(main())
