"""
Advanced Filtering System

This module provides advanced filtering capabilities for vector store queries,
including range filters, regex patterns, composite filters, and geographic filtering.
"""

from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import re
import math
import time
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class FilterOperator(Enum):
    """عملگرهای فیلتر"""

    EQ = "equals"  # برابر
    NE = "not_equals"  # نابرابر
    GT = "greater_than"  # بزرگتر از
    GTE = "greater_equal"  # بزرگتر یا مساوی
    LT = "less_than"  # کوچکتر از
    LTE = "less_equal"  # کوچکتر یا مساوی
    IN = "in"  # در لیست
    NIN = "not_in"  # خارج از لیست
    CONTAINS = "contains"  # شامل
    REGEX = "regex"  # الگوی منظم
    EXISTS = "exists"  # وجود دارد
    RANGE = "range"  # بازه
    GEO_WITHIN = "geo_within"  # در محدوده جغرافیایی


@dataclass
class FilterCondition:
    """شرط فیلتر"""

    field: str
    operator: FilterOperator
    value: Any
    case_sensitive: bool = True


@dataclass
class CompositeFilter:
    """فیلتر ترکیبی"""

    conditions: List[FilterCondition]
    logic: str = "AND"  # AND, OR, NOT
    sub_filters: Optional[List["CompositeFilter"]] = None


@dataclass
class GeoFilter:
    """فیلتر جغرافیایی"""

    lat: float
    lon: float
    radius: float  # در کیلومتر
    field: str = "location"


class AdvancedFilter:
    """سیستم فیلترینگ پیشرفته"""

    def __init__(self, vector_store):
        """Initialize filter system"""
        self.vector_store = vector_store
        self.compiled_patterns = {}  # برای caching regex patterns

    async def range_filter(
        self, field: str, min_val: Any, max_val: Any, inclusive: bool = True
    ) -> List[str]:
        """
        فیلتر بازه‌ای برای مقادیر عددی یا تاریخی

        Args:
            field: نام فیلد
            min_val: حداقل مقدار
            max_val: حداکثر مقدار
            inclusive: شامل مرزها باشد یا نه

        Returns:
            لیست ID های اسناد مطابق
        """
        documents = await self._get_all_documents()
        matching_ids = []

        for doc in documents:
            if not hasattr(doc, "metadata") or field not in doc.metadata:
                continue

            value = doc.metadata[field]

            # تبدیل به نوع مناسب
            try:
                if isinstance(min_val, datetime):
                    value = (
                        datetime.fromisoformat(value)
                        if isinstance(value, str)
                        else value
                    )
                else:
                    value = type(min_val)(value)
            except (ValueError, TypeError):
                continue

            # بررسی بازه
            if inclusive:
                if min_val <= value <= max_val:
                    matching_ids.append(doc.id)
            else:
                if min_val < value < max_val:
                    matching_ids.append(doc.id)

        return matching_ids

    async def regex_filter(
        self, field: str, pattern: str, case_sensitive: bool = True
    ) -> List[str]:
        """
        فیلتر بر اساس الگوی منظم

        Args:
            field: نام فیلد
            pattern: الگوی regex
            case_sensitive: حساس به حروف بزرگ/کوچک

        Returns:
            لیست ID های اسناد مطابق
        """
        # Compile pattern با caching
        cache_key = f"{pattern}_{case_sensitive}"
        if cache_key not in self.compiled_patterns:
            flags = 0 if case_sensitive else re.IGNORECASE
            self.compiled_patterns[cache_key] = re.compile(pattern, flags)

        compiled_pattern = self.compiled_patterns[cache_key]
        documents = await self._get_all_documents()
        matching_ids = []

        for doc in documents:
            if not hasattr(doc, "metadata") or field not in doc.metadata:
                continue

            value = str(doc.metadata[field])
            if compiled_pattern.search(value):
                matching_ids.append(doc.id)

        return matching_ids

    async def composite_filter(
        self, filters: List[FilterCondition], logic: str = "AND"
    ) -> List[str]:
        """
        فیلتر ترکیبی با چندین شرط

        Args:
            filters: لیست شرایط فیلتر
            logic: منطق ترکیب (AND, OR, NOT)

        Returns:
            لیست ID های اسناد مطابق
        """
        if not filters:
            return []

        # اجرای هر فیلتر
        filter_results = []
        for condition in filters:
            result_ids = await self._apply_single_condition(condition)
            filter_results.append(set(result_ids))

        # ترکیب نتایج بر اساس منطق
        if logic == "AND":
            result = filter_results[0]
            for result_set in filter_results[1:]:
                result = result.intersection(result_set)
        elif logic == "OR":
            result = set()
            for result_set in filter_results:
                result = result.union(result_set)
        elif logic == "NOT":
            # NOT فقط برای یک فیلتر
            all_ids = set(doc.id for doc in await self._get_all_documents())
            result = all_ids - filter_results[0]
        else:
            raise ValueError(f"Unsupported logic: {logic}")

        return list(result)

    async def geo_filter(
        self, lat: float, lon: float, radius: float, field: str = "location"
    ) -> List[str]:
        """
        فیلتر جغرافیایی بر اساس فاصله

        Args:
            lat: عرض جغرافیایی مرکز
            lon: طول جغرافیایی مرکز
            radius: شعاع در کیلومتر
            field: نام فیلد موقعیت در metadata

        Returns:
            لیست ID های اسناد در محدوده
        """
        documents = await self._get_all_documents()
        matching_ids = []

        for doc in documents:
            if not hasattr(doc, "metadata") or field not in doc.metadata:
                continue

            location = doc.metadata[field]
            if (
                not isinstance(location, dict)
                or "lat" not in location
                or "lon" not in location
            ):
                continue

            doc_lat = location["lat"]
            doc_lon = location["lon"]

            # محاسبه فاصله (Haversine formula)
            distance = self._calculate_distance(lat, lon, doc_lat, doc_lon)

            if distance <= radius:
                matching_ids.append(doc.id)

        return matching_ids

    async def date_range_filter(
        self,
        field: str,
        start_date: Union[str, datetime],
        end_date: Union[str, datetime],
        date_format: str = "%Y-%m-%d",
    ) -> List[str]:
        """
        فیلتر بازه تاریخی

        Args:
            field: نام فیلد تاریخ
            start_date: تاریخ شروع
            end_date: تاریخ پایان
            date_format: فرمت تاریخ

        Returns:
            لیست ID های اسناد در بازه
        """
        # تبدیل به datetime
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, date_format)
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, date_format)

        return await self.range_filter(field, start_date, end_date)

    async def text_search_filter(
        self,
        field: str,
        search_text: str,
        search_type: str = "contains",  # contains, starts_with, ends_with, exact
    ) -> List[str]:
        """
        فیلتر جستجوی متنی

        Args:
            field: نام فیلد متنی
            search_text: متن جستجو
            search_type: نوع جستجو

        Returns:
            لیست ID های اسناد مطابق
        """
        documents = await self._get_all_documents()
        matching_ids = []

        for doc in documents:
            if not hasattr(doc, "metadata") or field not in doc.metadata:
                continue

            value = str(doc.metadata[field]).lower()
            search_lower = search_text.lower()

            if search_type == "contains":
                if search_lower in value:
                    matching_ids.append(doc.id)
            elif search_type == "starts_with":
                if value.startswith(search_lower):
                    matching_ids.append(doc.id)
            elif search_type == "ends_with":
                if value.endswith(search_lower):
                    matching_ids.append(doc.id)
            elif search_type == "exact":
                if value == search_lower:
                    matching_ids.append(doc.id)

        return matching_ids

    async def numeric_filter(
        self,
        field: str,
        operator: FilterOperator,
        value: Union[int, float],
        tolerance: float = 0.0,
    ) -> List[str]:
        """
        فیلتر عددی با عملگرهای مختلف

        Args:
            field: نام فیلد عددی
            operator: عملگر فیلتر
            value: مقدار مقایسه
            tolerance: تحمل برای مقایسه‌های تقریبی

        Returns:
            لیست ID های اسناد مطابق
        """
        documents = await self._get_all_documents()
        matching_ids = []

        for doc in documents:
            if not hasattr(doc, "metadata") or field not in doc.metadata:
                continue

            try:
                doc_value = float(doc.metadata[field])
            except (ValueError, TypeError):
                continue

            # اعمال عملگر
            if operator == FilterOperator.EQ:
                if abs(doc_value - value) <= tolerance:
                    matching_ids.append(doc.id)
            elif operator == FilterOperator.NE:
                if abs(doc_value - value) > tolerance:
                    matching_ids.append(doc.id)
            elif operator == FilterOperator.GT:
                if doc_value > value + tolerance:
                    matching_ids.append(doc.id)
            elif operator == FilterOperator.GTE:
                if doc_value >= value - tolerance:
                    matching_ids.append(doc.id)
            elif operator == FilterOperator.LT:
                if doc_value < value - tolerance:
                    matching_ids.append(doc.id)
            elif operator == FilterOperator.LTE:
                if doc_value <= value + tolerance:
                    matching_ids.append(doc.id)

        return matching_ids

    async def array_filter(
        self, field: str, operator: FilterOperator, values: List[Any]
    ) -> List[str]:
        """
        فیلتر آرایه‌ای

        Args:
            field: نام فیلد آرایه
            operator: عملگر فیلتر
            values: مقادیر برای مقایسه

        Returns:
            لیست ID های اسناد مطابق
        """
        documents = await self._get_all_documents()
        matching_ids = []

        for doc in documents:
            if not hasattr(doc, "metadata") or field not in doc.metadata:
                continue

            doc_value = doc.metadata[field]
            if not isinstance(doc_value, list):
                continue

            if operator == FilterOperator.IN:
                if any(v in doc_value for v in values):
                    matching_ids.append(doc.id)
            elif operator == FilterOperator.NIN:
                if not any(v in doc_value for v in values):
                    matching_ids.append(doc.id)
            elif operator == FilterOperator.CONTAINS:
                if all(v in doc_value for v in values):
                    matching_ids.append(doc.id)

        return matching_ids

    async def _apply_single_condition(self, condition: FilterCondition) -> List[str]:
        """اعمال یک شرط فیلتر"""
        documents = await self._get_all_documents()
        matching_ids = []

        for doc in documents:
            if not hasattr(doc, "metadata") or condition.field not in doc.metadata:
                if condition.operator == FilterOperator.EXISTS:
                    # بررسی وجود فیلد
                    if condition.value is False:
                        matching_ids.append(doc.id)
                continue

            value = doc.metadata[condition.field]

            # اعمال عملگر
            if condition.operator == FilterOperator.EQ:
                if value == condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.NE:
                if value != condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.GT:
                if value > condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.GTE:
                if value >= condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.LT:
                if value < condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.LTE:
                if value <= condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.IN:
                if value in condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.NIN:
                if value not in condition.value:
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.CONTAINS:
                if condition.value in str(value):
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.REGEX:
                pattern = re.compile(
                    condition.value, 0 if condition.case_sensitive else re.IGNORECASE
                )
                if pattern.search(str(value)):
                    matching_ids.append(doc.id)
            elif condition.operator == FilterOperator.EXISTS:
                if condition.value:
                    matching_ids.append(doc.id)

        return matching_ids

    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """محاسبه فاصله بین دو نقطه جغرافیایی (Haversine formula)"""
        R = 6371  # شعاع زمین در کیلومتر

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
            math.radians(lat1)
        ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = R * c

        return distance

    async def _get_all_documents(self) -> List:
        """دریافت همه اسناد از vector store"""
        try:
            if hasattr(self.vector_store, "get_all_documents"):
                return await self.vector_store.get_all_documents()
            elif hasattr(self.vector_store, "search"):
                # استفاده از search با query خالی برای دریافت همه
                results = await self.vector_store.search("", limit=10000)
                return [result.document for result in results]
            else:
                return []
        except Exception as e:
            logger.error(f"Error getting all documents: {str(e)}")
            return []

    async def clear_pattern_cache(self):
        """پاک کردن cache الگوهای regex"""
        self.compiled_patterns.clear()

    async def get_filter_statistics(self) -> Dict[str, Any]:
        """دریافت آمار فیلترها"""
        return {
            "cached_patterns": len(self.compiled_patterns),
            "total_documents": len(await self._get_all_documents()),
            "available_fields": await self._get_available_fields(),
        }

    async def _get_available_fields(self) -> List[str]:
        """دریافت فیلدهای موجود در metadata"""
        documents = await self._get_all_documents()
        fields = set()

        for doc in documents:
            if hasattr(doc, "metadata") and doc.metadata:
                fields.update(doc.metadata.keys())

        return list(fields)
