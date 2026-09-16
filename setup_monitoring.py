#!/usr/bin/env python3
"""
RAG Monitoring Setup Script

Persian developer notes:
- این script monitoring stack را راه‌اندازی می‌کند
- شامل Prometheus, Grafana, و Alert Manager
"""

import subprocess
import time
from pathlib import Path

import requests


class MonitoringSetup:
    """راه‌اندازی monitoring stack."""

    def __init__(self):
        self.monitoring_dir = Path("monitoring")
        self.docker_compose_file = self.monitoring_dir / "docker-compose.yml"

    def create_docker_compose(self):
        """ایجاد docker-compose.yml برای monitoring."""
        docker_compose_content = """
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: rag_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./alert_rules:/etc/prometheus/alert_rules
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: rag_grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/datasources:/etc/grafana/provisioning/datasources
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: rag_alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager.yml:/etc/alertmanager/alertmanager.yml
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
    restart: unless-stopped

volumes:
  prometheus_data:
  grafana_data:
  alertmanager_data:
"""

        with open(self.docker_compose_file, "w") as f:
            f.write(docker_compose_content.strip())

        print("✅ Docker Compose file created!")

    def create_alertmanager_config(self):
        """ایجاد تنظیمات Alert Manager."""
        alertmanager_content = """
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@ragbot.local'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://localhost:5001/'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'dev', 'instance']
"""

        alertmanager_file = self.monitoring_dir / "alertmanager.yml"
        with open(alertmanager_file, "w") as f:
            f.write(alertmanager_content.strip())

        print("✅ Alert Manager config created!")

    def check_docker(self):
        """بررسی نصب Docker."""
        try:
            result = subprocess.run(
                ["docker", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                print("✅ Docker is installed!")
                return True
            else:
                print("❌ Docker is not installed!")
                return False
        except FileNotFoundError:
            print("❌ Docker is not installed!")
            return False

    def start_monitoring(self):
        """راه‌اندازی monitoring stack."""
        if not self.check_docker():
            print("Please install Docker first!")
            return False

        print("🚀 Starting monitoring stack...")

        try:
            # Start services
            subprocess.run(
                ["docker-compose", "up", "-d"], cwd=self.monitoring_dir, check=True
            )

            print("✅ Monitoring stack started!")
            print()
            print("🌐 Access URLs:")
            print("  📊 Prometheus: http://localhost:9090")
            print("  📈 Grafana: http://localhost:3000")
            print("  📋 Alert Manager: http://localhost:9093")
            print()
            print("🔑 Grafana Login:")
            print("  Username: admin")
            print("  Password: admin")

            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to start monitoring: {e}")
            return False

    def wait_for_services(self):
        """انتظار برای آماده شدن سرویس‌ها."""
        print("⏳ Waiting for services to be ready...")

        services = [
            ("Prometheus", "http://localhost:9090/-/ready"),
            ("Grafana", "http://localhost:3000/api/health"),
        ]

        for service_name, url in services:
            for _ in range(30):  # 30 attempts, 2 seconds each
                try:
                    response = requests.get(url, timeout=2)
                    if response.status_code == 200:
                        print(f"✅ {service_name} is ready!")
                        break
                except requests.RequestException:
                    pass

                time.sleep(2)
            else:
                print(f"⚠️  {service_name} might not be ready yet")

    def show_dashboard_info(self):
        """نمایش اطلاعات dashboard."""
        print()
        print("📋 DASHBOARD FILES:")
        print("-" * 40)
        print("• monitoring/grafana/dashboards/rag_phase1_metrics.json")
        print("• monitoring/grafana/dashboards/rag_phase4_quality_metrics.json")
        print("• monitoring/alert_rules/rag_phase1_alerts.yml")
        print("• monitoring/alert_rules/rag_phase4_quality_alerts.yml")
        print()

        print("📊 IMPORT DASHBOARDS:")
        print("-" * 40)
        print("1. Go to http://localhost:3000")
        print("2. Login with admin/admin")
        print("3. Go to '+' > Import")
        print("4. Upload the JSON files from grafana/dashboards/")
        print()

    def run_setup(self):
        """اجرای کامل setup."""
        print("=" * 60)
        print("🔧 RAG MONITORING SETUP")
        print("=" * 60)

        # Create necessary files
        self.create_docker_compose()
        self.create_alertmanager_config()

        # Start monitoring
        if self.start_monitoring():
            self.wait_for_services()
            self.show_dashboard_info()

            print("=" * 60)
            print("🎉 Monitoring setup completed!")
            print("=" * 60)
        else:
            print("❌ Setup failed!")


def main():
    """تابع اصلی."""
    setup = MonitoringSetup()
    setup.run_setup()


if __name__ == "__main__":
    main()
