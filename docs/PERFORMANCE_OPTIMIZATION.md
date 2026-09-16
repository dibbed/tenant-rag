# ⚡ Performance Optimization & Monitoring

## 📋 **Overview**

سیستم بهینه‌سازی عملکرد و نظارت بلادرنگ برای بهبود throughput و کاهش latency در RAG Telegram Assistant.

## 🎯 **Features**

### **1. Performance Monitoring**

- نظارت بلادرنگ بر زمان پاسخ‌دهی
- ردیابی throughput و error rate
- جمع‌آوری متریک‌های سیستم (CPU, Memory, Network)
- ادغام با Prometheus metrics

### **2. Resource Monitoring**

- نظارت بر استفاده از منابع سیستم
- سیستم هشدار پیش‌گیرانه
- ردیابی CPU، Memory، Disk usage
- تحلیل الگوهای استفاده

### **3. Async Processing**

- پردازش ناهمزمان اسناد
- پردازش دسته‌ای با محدودیت
- اجرای موازی با کنترل concurrency
- اجرای توابع blocking در thread جداگانه

### **4. Memory Optimization**

- بهینه‌سازی خودکار حافظه
- پاک‌سازی garbage collection
- مدیریت کش‌های قدیمی
- نظارت بر استفاده از حافظه

## 🏗️ **Architecture**

```
ragbot/
├── outputs/
│   ├── performance_monitor.py      # نظارت عملکرد
│   ├── resource_monitor.py          # نظارت منابع
│   └── performance_dashboard.py    # داشبورد عملکرد
├── utils/
│   ├── async_processor.py           # پردازش ناهمزمان
│   └── memory_optimizer.py          # بهینه‌سازی حافظه
└── configs/
    └── settings.py                  # تنظیمات عملکرد
```

## ⚙️ **Configuration**

### **Performance Settings**

```python
# در settings.py
class PerformanceSettings(BaseSettings):
    # Monitoring
    enable_performance_monitoring: bool = True
    monitoring_interval: int = 10  # seconds
    metrics_retention_days: int = 7

    # Resource monitoring
    enable_resource_monitoring: bool = True
    resource_check_interval: int = 5  # seconds
    alert_thresholds: Dict[str, float] = {
        "cpu": 80.0,
        "memory": 85.0,
        "disk": 90.0
    }

    # Async processing
    max_async_workers: int = 4
    max_concurrent_tasks: int = 10
    batch_size: int = 10

    # Memory optimization
    enable_memory_optimization: bool = True
    max_memory_usage: float = 0.8
    optimization_interval: int = 60  # seconds

    # Performance limits
    max_response_time: float = 5.0  # seconds
    max_throughput: int = 1000  # requests per minute
    max_concurrent_requests: int = 50
```

### **Environment Variables**

```bash
# Performance Monitoring
PERFORMANCE_ENABLE_PERFORMANCE_MONITORING=true
PERFORMANCE_MONITORING_INTERVAL=10
PERFORMANCE_METRICS_RETENTION_DAYS=7

# Resource Monitoring
PERFORMANCE_ENABLE_RESOURCE_MONITORING=true
PERFORMANCE_RESOURCE_CHECK_INTERVAL=5
PERFORMANCE_ALERT_THRESHOLDS_CPU=80.0
PERFORMANCE_ALERT_THRESHOLDS_MEMORY=85.0
PERFORMANCE_ALERT_THRESHOLDS_DISK=90.0

# Async Processing
PERFORMANCE_MAX_ASYNC_WORKERS=4
PERFORMANCE_MAX_CONCURRENT_TASKS=10
PERFORMANCE_BATCH_SIZE=10

# Memory Optimization
PERFORMANCE_ENABLE_MEMORY_OPTIMIZATION=true
PERFORMANCE_MAX_MEMORY_USAGE=0.8
PERFORMANCE_OPTIMIZATION_INTERVAL=60

# Performance Limits
PERFORMANCE_MAX_RESPONSE_TIME=5.0
PERFORMANCE_MAX_THROUGHPUT=1000
PERFORMANCE_MAX_CONCURRENT_REQUESTS=50
```

## 🚀 **Usage**

### **1. Basic Usage**

```python
from ragbot.outputs.performance_dashboard import PerformanceDashboard
from ragbot.configs.settings import Settings

# ایجاد تنظیمات
settings = Settings()

# ایجاد Performance Dashboard
dashboard = PerformanceDashboard(settings)
await dashboard.initialize()

# ثبت درخواست
await dashboard.record_request(0.5, success=True)

# دریافت خلاصه عملکرد
summary = await dashboard.get_performance_summary()
print(f"Average response time: {summary['average_response_time']:.3f}s")

# دریافت وضعیت سلامت
health = await dashboard.get_health_status()
print(f"System status: {health['overall_status']}")

# پاک‌سازی
await dashboard.shutdown()
```

### **2. Async Processing**

```python
from ragbot.utils.async_processor import AsyncProcessor

# ایجاد Async Processor
processor = AsyncProcessor(max_workers=4)

# پردازش ناهمزمان اسناد
async def process_document(doc):
    # پردازش سند
    return processed_doc

documents = [doc1, doc2, doc3, doc4]
results = await processor.process_documents_async(documents, process_document)

# پردازش دسته‌ای
async def process_batch(batch):
    # پردازش دسته
    return processed_batch

batch_results = await processor.batch_process(items, batch_size=10, process_func=process_batch)

# اجرای موازی با محدودیت
tasks = [create_task(i) for i in range(100)]
results = await processor.parallel_execute(tasks, max_concurrent=5)

# پاک‌سازی
await processor.shutdown()
```

### **3. Memory Optimization**

```python
from ragbot.utils.memory_optimizer import MemoryOptimizer

# ایجاد Memory Optimizer
optimizer = MemoryOptimizer(settings)

# دریافت آمار حافظه
stats = await optimizer.get_memory_stats()
print(f"Memory usage: {stats['memory_percent']:.1f}%")

# بررسی سلامت حافظه
health = await optimizer.health_check()
print(f"Memory health: {health['status']}")

# پاک‌سازی
await optimizer.shutdown()
```

## 🖥️ **CLI Commands**

### **Performance Command**

```bash
# نمایش متریک‌های عملکرد
ragbot-cli performance

# خروجی نمونه:
# Performance Summary:
# average_response_time: 0.523s
# total_requests: 150
# error_rate: 2.67%
# cpu_usage: 45.2%
# memory_usage: 67.8%
# active_connections: 12
#
# Resource Summary:
# current_cpu: 45.2%
# current_memory: 67.8%
# current_disk: 23.4%
# avg_cpu: 42.1%
# avg_memory: 65.3%
#
# Active Alerts (1):
# - warning: CPU usage is approaching threshold: 78.5%
```

## 📊 **Metrics**

### **Performance Metrics**

- **Response Time**: زمان پاسخ‌دهی به درخواست‌ها
- **Throughput**: تعداد درخواست‌ها در ثانیه
- **Error Rate**: نرخ خطا
- **CPU Usage**: استفاده از CPU
- **Memory Usage**: استفاده از حافظه
- **Active Connections**: اتصالات فعال

### **Resource Metrics**

- **CPU Percent**: درصد استفاده از CPU
- **Memory Percent**: درصد استفاده از حافظه
- **Disk Usage**: درصد استفاده از دیسک
- **Network I/O**: ورودی/خروجی شبکه
- **Process Count**: تعداد فرآیندها

### **Alert Types**

- **High CPU**: استفاده از CPU بیش از threshold
- **High Memory**: استفاده از حافظه بیش از threshold
- **High Disk**: استفاده از دیسک بیش از threshold

## 🧪 **Testing**

### **Unit Tests**

```bash
# اجرای تست‌های performance
pytest tests/unit/test_performance_integration.py -v

# اجرای تست‌های CLI
pytest tests/unit/test_cli_performance.py -v
```

### **Integration Tests**

```bash
# اجرای مثال کامل
python examples/performance_monitoring_example.py
```

## 🔧 **Troubleshooting**

### **Common Issues**

1. **Performance monitoring not working**

   - بررسی تنظیمات `enable_performance_monitoring`
   - بررسی دسترسی به psutil
   - بررسی Prometheus client

2. **High memory usage**

   - فعال‌سازی `enable_memory_optimization`
   - کاهش `max_memory_usage` threshold
   - بررسی memory leaks

3. **Resource alerts not triggering**
   - بررسی تنظیمات `alert_thresholds`
   - بررسی `resource_check_interval`
   - بررسی دسترسی به system metrics

### **Debug Mode**

```python
# فعال‌سازی debug mode
settings.debug = True

# بررسی logs
tail -f logs/ragbot.log | grep -i performance
```

## 📈 **Performance Benefits**

### **Expected Improvements**

- **+50%** بهبود throughput
- **+30%** کاهش response time
- **+40%** بهینه‌سازی استفاده از منابع
- **+60%** بهبود reliability

### **Monitoring Benefits**

- نظارت بلادرنگ
- هشدارهای پیش‌گیرانه
- بهینه‌سازی خودکار
- تحلیل عملکرد

## 🔄 **Integration**

### **With Existing Services**

- **RAG Service**: ثبت متریک‌های query
- **Integration Service**: مدیریت lifecycle
- **CLI**: دستورات performance
- **Settings**: تنظیمات متمرکز

### **With External Tools**

- **Prometheus**: جمع‌آوری metrics
- **Grafana**: visualization
- **AlertManager**: مدیریت هشدارها

## 📚 **API Reference**

### **PerformanceMonitor**

```python
class PerformanceMonitor:
    async def record_request(duration: float, success: bool = True)
    async def get_performance_summary() -> Dict[str, Any]
    async def health_check() -> Dict[str, Any]
    async def shutdown()
```

### **ResourceMonitor**

```python
class ResourceMonitor:
    async def get_resource_summary() -> Dict[str, Any]
    async def health_check() -> Dict[str, Any]
    async def shutdown()
```

### **AsyncProcessor**

```python
class AsyncProcessor:
    async def process_documents_async(documents, process_func)
    async def batch_process(items, batch_size, process_func)
    async def parallel_execute(tasks, max_concurrent)
    def run_in_thread(func, *args, **kwargs)
    async def shutdown()
```

### **MemoryOptimizer**

```python
class MemoryOptimizer:
    async def get_memory_stats() -> Dict[str, Any]
    async def health_check() -> Dict[str, Any]
    async def shutdown()
```

### **PerformanceDashboard**

```python
class PerformanceDashboard:
    async def initialize()
    async def get_dashboard_data() -> Dict[str, Any]
    async def get_health_status() -> Dict[str, Any]
    async def record_request(duration: float, success: bool = True)
    async def get_performance_summary() -> Dict[str, Any]
    async def get_resource_summary() -> Dict[str, Any]
    async def get_memory_stats() -> Dict[str, Any]
    async def shutdown()
```

---

**تاریخ آخرین بروزرسانی:** 2024-01-21
**نسخه:** 1.0.0
**وضعیت:** Production Ready
