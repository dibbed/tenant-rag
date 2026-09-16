#!/bin/bash

# RAG Telegram Assistant Setup Script
# This script sets up the environment for the RAG Telegram Assistant

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root for security reasons"
        exit 1
    fi
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    
    python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
    required_version="3.10"
    
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"; then
        log_error "Python 3.10+ is required, found $python_version"
        exit 1
    fi
    
    log_success "Python $python_version found"
    
    # Check Docker
    if command -v docker &> /dev/null; then
        log_success "Docker found"
    else
        log_warning "Docker not found - Docker deployment will not be available"
    fi
    
    # Check Docker Compose
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        log_success "Docker Compose found"
    else
        log_warning "Docker Compose not found - Docker deployment will not be available"
    fi
}

# Create directory structure
create_directories() {
    log_info "Creating directory structure..."
    
    directories=(
        "data"
        "data/vector_store"
        "logs"
        "config"
        "monitoring"
        "monitoring/grafana/dashboards"
        "monitoring/grafana/datasources"
        "backups"
    )
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            log_success "Created directory: $dir"
        else
            log_info "Directory already exists: $dir"
        fi
    done
    
    # Set proper permissions
    chmod 755 data logs config monitoring backups
    chmod 700 data/vector_store  # More restrictive for sensitive data
}

# Setup Python virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."
    
    if [[ ! -d "venv" ]]; then
        python3 -m venv venv
        log_success "Virtual environment created"
    else
        log_info "Virtual environment already exists"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        log_info "Installing Python dependencies..."
        pip install -r requirements.txt
        log_success "Dependencies installed"
    else
        log_error "requirements.txt not found"
        exit 1
    fi
}

# Setup environment configuration
setup_env() {
    log_info "Setting up environment configuration..."
    
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            log_success "Environment file created from template"
            log_warning "Please edit .env file with your actual credentials"
        else
            log_error ".env.example not found"
            exit 1
        fi
    else
        log_info "Environment file already exists"
    fi
    
    # Validate environment file
    if ! grep -q "BOT_TOKEN=" .env || ! grep -q "OPENAI_API_KEY=" .env; then
        log_warning "Please ensure BOT_TOKEN and OPENAI_API_KEY are set in .env file"
    fi
}

# Setup monitoring configuration
setup_monitoring() {
    log_info "Setting up monitoring configuration..."
    
    # Prometheus configuration
    cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'ragbot'
    static_configs:
      - targets: ['ragbot:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
    scrape_interval: 30s
EOF

    # Grafana datasource configuration
    cat > monitoring/grafana/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

    log_success "Monitoring configuration created"
}

# Setup Redis configuration
setup_redis() {
    log_info "Setting up Redis configuration..."
    
    cat > config/redis.conf << 'EOF'
# Redis configuration for RAG Telegram Assistant

# Network
bind 127.0.0.1
port 6379
timeout 300

# Memory management
maxmemory 256mb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Security
requirepass changeme

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Performance
tcp-keepalive 300
tcp-backlog 511
EOF

    log_success "Redis configuration created"
    log_warning "Please change the Redis password in config/redis.conf"
}

# Setup systemd service (optional)
setup_systemd() {
    if [[ "$1" == "--systemd" ]]; then
        log_info "Setting up systemd service..."
        
        current_dir=$(pwd)
        user=$(whoami)
        
        cat > ragbot.service << EOF
[Unit]
Description=RAG Telegram Assistant
After=network.target

[Service]
Type=simple
User=$user
WorkingDirectory=$current_dir
Environment=PATH=$current_dir/venv/bin
ExecStart=$current_dir/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

        log_success "Systemd service file created: ragbot.service"
        log_info "To install: sudo cp ragbot.service /etc/systemd/system/"
        log_info "To enable: sudo systemctl enable ragbot"
        log_info "To start: sudo systemctl start ragbot"
    fi
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."
    
    # Check if virtual environment is activated
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        log_success "Virtual environment is activated"
    else
        log_warning "Virtual environment is not activated"
    fi
    
    # Check if required packages are installed
    if python3 -c "import ragbot" 2>/dev/null; then
        log_success "RAGBot package is importable"
    else
        log_error "RAGBot package is not importable"
    fi
    
    # Check environment variables
    if [[ -f ".env" ]]; then
        source .env
        if [[ -n "${BOT_TOKEN:-}" ]] && [[ -n "${OPENAI_API_KEY:-}" ]]; then
            log_success "Required environment variables are set"
        else
            log_warning "Required environment variables are not set"
        fi
    fi
}

# Main setup function
main() {
    log_info "Starting RAG Telegram Assistant setup..."
    
    check_root
    check_requirements
    create_directories
    setup_venv
    setup_env
    setup_monitoring
    setup_redis
    setup_systemd "$@"
    run_health_checks
    
    log_success "Setup completed successfully!"
    log_info "Next steps:"
    echo "  1. Edit .env file with your credentials"
    echo "  2. Review config/redis.conf and update password"
    echo "  3. Run: source venv/bin/activate"
    echo "  4. Run: python main.py"
    echo ""
    echo "For Docker deployment:"
    echo "  docker-compose up --build -d"
    echo ""
    echo "For production deployment:"
    echo "  docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
}

# Run main function with all arguments
main "$@"