#!/bin/bash

# TenantRAG Health Check Script
# Usage: ./scripts/health_check.sh [options]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
HEALTH_ENDPOINT="http://localhost:8000/api/v1/health"
TIMEOUT=10

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

# Check if Docker containers are running
check_containers() {
    log_info "Checking Docker containers..."
    
    local containers=("tenant-rag")
    local all_healthy=true
    
    for container in "${containers[@]}"; do
        if docker ps --format "table {{.Names}}" | grep -q "$container"; then
            local status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-health-check")
            
            case "$status" in
                "healthy")
                    log_success "Container $container: healthy"
                    ;;
                "unhealthy")
                    log_error "Container $container: unhealthy"
                    all_healthy=false
                    ;;
                "starting")
                    log_warning "Container $container: starting"
                    ;;
                "no-health-check")
                    log_warning "Container $container: running (no health check configured)"
                    ;;
                *)
                    log_error "Container $container: unknown status ($status)"
                    all_healthy=false
                    ;;
            esac
        else
            log_error "Container $container: not running"
            all_healthy=false
        fi
    done
    
    return $([ "$all_healthy" = true ] && echo 0 || echo 1)
}

# Check health endpoint
check_health_endpoint() {
    log_info "Checking health endpoint..."
    
    if command -v curl &> /dev/null; then
        local response=$(curl -s -w "%{http_code}" --max-time "$TIMEOUT" "$HEALTH_ENDPOINT" 2>/dev/null || echo "000")
        local http_code="${response: -3}"
        local body="${response%???}"
        
        case "$http_code" in
            "200")
                log_success "Health endpoint: OK"
                if [[ -n "$body" ]]; then
                    echo "Response: $body"
                fi
                return 0
                ;;
            "000")
                log_error "Health endpoint: Connection failed"
                return 1
                ;;
            *)
                log_error "Health endpoint: HTTP $http_code"
                return 1
                ;;
        esac
    else
        log_warning "curl not available, skipping health endpoint check"
        return 0
    fi
}

# Check storage directories
check_storage() {
    log_info "Checking storage directories..."
    local storage_dir="$PROJECT_DIR/data/vector_stores"
    if [[ -d "$storage_dir" ]]; then
        log_success "Storage directory exists: $storage_dir"
        return 0
    else
        log_warning "Storage directory not yet created: $storage_dir"
        return 0
    fi
}

# Check OpenAI API connectivity
check_openai_api() {
    log_info "Checking OpenAI API connectivity..."
    
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        local api_key=$(grep "^OPENAI_API_KEY=" "$PROJECT_DIR/.env" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        
        if [[ -n "$api_key" && "$api_key" != "your_openai_api_key_here" ]]; then
            if command -v curl &> /dev/null; then
                local response=$(curl -s --max-time "$TIMEOUT" \
                    -H "Authorization: Bearer $api_key" \
                    "https://api.openai.com/v1/models" 2>/dev/null || echo '{"error":{"message":"Connection failed"}}')
                
                if echo "$response" | grep -q '"data"'; then
                    log_success "OpenAI API: Connected"
                    return 0
                else
                    local error_message=$(echo "$response" | grep -o '"message":"[^"]*' | cut -d'"' -f4)
                    log_error "OpenAI API: ${error_message:-Authentication failed}"
                    return 1
                fi
            else
                log_warning "curl not available, skipping OpenAI API check"
                return 0
            fi
        else
            log_warning "OpenAI API key not configured, skipping OpenAI API check"
            return 0
        fi
    else
        log_warning ".env file not found, skipping OpenAI API check"
        return 0
    fi
}

# Check disk space
check_disk_space() {
    log_info "Checking disk space..."
    
    local data_dir="$PROJECT_DIR/data"
    local logs_dir="$PROJECT_DIR/logs"
    
    if command -v df &> /dev/null; then
        local disk_usage=$(df -h "$PROJECT_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
        
        if [[ "$disk_usage" -gt 90 ]]; then
            log_error "Disk space: ${disk_usage}% used (critical)"
            return 1
        elif [[ "$disk_usage" -gt 80 ]]; then
            log_warning "Disk space: ${disk_usage}% used (warning)"
        else
            log_success "Disk space: ${disk_usage}% used"
        fi
        
        # Check specific directories
        if [[ -d "$data_dir" ]]; then
            local data_size=$(du -sh "$data_dir" 2>/dev/null | cut -f1 || echo "unknown")
            echo "Data directory size: $data_size"
        fi
        
        if [[ -d "$logs_dir" ]]; then
            local logs_size=$(du -sh "$logs_dir" 2>/dev/null | cut -f1 || echo "unknown")
            echo "Logs directory size: $logs_size"
        fi
        
        return 0
    else
        log_warning "df command not available, skipping disk space check"
        return 0
    fi
}

# Check memory usage
check_memory_usage() {
    log_info "Checking memory usage..."
    
    if command -v docker &> /dev/null; then
        local container_stats=$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" 2>/dev/null | grep "tenant-rag" || echo "")
        
        if [[ -n "$container_stats" ]]; then
            echo "Container stats:"
            echo "$container_stats"
            
            local mem_perc=$(echo "$container_stats" | awk '{print $4}' | sed 's/%//')
            if [[ -n "$mem_perc" && "$mem_perc" =~ ^[0-9]+\.?[0-9]*$ ]]; then
                if (( $(echo "$mem_perc > 80" | bc -l) )); then
                    log_warning "High memory usage: ${mem_perc}%"
                else
                    log_success "Memory usage: ${mem_perc}%"
                fi
            fi
        else
            log_warning "Container not found or not running"
        fi
    else
        log_warning "Docker not available, skipping memory usage check"
    fi
}

# Check log files for errors
check_logs() {
    log_info "Checking recent logs for errors..."
    
    local logs_dir="$PROJECT_DIR/logs"
    local log_file="$logs_dir/ragbot.log"
    
    if [[ -f "$log_file" ]]; then
        local error_count=$(tail -100 "$log_file" | grep -c "ERROR" || echo "0")
        local warning_count=$(tail -100 "$log_file" | grep -c "WARNING" || echo "0")
        
        if [[ "$error_count" -gt 0 ]]; then
            log_warning "Found $error_count errors in recent logs"
            echo "Recent errors:"
            tail -100 "$log_file" | grep "ERROR" | tail -3
        else
            log_success "No errors found in recent logs"
        fi
        
        if [[ "$warning_count" -gt 0 ]]; then
            echo "Found $warning_count warnings in recent logs"
        fi
    else
        log_warning "Log file not found: $log_file"
    fi
}

# Generate health report
generate_report() {
    local overall_status="healthy"
    local failed_checks=0
    
    echo "=================================="
    echo "TenantRAG Health Report"
    echo "Generated: $(date)"
    echo "=================================="
    echo
    
    # Run all checks
    check_containers || { overall_status="unhealthy"; ((failed_checks++)); }
    echo
    
    check_health_endpoint || { overall_status="degraded"; ((failed_checks++)); }
    echo
    
    check_storage || { overall_status="degraded"; ((failed_checks++)); }
    echo
    
    check_openai_api || { overall_status="degraded"; ((failed_checks++)); }
    echo
    
    check_disk_space || { overall_status="degraded"; ((failed_checks++)); }
    echo
    
    check_memory_usage
    echo
    
    check_logs
    echo
    
    # Overall status
    echo "=================================="
    case "$overall_status" in
        "healthy")
            log_success "Overall Status: HEALTHY"
            ;;
        "degraded")
            log_warning "Overall Status: DEGRADED ($failed_checks issues)"
            ;;
        "unhealthy")
            log_error "Overall Status: UNHEALTHY ($failed_checks critical issues)"
            ;;
    esac
    echo "=================================="
    
    return $([ "$overall_status" = "healthy" ] && echo 0 || echo 1)
}

# Show help
show_help() {
    cat << EOF
TenantRAG Health Check Script

Usage: $0 [options]

Options:
  --containers    - Check only Docker containers
  --endpoint      - Check only health endpoint
  --storage       - Check vector store directory
  --openai        - Check only OpenAI API
  --disk          - Check only disk space
  --memory        - Check only memory usage
  --logs          - Check only log files
  --report        - Generate full health report (default)
  --help          - Show this help message

Examples:
  $0                # Full health report
  $0 --containers   # Check only containers
  $0 --endpoint     # Check only health endpoint
  $0 --report       # Full health report

EOF
}

# Main function
main() {
    cd "$PROJECT_DIR"
    
    case "${1:---report}" in
        --containers)
            check_containers
            ;;
        --endpoint)
            check_health_endpoint
            ;;
        --storage)
            check_storage
            ;;
        --openai)
            check_openai_api
            ;;
        --disk)
            check_disk_space
            ;;
        --memory)
            check_memory_usage
            ;;
        --logs)
            check_logs
            ;;
        --report)
            generate_report
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"