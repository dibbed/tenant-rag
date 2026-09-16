"""
پردازش ناهمزمان برای بهبود عملکرد
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, List

from loguru import logger


class AsyncProcessor:
    """پردازش ناهمزمان"""

    def __init__(self, max_workers: int = 4):
        """Initialize async processor"""
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def process_documents_async(
        self, documents: List[Any], process_func: Callable[[Any], Awaitable[Any]]
    ) -> List[Any]:
        """پردازش ناهمزمان اسناد"""
        try:
            # ایجاد تسک‌ها
            tasks = [process_func(doc) for doc in documents]

            # اجرای موازی
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # فیلتر کردن خطاها
            successful_results = [r for r in results if not isinstance(r, Exception)]

            # لاگ کردن خطاها
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                logger.warning(f"Async processing completed with {len(errors)} errors")

            return successful_results
        except Exception as e:
            logger.error(f"Error in async document processing: {e}")
            return []

    async def batch_process(
        self,
        items: List[Any],
        process_func: Callable[[List[Any]], Awaitable[List[Any]]],
        batch_size: int = 10,
    ) -> List[Any]:
        """پردازش دسته‌ای"""
        try:
            results = []

            # تقسیم به دسته‌ها
            for i in range(0, len(items), batch_size):
                batch = items[i : i + batch_size]

                # پردازش دسته
                batch_result = await process_func(batch)
                results.extend(batch_result)

            return results
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            return []

    async def parallel_execute(
        self, tasks: List[Awaitable[Any]], max_concurrent: int = 5
    ) -> List[Any]:
        """اجرای موازی با محدودیت"""
        try:
            semaphore = asyncio.Semaphore(max_concurrent)

            async def limited_task(task):
                async with semaphore:
                    return await task

            # اجرای موازی با محدودیت
            results = await asyncio.gather(*[limited_task(task) for task in tasks])

            return results
        except Exception as e:
            logger.error(f"Error in parallel execution: {e}")
            return []

    def run_in_thread(self, func: Callable, *args, **kwargs) -> Awaitable[Any]:
        """اجرای تابع در thread جداگانه"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_in_executor(self.executor, func, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error running function in thread: {e}")
            raise

    async def shutdown(self):
        """خاموش کردن executor"""
        try:
            self.executor.shutdown(wait=True)
        except Exception as e:
            logger.error(f"Error shutting down async processor: {e}")
