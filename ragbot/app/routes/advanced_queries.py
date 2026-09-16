"""Advanced query features handler."""

import asyncio

from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ragbot.configs.settings import settings
from ragbot.outputs.logger import logger

from .utils import (
    check_rate_limit,
    get_rag_service,
    is_user_authorized,
    safe_log_error,
    safe_reply,
)

router = Router()


@router.message(Command("aggregate"))
async def aggregate_handler(message: Message) -> None:
    """Handle aggregation queries."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="aggregate_query_start")
        logger.info("aggregate_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        # Parse aggregation query from message
        query_text = (
            message.text.replace("/aggregate", "").strip() if message.text else ""
        )
        if not query_text:
            error_msg = (
                "❓ لطفاً query aggregation خود را بعد از دستور /aggregate بنویسید.\n"
                "مثال: /aggregate group by source_type count"
                if settings.default_lang == "fa"
                else "❓ Please write your aggregation query after /aggregate command.\n"
                "Example: /aggregate group by source_type count"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "📊 در حال پردازش query aggregation..."
            if settings.default_lang == "fa"
            else "📊 Processing aggregation query..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use QueryAggregator for aggregation
        if hasattr(rag_service, "query_aggregator"):
            try:
                # Simple aggregation example
                if "count" in query_text.lower():
                    result = await rag_service.query_aggregator.count_by_date_range(
                        field="created_at",
                        start_date="2024-01-01",
                        end_date="2024-12-31",
                    )

                    response_msg = (
                        f"📊 نتیجه aggregation:\n"
                        f"تعداد اسناد: {result.total_count}\n"
                        f"تاریخ شروع: {result.start_date}\n"
                        f"تاریخ پایان: {result.end_date}"
                        if settings.default_lang == "fa"
                        else f"📊 Aggregation result:\n"
                        f"Total documents: {result.total_count}\n"
                        f"Start date: {result.start_date}\n"
                        f"End date: {result.end_date}"
                    )
                else:
                    response_msg = (
                        "❌ نوع aggregation پشتیبانی نشده. از 'count' استفاده کنید."
                        if settings.default_lang == "fa"
                        else "❌ Unsupported aggregation type. Use 'count'."
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Aggregation query failed: {e}")
                error_msg = (
                    f"❌ خطا در پردازش aggregation: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Aggregation processing error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت aggregation فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Aggregation feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "aggregate_handler")


@router.message(Command("filter"))
async def filter_handler(message: Message) -> None:
    """Handle advanced filtering queries."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="filter_query_start")
        logger.info("filter_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        # Parse filter query from message
        query_text = message.text.replace("/filter", "").strip() if message.text else ""
        if not query_text:
            error_msg = (
                "❓ لطفاً filter query خود را بعد از دستور /filter بنویسید.\n"
                "مثال: /filter date_range created_at 2024-01-01 2024-12-31"
                if settings.default_lang == "fa"
                else "❓ Please write your filter query after /filter command.\n"
                "Example: /filter date_range created_at 2024-01-01 2024-12-31"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "🔍 در حال پردازش filter query..."
            if settings.default_lang == "fa"
            else "🔍 Processing filter query..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use AdvancedFilter for filtering
        if hasattr(rag_service, "advanced_filter"):
            try:
                # Simple date range filter example
                if "date_range" in query_text.lower():
                    parts = query_text.split()
                    if len(parts) >= 4:
                        field = parts[1]
                        start_date = parts[2]
                        end_date = parts[3]

                        result = await rag_service.advanced_filter.date_range_filter(
                            field=field, start_date=start_date, end_date=end_date
                        )

                        response_msg = (
                            f"🔍 نتیجه filter:\n"
                            f"تعداد اسناد یافت شده: {len(result)}\n"
                            f"فیلد: {field}\n"
                            f"از تاریخ: {start_date}\n"
                            f"تا تاریخ: {end_date}"
                            if settings.default_lang == "fa"
                            else f"🔍 Filter result:\n"
                            f"Documents found: {len(result)}\n"
                            f"Field: {field}\n"
                            f"From: {start_date}\n"
                            f"To: {end_date}"
                        )
                    else:
                        response_msg = (
                            "❌ فرمت filter نادرست. از 'date_range field start_date end_date' استفاده کنید."
                            if settings.default_lang == "fa"
                            else "❌ Invalid filter format. Use 'date_range field start_date end_date'."
                        )
                else:
                    response_msg = (
                        "❌ نوع filter پشتیبانی نشده. از 'date_range' استفاده کنید."
                        if settings.default_lang == "fa"
                        else "❌ Unsupported filter type. Use 'date_range'."
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Filter query failed: {e}")
                error_msg = (
                    f"❌ خطا در پردازش filter: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Filter processing error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت advanced filtering فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Advanced filtering feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "filter_handler")


@router.message(Command("optimize"))
async def optimize_handler(message: Message) -> None:
    """Handle query optimization requests."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="optimize_query_start")
        logger.info("optimize_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        # Parse optimization query from message
        query_text = (
            message.text.replace("/optimize", "").strip() if message.text else ""
        )
        if not query_text:
            error_msg = (
                "❓ لطفاً query خود را بعد از دستور /optimize بنویسید.\n"
                "مثال: /optimize بهترین روش برای جستجوی اسناد"
                if settings.default_lang == "fa"
                else "❓ Please write your query after /optimize command.\n"
                "Example: /optimize best way to search documents"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "⚡ در حال بهینه‌سازی query..."
            if settings.default_lang == "fa"
            else "⚡ Optimizing query..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use QueryOptimizer for optimization
        if hasattr(rag_service, "query_optimizer"):
            try:
                result = await rag_service.query_optimizer.optimize_query(
                    query=query_text,
                    context={"user_id": user_id, "timestamp": start_time},
                )

                response_msg = (
                    f"⚡ نتیجه بهینه‌سازی:\n"
                    f"بهبود عملکرد: {result.improvement_percentage:.2f}%\n"
                    f"زمان اجرا: {result.execution_time:.3f}s\n"
                    f"استراتژی: {result.strategy.value}\n"
                    f"توصیه‌ها: {', '.join(result.recommendations[:3])}"
                    if settings.default_lang == "fa"
                    else f"⚡ Optimization result:\n"
                    f"Performance improvement: {result.improvement_percentage:.2f}%\n"
                    f"Execution time: {result.execution_time:.3f}s\n"
                    f"Strategy: {result.strategy.value}\n"
                    f"Recommendations: {', '.join(result.recommendations[:3])}"
                )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Query optimization failed: {e}")
                error_msg = (
                    f"❌ خطا در بهینه‌سازی query: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Query optimization error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت query optimization فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Query optimization feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "optimize_handler")


@router.message(Command("score"))
async def score_handler(message: Message) -> None:
    """Handle custom scoring requests."""
    user_id = message.from_user.id if message.from_user else 0
    start_time = asyncio.get_event_loop().time()

    try:
        logger.log_user_action(user_id=user_id, action="score_query_start")
        logger.info("score_handler invoked", user_id=user_id)

        if not is_user_authorized(user_id):
            msg = (
                "⛔ دسترسی غیرمجاز."
                if settings.default_lang == "fa"
                else "⛔ Unauthorized."
            )
            await safe_reply(message, msg)
            return

        if not check_rate_limit(user_id):
            msg = (
                "⏳ لطفاً بعداً تلاش کنید. محدودیت نرخ فعال است."
                if settings.default_lang == "fa"
                else "⏳ Please try again later. Rate limit exceeded."
            )
            await safe_reply(message, msg)
            return

        # Parse scoring query from message
        query_text = message.text.replace("/score", "").strip() if message.text else ""
        if not query_text:
            error_msg = (
                "❓ لطفاً query خود را بعد از دستور /score بنویسید.\n"
                "مثال: /score weighted semantic 0.6 time_decay 0.4"
                if settings.default_lang == "fa"
                else "❓ Please write your query after /score command.\n"
                "Example: /score weighted semantic 0.6 time_decay 0.4"
            )
            await safe_reply(message, error_msg)
            return

        processing_msg = (
            "🎯 در حال اعمال custom scoring..."
            if settings.default_lang == "fa"
            else "🎯 Applying custom scoring..."
        )
        await safe_reply(message, processing_msg)

        rag_service = await get_rag_service()

        # Use CustomScorer for scoring
        if hasattr(rag_service, "custom_scorer"):
            try:
                # Simple weighted scoring example
                if "weighted" in query_text.lower():
                    # Get some documents to score (mock data for demonstration)
                    from ragbot.rag import VectorDocument

                    mock_docs = [
                        VectorDocument(
                            id="doc1",
                            content="Sample document 1",
                            embedding=[0.1, 0.2, 0.3],
                            metadata={"created_at": "2024-01-01"},
                        ),
                        VectorDocument(
                            id="doc2",
                            content="Sample document 2",
                            embedding=[0.4, 0.5, 0.6],
                            metadata={"created_at": "2024-06-01"},
                        ),
                    ]

                    result = await rag_service.custom_scorer.weighted_scoring(
                        documents=mock_docs,
                        weights={"semantic": 0.6, "time_decay": 0.4},
                    )

                    response_msg = (
                        f"🎯 نتیجه custom scoring:\n"
                        f"تعداد اسناد scored: {len(result)}\n"
                        f"بالاترین امتیاز: {max(doc.final_score for doc in result):.3f}\n"
                        f"پایین‌ترین امتیاز: {min(doc.final_score for doc in result):.3f}"
                        if settings.default_lang == "fa"
                        else f"🎯 Custom scoring result:\n"
                        f"Documents scored: {len(result)}\n"
                        f"Highest score: {max(doc.final_score for doc in result):.3f}\n"
                        f"Lowest score: {min(doc.final_score for doc in result):.3f}"
                    )
                else:
                    response_msg = (
                        "❌ نوع scoring پشتیبانی نشده. از 'weighted' استفاده کنید."
                        if settings.default_lang == "fa"
                        else "❌ Unsupported scoring type. Use 'weighted'."
                    )

                await safe_reply(message, response_msg)

            except Exception as e:
                logger.error(f"Custom scoring failed: {e}")
                error_msg = (
                    f"❌ خطا در custom scoring: {str(e)}"
                    if settings.default_lang == "fa"
                    else f"❌ Custom scoring error: {str(e)}"
                )
                await safe_reply(message, error_msg)
        else:
            error_msg = (
                "❌ قابلیت custom scoring فعال نیست."
                if settings.default_lang == "fa"
                else "❌ Custom scoring feature is not enabled."
            )
            await safe_reply(message, error_msg)

    except Exception as e:
        await safe_log_error(e, message, "score_handler")
