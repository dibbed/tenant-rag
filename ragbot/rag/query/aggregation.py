"""
Complex Aggregation Engine

This module provides advanced aggregation capabilities for vector store queries,
including statistical operations, grouping, and complex data analysis.
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import statistics
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AggregationType(Enum):
    """انواع عملیات جمع‌آوری"""

    COUNT = "count"
    SUM = "sum"
    AVG = "average"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"
    STD_DEV = "std_dev"
    PERCENTILE = "percentile"
    VARIANCE = "variance"
    MODE = "mode"
    RANGE = "range"


@dataclass
class AggregationQuery:
    """ساختار پرسش جمع‌آوری"""

    field: str
    operation: AggregationType
    filters: Optional[Dict[str, Any]] = None
    group_by: Optional[List[str]] = None
    having: Optional[Dict[str, Any]] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    percentile: Optional[float] = None  # برای percentile operations


@dataclass
class AggregationResult:
    """نتیجه عملیات جمع‌آوری"""

    data: Dict[str, Any]
    total_count: int
    execution_time: float
    metadata: Dict[str, Any]
    groups: Optional[Dict[str, Any]] = None


class QueryAggregator:
    """موتور جمع‌آوری پیچیده برای پرسش‌های آماری"""

    def __init__(self, vector_store):
        """Initialize aggregator with vector store reference"""
        self.vector_store = vector_store
        self.cache = {}  # برای caching نتایج
        self.cache_ttl = 300  # 5 minutes

    async def group_by_metadata(
        self,
        field: str,
        filters: Optional[Dict] = None,
        aggregation: AggregationType = AggregationType.COUNT,
    ) -> Dict[str, Union[int, float]]:
        """
        گروه‌بندی اسناد بر اساس metadata field

        Args:
            field: نام فیلد metadata برای گروه‌بندی
            filters: فیلترهای اضافی
            aggregation: نوع عملیات جمع‌آوری

        Returns:
            Dictionary با کلیدهای گروه و مقادیر جمع‌آوری شده
        """
        start_time = time.time()

        # دریافت همه اسناد با فیلتر
        documents = await self._get_filtered_documents(filters)

        # گروه‌بندی بر اساس field
        groups = {}
        for doc in documents:
            if hasattr(doc, "metadata") and field in doc.metadata:
                value = doc.metadata[field]
                if value not in groups:
                    groups[value] = []
                groups[value].append(doc)

        # اعمال عملیات جمع‌آوری
        result = {}
        for group_key, group_docs in groups.items():
            if aggregation == AggregationType.COUNT:
                result[group_key] = len(group_docs)
            elif aggregation == AggregationType.SUM:
                # فرض: فیلد score برای جمع
                result[group_key] = sum(getattr(doc, "score", 0) for doc in group_docs)
            elif aggregation == AggregationType.AVG:
                scores = [getattr(doc, "score", 0) for doc in group_docs]
                result[group_key] = statistics.mean(scores) if scores else 0
            elif aggregation == AggregationType.MIN:
                scores = [getattr(doc, "score", 0) for doc in group_docs]
                result[group_key] = min(scores) if scores else 0
            elif aggregation == AggregationType.MAX:
                scores = [getattr(doc, "score", 0) for doc in group_docs]
                result[group_key] = max(scores) if scores else 0
            elif aggregation == AggregationType.MEDIAN:
                scores = [getattr(doc, "score", 0) for doc in group_docs]
                result[group_key] = statistics.median(scores) if scores else 0
            elif aggregation == AggregationType.STD_DEV:
                scores = [getattr(doc, "score", 0) for doc in group_docs]
                result[group_key] = statistics.stdev(scores) if len(scores) > 1 else 0
            elif aggregation == AggregationType.VARIANCE:
                scores = [getattr(doc, "score", 0) for doc in group_docs]
                result[group_key] = (
                    statistics.variance(scores) if len(scores) > 1 else 0
                )

        execution_time = time.time() - start_time
        logger.info(f"Group by {field} completed in {execution_time:.3f}s")

        return result

    async def count_by_date_range(
        self, start_date: str, end_date: str, date_field: str = "created_at"
    ) -> int:
        """
        شمارش اسناد در بازه زمانی مشخص

        Args:
            start_date: تاریخ شروع (YYYY-MM-DD)
            end_date: تاریخ پایان (YYYY-MM-DD)
            date_field: نام فیلد تاریخ در metadata

        Returns:
            تعداد اسناد در بازه زمانی
        """
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        documents = await self._get_filtered_documents(
            {date_field: {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}}
        )

        return len(documents)

    async def aggregate_scores(
        self, aggregation_type: AggregationType, filters: Optional[Dict] = None
    ) -> float:
        """
        جمع‌آوری امتیازات اسناد

        Args:
            aggregation_type: نوع عملیات (AVG, SUM, MIN, MAX, etc.)
            filters: فیلترهای اضافی

        Returns:
            نتیجه عملیات جمع‌آوری
        """
        documents = await self._get_filtered_documents(filters)
        scores = [getattr(doc, "score", 0) for doc in documents]

        if not scores:
            return 0.0

        if aggregation_type == AggregationType.SUM:
            return sum(scores)
        elif aggregation_type == AggregationType.AVG:
            return statistics.mean(scores)
        elif aggregation_type == AggregationType.MIN:
            return min(scores)
        elif aggregation_type == AggregationType.MAX:
            return max(scores)
        elif aggregation_type == AggregationType.MEDIAN:
            return statistics.median(scores)
        elif aggregation_type == AggregationType.STD_DEV:
            return statistics.stdev(scores) if len(scores) > 1 else 0.0
        elif aggregation_type == AggregationType.VARIANCE:
            return statistics.variance(scores) if len(scores) > 1 else 0.0
        elif aggregation_type == AggregationType.PERCENTILE:
            # استفاده از percentile پیش‌فرض 50 (median)
            return (
                statistics.quantiles(scores, n=100)[49]
                if len(scores) > 1
                else scores[0]
            )

        return 0.0

    async def statistical_summary(
        self, field: str, filters: Optional[Dict] = None
    ) -> Dict[str, float]:
        """
        خلاصه آماری برای یک فیلد

        Args:
            field: نام فیلد برای تحلیل
            filters: فیلترهای اضافی

        Returns:
            Dictionary با آمارهای مختلف
        """
        documents = await self._get_filtered_documents(filters)
        values = []

        for doc in documents:
            if hasattr(doc, "metadata") and field in doc.metadata:
                try:
                    value = float(doc.metadata[field])
                    values.append(value)
                except (ValueError, TypeError):
                    continue

        if not values:
            return {}

        return {
            "count": len(values),
            "sum": sum(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0.0,
            "variance": statistics.variance(values) if len(values) > 1 else 0.0,
            "range": max(values) - min(values),
        }

    async def execute_aggregation_query(
        self, query: AggregationQuery
    ) -> AggregationResult:
        """
        اجرای پرسش جمع‌آوری پیچیده

        Args:
            query: پرسش جمع‌آوری

        Returns:
            نتیجه کامل عملیات
        """
        start_time = time.time()

        # اعمال فیلترها
        documents = await self._get_filtered_documents(query.filters)

        # گروه‌بندی اگر لازم باشد
        if query.group_by:
            result_data = await self._group_and_aggregate(documents, query)
        else:
            # عملیات ساده روی کل مجموعه
            result_data = await self._simple_aggregate(documents, query)

        execution_time = time.time() - start_time

        return AggregationResult(
            data=result_data,
            total_count=len(documents),
            execution_time=execution_time,
            metadata={"query": query.__dict__, "timestamp": datetime.now().isoformat()},
        )

    async def percentile_analysis(
        self,
        field: str,
        percentiles: List[float] = None,
        filters: Optional[Dict] = None,
    ) -> Dict[str, float]:
        """
        تحلیل percentile برای یک فیلد

        Args:
            field: نام فیلد
            percentiles: لیست percentile ها
            filters: فیلترهای اضافی

        Returns:
            Dictionary با percentile ها
        """
        if percentiles is None:
            percentiles = [25, 50, 75, 90, 95, 99]

        documents = await self._get_filtered_documents(filters)
        values = []

        for doc in documents:
            if hasattr(doc, "metadata") and field in doc.metadata:
                try:
                    value = float(doc.metadata[field])
                    values.append(value)
                except (ValueError, TypeError):
                    continue

        if not values:
            return {}

        values.sort()
        result = {}

        for p in percentiles:
            if 0 <= p <= 100:
                index = int((p / 100) * (len(values) - 1))
                result[f"p{p}"] = values[index]

        return result

    async def mode_analysis(
        self, field: str, filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        تحلیل mode (بیشترین تکرار) برای یک فیلد

        Args:
            field: نام فیلد
            filters: فیلترهای اضافی

        Returns:
            Dictionary با mode و frequency
        """
        documents = await self._get_filtered_documents(filters)
        value_counts = {}

        for doc in documents:
            if hasattr(doc, "metadata") and field in doc.metadata:
                value = doc.metadata[field]
                value_counts[value] = value_counts.get(value, 0) + 1

        if not value_counts:
            return {"mode": None, "frequency": 0}

        mode_value = max(value_counts, key=value_counts.get)
        frequency = value_counts[mode_value]

        return {
            "mode": mode_value,
            "frequency": frequency,
            "total_values": len(value_counts),
        }

    async def _get_filtered_documents(self, filters: Optional[Dict]) -> List:
        """دریافت اسناد فیلتر شده"""
        try:
            if hasattr(self.vector_store, "get_documents_by_metadata"):
                return await self.vector_store.get_documents_by_metadata(filters or {})
            elif hasattr(self.vector_store, "get_all_documents"):
                all_docs = await self.vector_store.get_all_documents()
                if filters:
                    # اعمال فیلتر ساده
                    filtered_docs = []
                    for doc in all_docs:
                        if self._matches_filters(doc, filters):
                            filtered_docs.append(doc)
                    return filtered_docs
                return all_docs
            else:
                # fallback - return empty list
                return []
        except Exception as e:
            logger.error(f"Error getting filtered documents: {str(e)}")
            return []

    def _matches_filters(self, doc, filters: Dict[str, Any]) -> bool:
        """بررسی تطابق سند با فیلترها"""
        if not hasattr(doc, "metadata"):
            return False

        for field, condition in filters.items():
            if field not in doc.metadata:
                return False

            doc_value = doc.metadata[field]

            if isinstance(condition, dict):
                # فیلتر پیچیده
                for op, value in condition.items():
                    if op == "$gte" and doc_value < value:
                        return False
                    elif op == "$lte" and doc_value > value:
                        return False
                    elif op == "$gt" and doc_value <= value:
                        return False
                    elif op == "$lt" and doc_value >= value:
                        return False
                    elif op == "$eq" and doc_value != value:
                        return False
                    elif op == "$ne" and doc_value == value:
                        return False
            else:
                # فیلتر ساده
                if doc_value != condition:
                    return False

        return True

    async def _group_and_aggregate(
        self, documents: List, query: AggregationQuery
    ) -> Dict:
        """گروه‌بندی و جمع‌آوری"""
        groups = {}

        # گروه‌بندی بر اساس فیلدهای group_by
        for doc in documents:
            group_key = []
            for field in query.group_by:
                if hasattr(doc, "metadata") and field in doc.metadata:
                    group_key.append(str(doc.metadata[field]))
                else:
                    group_key.append("null")

            group_key_str = "|".join(group_key)
            if group_key_str not in groups:
                groups[group_key_str] = []
            groups[group_key_str].append(doc)

        # اعمال عملیات جمع‌آوری روی هر گروه
        result = {}
        for group_key, group_docs in groups.items():
            if query.operation == AggregationType.COUNT:
                result[group_key] = len(group_docs)
            else:
                # برای سایر عملیات، از فیلد score استفاده می‌کنیم
                scores = [getattr(doc, "score", 0) for doc in group_docs]
                if scores:
                    if query.operation == AggregationType.SUM:
                        result[group_key] = sum(scores)
                    elif query.operation == AggregationType.AVG:
                        result[group_key] = statistics.mean(scores)
                    elif query.operation == AggregationType.MIN:
                        result[group_key] = min(scores)
                    elif query.operation == AggregationType.MAX:
                        result[group_key] = max(scores)
                    elif query.operation == AggregationType.MEDIAN:
                        result[group_key] = statistics.median(scores)
                else:
                    result[group_key] = 0

        return result

    async def _simple_aggregate(self, documents: List, query: AggregationQuery) -> Any:
        """جمع‌آوری ساده"""
        if query.operation == AggregationType.COUNT:
            return len(documents)
        else:
            # برای سایر عملیات، از فیلد score استفاده می‌کنیم
            scores = [getattr(doc, "score", 0) for doc in documents]
            if not scores:
                return 0

            if query.operation == AggregationType.SUM:
                return sum(scores)
            elif query.operation == AggregationType.AVG:
                return statistics.mean(scores)
            elif query.operation == AggregationType.MIN:
                return min(scores)
            elif query.operation == AggregationType.MAX:
                return max(scores)
            elif query.operation == AggregationType.MEDIAN:
                return statistics.median(scores)
            elif query.operation == AggregationType.STD_DEV:
                return statistics.stdev(scores) if len(scores) > 1 else 0.0
            elif query.operation == AggregationType.VARIANCE:
                return statistics.variance(scores) if len(scores) > 1 else 0.0
            elif query.operation == AggregationType.PERCENTILE:
                if query.percentile:
                    return (
                        statistics.quantiles(scores, n=100)[int(query.percentile) - 1]
                        if len(scores) > 1
                        else scores[0]
                    )
                else:
                    return statistics.median(scores)

        return 0
