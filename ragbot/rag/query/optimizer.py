"""
Query Optimization Engine

This module provides query optimization capabilities including query analysis,
execution planning, performance hints, and optimization strategies.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import time
import statistics
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OptimizationStrategy(Enum):
    """استراتژی‌های بهینه‌سازی"""

    INDEX_HINT = "index_hint"
    QUERY_REWRITE = "query_rewrite"
    CACHE_OPTIMIZATION = "cache_optimization"
    PARALLEL_EXECUTION = "parallel_execution"
    FILTER_PUSHDOWN = "filter_pushdown"
    RESULT_LIMITING = "result_limiting"
    EARLY_TERMINATION = "early_termination"


@dataclass
class QueryPlan:
    """طرح اجرای پرسش"""

    steps: List[str]
    estimated_cost: float
    execution_time: float
    optimization_applied: List[OptimizationStrategy]
    estimated_result_size: int


@dataclass
class OptimizationResult:
    """نتیجه بهینه‌سازی"""

    original_plan: QueryPlan
    optimized_plan: QueryPlan
    improvement_percentage: float
    recommendations: List[str]
    performance_metrics: Dict[str, Any]


class QueryOptimizer:
    """موتور بهینه‌سازی پرسش‌ها"""

    def __init__(self, vector_store):
        """Initialize query optimizer"""
        self.vector_store = vector_store
        self.query_history = []
        self.performance_metrics = {}
        self.optimization_rules = self._load_optimization_rules()
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    async def optimize_query(
        self, query: str, filters: Optional[Dict] = None, context: Optional[Dict] = None
    ) -> OptimizationResult:
        """
        بهینه‌سازی پرسش بر اساس الگوهای موجود

        Args:
            query: پرسش اصلی
            filters: فیلترهای اعمال شده
            context: اطلاعات اضافی

        Returns:
            نتیجه بهینه‌سازی
        """
        # تحلیل پرسش
        query_analysis = await self._analyze_query(query, filters)

        # ایجاد طرح اولیه
        original_plan = await self._create_execution_plan(query_analysis)

        # اعمال بهینه‌سازی‌ها
        optimized_plan = await self._apply_optimizations(original_plan, query_analysis)

        # محاسبه بهبود
        improvement = self._calculate_improvement(original_plan, optimized_plan)

        # تولید توصیه‌ها
        recommendations = await self._generate_recommendations(
            query_analysis, optimized_plan
        )

        # محاسبه متریک‌های عملکرد
        performance_metrics = await self._calculate_performance_metrics(
            original_plan, optimized_plan
        )

        # ثبت در تاریخچه
        await self._record_query_history(
            query, query_analysis, original_plan, optimized_plan
        )

        return OptimizationResult(
            original_plan=original_plan,
            optimized_plan=optimized_plan,
            improvement_percentage=improvement,
            recommendations=recommendations,
            performance_metrics=performance_metrics,
        )

    async def _analyze_query(
        self, query: str, filters: Optional[Dict]
    ) -> Dict[str, Any]:
        """تحلیل پرسش برای شناسایی الگوها"""
        analysis = {
            "query_length": len(query.split()),
            "has_filters": bool(filters),
            "filter_complexity": self._calculate_filter_complexity(filters),
            "estimated_result_size": await self._estimate_result_size(query, filters),
            "query_type": self._classify_query_type(query),
            "performance_hints": [],
            "complexity_score": 0.0,
        }

        # شناسایی الگوهای مشکل‌ساز
        if analysis["query_length"] > 20:
            analysis["performance_hints"].append("long_query")

        if analysis["filter_complexity"] > 5:
            analysis["performance_hints"].append("complex_filters")

        if analysis["estimated_result_size"] > 10000:
            analysis["performance_hints"].append("large_result_set")

        # محاسبه complexity score
        analysis["complexity_score"] = self._calculate_complexity_score(analysis)

        return analysis

    async def _create_execution_plan(self, analysis: Dict[str, Any]) -> QueryPlan:
        """ایجاد طرح اجرای پرسش"""
        steps = []

        # مراحل پایه
        steps.append("parse_query")
        steps.append("validate_filters")

        if analysis["has_filters"]:
            steps.append("apply_filters")

        steps.append("vector_search")
        steps.append("rank_results")
        steps.append("format_output")

        # تخمین هزینه
        estimated_cost = self._estimate_execution_cost(analysis)

        return QueryPlan(
            steps=steps,
            estimated_cost=estimated_cost,
            execution_time=0.0,  # محاسبه می‌شود
            optimization_applied=[],
            estimated_result_size=analysis["estimated_result_size"],
        )

    async def _apply_optimizations(
        self, plan: QueryPlan, analysis: Dict[str, Any]
    ) -> QueryPlan:
        """اعمال بهینه‌سازی‌ها"""
        optimized_steps = plan.steps.copy()
        applied_optimizations = []

        # بهینه‌سازی فیلترها
        if "complex_filters" in analysis["performance_hints"]:
            optimized_steps = self._optimize_filter_order(optimized_steps)
            applied_optimizations.append(OptimizationStrategy.FILTER_PUSHDOWN)

        # بهینه‌سازی cache
        if "long_query" in analysis["performance_hints"]:
            optimized_steps.insert(1, "check_cache")
            applied_optimizations.append(OptimizationStrategy.CACHE_OPTIMIZATION)

        # بهینه‌سازی موازی
        if "large_result_set" in analysis["performance_hints"]:
            optimized_steps = self._add_parallel_execution(optimized_steps)
            applied_optimizations.append(OptimizationStrategy.PARALLEL_EXECUTION)

        # محدود کردن نتایج
        if analysis["estimated_result_size"] > 1000:
            optimized_steps.append("limit_results")
            applied_optimizations.append(OptimizationStrategy.RESULT_LIMITING)

        # بهینه‌سازی index
        if analysis["complexity_score"] > 0.7:
            optimized_steps.insert(2, "use_index_hint")
            applied_optimizations.append(OptimizationStrategy.INDEX_HINT)

        # محاسبه هزینه جدید
        new_cost = self._estimate_execution_cost(analysis, applied_optimizations)

        return QueryPlan(
            steps=optimized_steps,
            estimated_cost=new_cost,
            execution_time=0.0,
            optimization_applied=applied_optimizations,
            estimated_result_size=analysis["estimated_result_size"],
        )

    def _calculate_filter_complexity(self, filters: Optional[Dict]) -> int:
        """محاسبه پیچیدگی فیلترها"""
        if not filters:
            return 0

        complexity = 0
        for key, value in filters.items():
            if isinstance(value, dict):
                complexity += len(value)
            elif isinstance(value, list):
                complexity += len(value)
            else:
                complexity += 1

        return complexity

    async def _estimate_result_size(self, query: str, filters: Optional[Dict]) -> int:
        """تخمین اندازه نتیجه"""
        # تخمین ساده بر اساس طول پرسش
        base_size = len(query.split()) * 100

        if filters:
            # کاهش تخمین بر اساس فیلترها
            filter_reduction = len(filters) * 0.1
            base_size = int(base_size * (1 - filter_reduction))

        return max(base_size, 10)  # حداقل 10 نتیجه

    def _classify_query_type(self, query: str) -> str:
        """طبقه‌بندی نوع پرسش"""
        query_lower = query.lower()

        if any(word in query_lower for word in ["count", "sum", "avg", "group"]):
            return "aggregation"
        elif any(word in query_lower for word in ["find", "search", "look"]):
            return "search"
        elif any(word in query_lower for word in ["list", "show", "get"]):
            return "retrieval"
        else:
            return "general"

    def _calculate_complexity_score(self, analysis: Dict[str, Any]) -> float:
        """محاسبه امتیاز پیچیدگی"""
        score = 0.0

        # پیچیدگی بر اساس طول پرسش
        score += min(analysis["query_length"] / 50.0, 0.3)

        # پیچیدگی بر اساس فیلترها
        score += min(analysis["filter_complexity"] / 20.0, 0.3)

        # پیچیدگی بر اساس اندازه نتیجه
        score += min(analysis["estimated_result_size"] / 50000.0, 0.4)

        return min(score, 1.0)

    def _estimate_execution_cost(
        self, analysis: Dict[str, Any], optimizations: List[OptimizationStrategy] = None
    ) -> float:
        """تخمین هزینه اجرا"""
        base_cost = 1.0

        # هزینه بر اساس پیچیدگی
        base_cost += analysis["query_length"] * 0.1
        base_cost += analysis["filter_complexity"] * 0.2
        base_cost += analysis["estimated_result_size"] * 0.001

        # کاهش هزینه با بهینه‌سازی‌ها
        if optimizations:
            for opt in optimizations:
                if opt == OptimizationStrategy.CACHE_OPTIMIZATION:
                    base_cost *= 0.5
                elif opt == OptimizationStrategy.PARALLEL_EXECUTION:
                    base_cost *= 0.7
                elif opt == OptimizationStrategy.FILTER_PUSHDOWN:
                    base_cost *= 0.8
                elif opt == OptimizationStrategy.RESULT_LIMITING:
                    base_cost *= 0.6
                elif opt == OptimizationStrategy.INDEX_HINT:
                    base_cost *= 0.9

        return base_cost

    def _optimize_filter_order(self, steps: List[str]) -> List[str]:
        """بهینه‌سازی ترتیب فیلترها"""
        # جابجایی فیلترهای ساده به ابتدا
        optimized_steps = []

        for step in steps:
            if step == "apply_filters":
                optimized_steps.append("apply_simple_filters")
                optimized_steps.append("apply_complex_filters")
            else:
                optimized_steps.append(step)

        return optimized_steps

    def _add_parallel_execution(self, steps: List[str]) -> List[str]:
        """اضافه کردن اجرای موازی"""
        optimized_steps = []

        for step in steps:
            if step == "vector_search":
                optimized_steps.append("parallel_vector_search")
            else:
                optimized_steps.append(step)

        return optimized_steps

    def _calculate_improvement(
        self, original: QueryPlan, optimized: QueryPlan
    ) -> float:
        """محاسبه درصد بهبود"""
        if original.estimated_cost == 0:
            return 0.0

        improvement = (
            (original.estimated_cost - optimized.estimated_cost)
            / original.estimated_cost
        ) * 100
        return max(0.0, improvement)

    async def _generate_recommendations(
        self, analysis: Dict[str, Any], plan: QueryPlan
    ) -> List[str]:
        """تولید توصیه‌های بهینه‌سازی"""
        recommendations = []

        if "long_query" in analysis["performance_hints"]:
            recommendations.append(
                "Consider breaking down the query into smaller parts"
            )

        if "complex_filters" in analysis["performance_hints"]:
            recommendations.append("Simplify filter conditions for better performance")

        if "large_result_set" in analysis["performance_hints"]:
            recommendations.append("Add pagination or limit the result set size")

        if OptimizationStrategy.CACHE_OPTIMIZATION in plan.optimization_applied:
            recommendations.append(
                "Query results are cached for faster subsequent execution"
            )

        if OptimizationStrategy.PARALLEL_EXECUTION in plan.optimization_applied:
            recommendations.append(
                "Parallel execution is enabled for better performance"
            )

        if analysis["complexity_score"] > 0.8:
            recommendations.append(
                "Consider using more specific filters to reduce complexity"
            )

        if analysis["estimated_result_size"] > 5000:
            recommendations.append(
                "Large result set detected - consider implementing pagination"
            )

        return recommendations

    async def _calculate_performance_metrics(
        self, original: QueryPlan, optimized: QueryPlan
    ) -> Dict[str, Any]:
        """محاسبه متریک‌های عملکرد"""
        return {
            "cost_reduction": original.estimated_cost - optimized.estimated_cost,
            "cost_reduction_percentage": self._calculate_improvement(
                original, optimized
            ),
            "optimizations_applied": len(optimized.optimization_applied),
            "estimated_time_savings": (
                original.estimated_cost - optimized.estimated_cost
            )
            * 0.1,  # تخمین
            "complexity_reduction": len(original.steps) - len(optimized.steps),
        }

    async def _record_query_history(
        self,
        query: str,
        analysis: Dict[str, Any],
        original: QueryPlan,
        optimized: QueryPlan,
    ):
        """ثبت در تاریخچه پرسش‌ها"""
        history_entry = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "analysis": analysis,
            "original_plan": {
                "steps": original.steps,
                "estimated_cost": original.estimated_cost,
                "estimated_result_size": original.estimated_result_size,
            },
            "optimized_plan": {
                "steps": optimized.steps,
                "estimated_cost": optimized.estimated_cost,
                "optimizations_applied": [
                    opt.value for opt in optimized.optimization_applied
                ],
            },
            "improvement": self._calculate_improvement(original, optimized),
        }

        self.query_history.append(history_entry)

        # محدود کردن تاریخچه به 1000 ورودی
        if len(self.query_history) > 1000:
            self.query_history = self.query_history[-1000:]

    def _load_optimization_rules(self) -> Dict[str, Any]:
        """بارگذاری قوانین بهینه‌سازی"""
        return {
            "max_query_length": 50,
            "max_filter_complexity": 10,
            "max_result_size": 10000,
            "cache_threshold": 0.7,
            "parallel_threshold": 5000,
            "complexity_threshold": 0.7,
            "index_hint_threshold": 0.8,
        }

    async def get_optimization_statistics(self) -> Dict[str, Any]:
        """دریافت آمار بهینه‌سازی"""
        if not self.query_history:
            return {
                "total_queries": 0,
                "avg_improvement": 0.0,
                "most_common_optimizations": [],
                "performance_trends": {},
            }

        # محاسبه آمار
        total_queries = len(self.query_history)
        improvements = [entry["improvement"] for entry in self.query_history]
        avg_improvement = statistics.mean(improvements) if improvements else 0.0

        # محاسبه رایج‌ترین بهینه‌سازی‌ها
        optimization_counts = {}
        for entry in self.query_history:
            for opt in entry["optimized_plan"]["optimizations_applied"]:
                optimization_counts[opt] = optimization_counts.get(opt, 0) + 1

        most_common = sorted(
            optimization_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "total_queries": total_queries,
            "avg_improvement": avg_improvement,
            "most_common_optimizations": most_common,
            "performance_trends": {
                "recent_improvements": improvements[-10:]
                if len(improvements) >= 10
                else improvements
            },
        }

    async def clear_optimization_cache(self):
        """پاک کردن cache بهینه‌سازی"""
        self.cache.clear()

    async def benchmark_optimization(self, sample_queries: List[str]) -> Dict[str, Any]:
        """مقایسه عملکرد قبل و بعد از بهینه‌سازی"""
        results = {
            "queries_tested": len(sample_queries),
            "avg_improvement": 0.0,
            "optimization_effectiveness": {},
            "performance_gains": [],
        }

        improvements = []

        for query in sample_queries:
            try:
                optimization_result = await self.optimize_query(query)
                improvements.append(optimization_result.improvement_percentage)

                # ثبت اثربخشی بهینه‌سازی‌ها
                for opt in optimization_result.optimized_plan.optimization_applied:
                    opt_name = opt.value
                    if opt_name not in results["optimization_effectiveness"]:
                        results["optimization_effectiveness"][opt_name] = 0
                    results["optimization_effectiveness"][opt_name] += 1

            except Exception as e:
                logger.error(f"Error optimizing query '{query}': {str(e)}")
                continue

        if improvements:
            results["avg_improvement"] = statistics.mean(improvements)
            results["performance_gains"] = improvements

        return results
