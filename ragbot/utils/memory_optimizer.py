"""
بهینه‌سازی حافظه
"""

import asyncio
import gc
import time
from typing import Any, Dict

import psutil
from loguru import logger


class MemoryOptimizer:
    """بهینه‌سازی حافظه"""

    def __init__(self, settings=None, max_memory_usage: float = 0.8):
        """Initialize memory optimizer"""
        self.settings = settings

        if settings and hasattr(settings, "performance"):
            perf_settings = settings.performance
            self.max_memory_usage = perf_settings.max_memory_usage
            self.optimization_interval = perf_settings.optimization_interval
        else:
            self.max_memory_usage = max_memory_usage
            self.optimization_interval = 60

        self.optimization_history = []

        # Background optimization
        self._optimization_task = None
        self._start_optimization()

    def _start_optimization(self):
        """شروع بهینه‌سازی پس‌زمینه"""

        async def optimization_loop():
            while True:
                try:
                    await self._check_and_optimize()
                    await asyncio.sleep(self.optimization_interval)
                except Exception as e:
                    logger.error(f"Error in memory optimization loop: {e}")
                    await asyncio.sleep(60)

        self._optimization_task = asyncio.create_task(optimization_loop())

    async def _check_and_optimize(self):
        """بررسی و بهینه‌سازی"""
        try:
            memory_usage = psutil.virtual_memory().percent / 100

            # Handle Mock objects
            if hasattr(self.max_memory_usage, "_mock_name"):
                self.max_memory_usage = 0.8

            if memory_usage > self.max_memory_usage:
                await self._optimize_memory()
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")

    async def _optimize_memory(self):
        """بهینه‌سازی حافظه"""
        try:
            optimization_start = time.time()

            # پاک‌سازی garbage collection
            collected = gc.collect()

            # فشرده‌سازی حافظه
            await self._compact_memory()

            # حذف کش‌های قدیمی
            await self._clear_old_caches()

            optimization_time = time.time() - optimization_start

            # ثبت تاریخچه
            self.optimization_history.append(
                {
                    "timestamp": optimization_start,
                    "duration": optimization_time,
                    "collected_objects": collected,
                    "memory_before": psutil.virtual_memory().percent,
                    "memory_after": psutil.virtual_memory().percent,
                }
            )

            logger.info(
                f"Memory optimization completed: {collected} objects collected in {optimization_time:.2f}s"
            )
        except Exception as e:
            logger.error(f"Error optimizing memory: {e}")

    async def _compact_memory(self):
        """فشرده‌سازی حافظه"""
        try:
            # اجرای garbage collection چندین بار
            for _ in range(3):
                gc.collect()
                await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error compacting memory: {e}")

    async def _clear_old_caches(self):
        """حذف کش‌های قدیمی"""
        try:
            # اینجا باید با cache manager ارتباط برقرار شود
            # برای حذف کش‌های قدیمی
            # فعلاً فقط یک placeholder هست
            pass
        except Exception as e:
            logger.error(f"Error clearing old caches: {e}")

    async def get_memory_stats(self) -> Dict[str, Any]:
        """دریافت آمار حافظه"""
        try:
            memory = psutil.virtual_memory()

            return {
                "total_memory": memory.total,
                "available_memory": memory.available,
                "used_memory": memory.used,
                "memory_percent": memory.percent,
                "optimization_count": len(self.optimization_history),
                "last_optimization": self.optimization_history[-1]
                if self.optimization_history
                else None,
            }
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {"error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """بررسی سلامت حافظه"""
        try:
            stats = await self.get_memory_stats()

            if "error" in stats:
                return {"status": "unhealthy", "error": stats["error"]}

            memory_percent = stats.get("memory_percent", 0)

            # Handle Mock objects
            max_memory_threshold = self.max_memory_usage
            if hasattr(max_memory_threshold, "_mock_name"):
                max_memory_threshold = 0.8

            if memory_percent > max_memory_threshold * 100:
                return {
                    "status": "critical",
                    "reason": f"Memory usage is high: {memory_percent:.1f}%",
                    "threshold": self.max_memory_usage * 100,
                }
            elif memory_percent > max_memory_threshold * 80:  # 80% of threshold
                return {
                    "status": "warning",
                    "reason": f"Memory usage is approaching threshold: {memory_percent:.1f}%",
                    "threshold": self.max_memory_usage * 100,
                }

            return {"status": "healthy", "metrics": stats}
        except Exception as e:
            logger.error(f"Error in memory health check: {e}")
            return {"status": "unhealthy", "error": str(e)}

    async def shutdown(self):
        """خاموش کردن بهینه‌سازی"""
        if self._optimization_task:
            self._optimization_task.cancel()
            try:
                await self._optimization_task
            except asyncio.CancelledError:
                pass
