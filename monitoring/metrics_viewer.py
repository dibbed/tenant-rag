#!/usr/bin/env python3
"""
RAG Metrics Viewer - نمایش metrics های پیاده‌سازی شده

Persian developer notes:
- این script metrics های مختلف را نمایش می‌دهد
- شامل retrieval, reranker, cache, و quality metrics
"""

import time

from ragbot.outputs.metrics import (
    cache_analytics,
    metrics_manager,
    quality_evaluator,
    reranker_evaluator,
    retrieval_evaluator,
    system_performance_monitor,
)


class MetricsViewer:
    """نمایش‌دهنده metrics های RAG system."""

    def __init__(self):
        self.metrics_manager = metrics_manager
        self.retrieval_evaluator = retrieval_evaluator
        self.reranker_evaluator = reranker_evaluator
        self.cache_analytics = cache_analytics
        self.quality_evaluator = quality_evaluator
        self.system_performance_monitor = system_performance_monitor

    def show_system_status(self):
        """نمایش وضعیت کلی سیستم."""
        print("=" * 60)
        print("🔍 RAG SYSTEM METRICS DASHBOARD")
        print("=" * 60)
        print(
            f"📊 Metrics Manager: {'✅ Enabled' if self.metrics_manager.enabled else '❌ Disabled'}"
        )
        print(f"🕒 Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    def show_retrieval_metrics(self):
        """نمایش metrics های retrieval."""
        print("📈 RETRIEVAL PERFORMANCE METRICS")
        print("-" * 40)

        summary = self.retrieval_evaluator.get_evaluation_summary()
        print(f"Total Evaluations: {summary.get('total_evaluations', 0)}")
        print(f"Recent Evaluations: {summary.get('recent_evaluations', 0)}")
        print(f"Avg Recall Delta: {summary.get('avg_recall_delta', 0):.3f}")
        print(f"Avg MRR Improvement: {summary.get('avg_mrr_improvement', 0):.3f}")
        print(f"Avg NDCG Improvement: {summary.get('avg_ndcg_improvement', 0):.3f}")
        print(f"Improvement Rate: {summary.get('improvement_rate', 0):.1%}")
        print()

    def show_reranker_metrics(self):
        """نمایش metrics های reranker."""
        print("🎯 RERANKER PERFORMANCE METRICS")
        print("-" * 40)

        summary = self.reranker_evaluator.get_performance_summary()
        print(f"Total Reranking Operations: {summary.get('total_operations', 0)}")
        print(f"Average Latency: {summary.get('average_latency', 0):.3f}s")
        print(f"Average Quality Score: {summary.get('average_quality', 0):.3f}")
        print(f"Cache Hit Rate: {summary.get('cache_hit_rate', 0):.1%}")
        print(
            f"Average Throughput: {summary.get('average_throughput', 0):.1f} docs/sec"
        )
        print(f"Timeout Rate: {summary.get('timeout_rate', 0):.1%}")
        print(f"Fallback Rate: {summary.get('fallback_rate', 0):.1%}")
        print()

    def show_cache_metrics(self):
        """نمایش metrics های cache."""
        print("💾 CACHE ANALYTICS METRICS")
        print("-" * 40)

        summary = self.cache_analytics.get_analytics_summary()
        print(f"Cache Size: {summary.get('cache_size', 0)} entries")
        print(f"Hit Rate: {summary.get('hit_rate', 0):.1%}")
        print(f"Miss Rate: {summary.get('miss_rate', 0):.1%}")
        print(f"Eviction Rate: {summary.get('eviction_rate', 0):.1%}")
        print(f"TTL Expiration Rate: {summary.get('ttl_expiration_rate', 0):.1%}")
        print(
            f"Average Confidence Score: {summary.get('average_confidence_score', 0):.3f}"
        )
        print(
            f"Average Similarity Score: {summary.get('average_similarity_score', 0):.3f}"
        )
        print(f"Deduplication Ratio: {summary.get('deduplication_ratio', 0):.1%}")
        print(f"Memory Efficiency: {summary.get('memory_efficiency', 0):.1%}")
        print()

    def show_quality_metrics(self):
        """نمایش metrics های quality."""
        print("⭐ QUALITY & CONFIDENCE METRICS")
        print("-" * 40)

        summary = self.quality_evaluator.get_quality_summary()
        quality_stats = summary.get("quality_stats", {})

        print(f"Total Responses: {quality_stats.get('total_responses', 0)}")
        print(f"Average Confidence: {quality_stats.get('average_confidence', 0):.3f}")
        print(f"Average Quality: {quality_stats.get('average_quality', 0):.3f}")
        print(
            f"High Quality Responses: {quality_stats.get('high_quality_responses', 0)}"
        )
        print(
            f"Low Confidence Responses: {quality_stats.get('low_confidence_responses', 0)}"
        )
        print(
            f"User Satisfaction Count: {quality_stats.get('user_satisfaction_count', 0)}"
        )

        # Confidence Distribution
        conf_dist = summary.get("confidence_distribution", {})
        if conf_dist:
            print(f"Confidence - Mean: {conf_dist.get('mean', 0):.3f}")
            print(f"Confidence - Min: {conf_dist.get('min', 0):.3f}")
            print(f"Confidence - Max: {conf_dist.get('max', 0):.3f}")

        # Model Performance
        model_perf = summary.get("model_performance", {})
        if model_perf:
            print(f"Models Tracked: {len(model_perf)}")
            for model, perf in model_perf.items():
                print(
                    f"  {model}: {perf.get('average_confidence', 0):.3f} conf, {perf.get('average_quality', 0):.3f} quality"
                )
        print()

    def show_system_performance_metrics(self):
        """نمایش metrics های system performance."""
        print("🖥️ SYSTEM PERFORMANCE & RESOURCE METRICS")
        print("-" * 40)

        summary = self.system_performance_monitor.get_performance_summary()

        # CPU Metrics
        cpu_metrics = summary.get("cpu_metrics", {})
        print(f"CPU Usage - Current: {cpu_metrics.get('current', 0):.1f}%")
        print(f"CPU Usage - Average: {cpu_metrics.get('average', 0):.1f}%")
        print(f"CPU Usage - Max: {cpu_metrics.get('max', 0):.1f}%")

        # Memory Metrics
        memory_metrics = summary.get("memory_metrics", {})
        print(f"Memory Usage - Current: {memory_metrics.get('current', 0):.1f}%")
        print(f"Memory Usage - Average: {memory_metrics.get('average', 0):.1f}%")
        print(f"Memory Usage - Max: {memory_metrics.get('max', 0):.1f}%")

        # Disk Metrics
        disk_metrics = summary.get("disk_metrics", {})
        print(f"Disk Usage - Current: {disk_metrics.get('current', 0):.1f}%")
        print(f"Disk Usage - Average: {disk_metrics.get('average', 0):.1f}%")
        print(f"Disk Usage - Max: {disk_metrics.get('max', 0):.1f}%")

        # Network Metrics
        network_metrics = summary.get("network_metrics", {})
        print(f"Network Latency - Current: {network_metrics.get('current', 0):.3f}s")
        print(f"Network Latency - Average: {network_metrics.get('average', 0):.3f}s")
        print(f"Network Latency - Max: {network_metrics.get('max', 0):.3f}s")

        # Response Time Metrics
        response_metrics = summary.get("response_time_metrics", {})
        print(f"Response Time - Current: {response_metrics.get('current', 0):.2f}s")
        print(f"Response Time - Average: {response_metrics.get('average', 0):.2f}s")
        print(f"Response Time - Max: {response_metrics.get('max', 0):.2f}s")

        # System Metrics
        print(f"Error Rate: {summary.get('error_rate', 0):.1f}%")
        print(f"Throughput: {summary.get('throughput', 0):.2f} req/s")
        print(f"Concurrent Users: {summary.get('concurrent_users', 0)}")
        print(f"Queue Length: {summary.get('queue_length', 0)}")
        print(f"Total Requests: {summary.get('total_requests', 0)}")
        print(f"Total Errors: {summary.get('total_errors', 0)}")

        # Bottlenecks
        bottlenecks = summary.get("bottlenecks", [])
        if bottlenecks:
            print(f"⚠️ Bottlenecks Detected: {len(bottlenecks)}")
            for bottleneck in bottlenecks:
                print(f"  - {bottleneck}")
        else:
            print("✅ No bottlenecks detected")
        print()

    def show_prometheus_endpoints(self):
        """نمایش Prometheus endpoints."""
        print("🌐 PROMETHEUS ENDPOINTS")
        print("-" * 40)
        print("📊 Metrics Endpoint: http://localhost:8000/metrics")
        print("🔍 Prometheus UI: http://localhost:9090")
        print("📈 Grafana Dashboard: http://localhost:3000")
        print("📋 Alert Manager: http://localhost:9093")
        print()

    def show_sample_data(self):
        """نمایش نمونه داده‌ها."""
        print("🧪 ADDING SAMPLE DATA FOR DEMONSTRATION")
        print("-" * 40)

        try:
            # Add sample cache data
            self.cache_analytics.record_cache_hit(
                query="test query",
                confidence_score=0.9,
                similarity_score=0.95,
            )
            self.cache_analytics.record_cache_miss(query="test query")
            self.cache_analytics.record_cache_size(100)

            # Add sample quality data
            self.quality_evaluator.record_response_quality(
                query="What is machine learning?",
                response="Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
                confidence_score=0.88,
                model_name="gpt-3.5-turbo",
                context_used=["ML is a subset of AI", "Computers learn from data"],
                quality_scores={
                    "accuracy": 0.9,
                    "relevance": 0.95,
                    "completeness": 0.85,
                    "coherence": 0.9,
                    "factual_accuracy": 0.88,
                },
                user_satisfaction=4,
            )

            # Add sample system performance data
            self.system_performance_monitor.record_cpu_usage(75.0)
            self.system_performance_monitor.record_memory_usage(1024000000, 80.0)
            self.system_performance_monitor.record_disk_usage(512000000000, 60.0)
            self.system_performance_monitor.record_network_latency(0.05)
            self.system_performance_monitor.record_response_time(2.0)
            self.system_performance_monitor.record_request(success=True)
            self.system_performance_monitor.record_request(success=False)
            self.system_performance_monitor.update_concurrent_users(10)
            self.system_performance_monitor.update_queue_length(5)

            print("✅ Sample data added successfully!")
        except Exception as e:
            print(f"⚠️  Could not add sample data: {e}")
        print()

    def run_dashboard(self):
        """اجرای dashboard کامل."""
        self.show_system_status()
        self.show_sample_data()
        self.show_retrieval_metrics()
        self.show_reranker_metrics()
        self.show_cache_metrics()
        self.show_quality_metrics()
        self.show_system_performance_metrics()
        self.show_prometheus_endpoints()

        print("=" * 60)
        print("🎉 Dashboard completed! Check Prometheus/Grafana for live metrics.")
        print("=" * 60)


def main():
    """تابع اصلی."""
    viewer = MetricsViewer()
    viewer.run_dashboard()


if __name__ == "__main__":
    main()
