#!/bin/bash

# RAG Telegram Bot Backup Script
# Usage: ./scripts/backup.sh [backup_name]

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="${1:-backup_$TIMESTAMP}"

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

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR"
    log_info "Backup directory: $BACKUP_DIR"
}

# Backup vector store data
backup_vector_store() {
    local vector_store_dir="$PROJECT_DIR/data/vector_store"
    local backup_path="$BACKUP_DIR/${BACKUP_NAME}_vector_store.tar.gz"
    
    if [[ -d "$vector_store_dir" && "$(ls -A "$vector_store_dir")" ]]; then
        log_info "Backing up vector store data..."
        tar -czf "$backup_path" -C "$PROJECT_DIR" data/vector_store/
        log_success "Vector store backup created: $backup_path"
    else
        log_warning "Vector store directory is empty or doesn't exist"
    fi
}

# Backup logs
backup_logs() {
    local logs_dir="$PROJECT_DIR/logs"
    local backup_path="$BACKUP_DIR/${BACKUP_NAME}_logs.tar.gz"
    
    if [[ -d "$logs_dir" && "$(ls -A "$logs_dir")" ]]; then
        log_info "Backing up logs..."
        tar -czf "$backup_path" -C "$PROJECT_DIR" logs/
        log_success "Logs backup created: $backup_path"
    else
        log_warning "Logs directory is empty or doesn't exist"
    fi
}

# Backup configuration
backup_configuration() {
    local config_backup_path="$BACKUP_DIR/${BACKUP_NAME}_config.tar.gz"
    
    log_info "Backing up configuration files..."
    
    # Create temporary directory for config files
    local temp_config_dir=$(mktemp -d)
    
    # Copy configuration files (excluding sensitive data)
    if [[ -f "$PROJECT_DIR/.env.example" ]]; then
        cp "$PROJECT_DIR/.env.example" "$temp_config_dir/"
    fi
    
    if [[ -f "$PROJECT_DIR/docker-compose.yml" ]]; then
        cp "$PROJECT_DIR/docker-compose.yml" "$temp_config_dir/"
    fi
    
    if [[ -f "$PROJECT_DIR/docker-compose.prod.yml" ]]; then
        cp "$PROJECT_DIR/docker-compose.prod.yml" "$temp_config_dir/"
    fi
    
    if [[ -f "$PROJECT_DIR/pyproject.toml" ]]; then
        cp "$PROJECT_DIR/pyproject.toml" "$temp_config_dir/"
    fi
    
    if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
        cp "$PROJECT_DIR/requirements.txt" "$temp_config_dir/"
    fi
    
    # Create backup
    tar -czf "$config_backup_path" -C "$temp_config_dir" .
    
    # Cleanup
    rm -rf "$temp_config_dir"
    
    log_success "Configuration backup created: $config_backup_path"
}

# Create full backup
create_full_backup() {
    local full_backup_path="$BACKUP_DIR/${BACKUP_NAME}_full.tar.gz"
    
    log_info "Creating full backup..."
    
    tar -czf "$full_backup_path" \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='htmlcov' \
        --exclude='dist' \
        --exclude='build' \
        --exclude='backups' \
        --exclude='.env' \
        --exclude='.env.*' \
        -C "$PROJECT_DIR" .
    
    log_success "Full backup created: $full_backup_path"
}

# List existing backups
list_backups() {
    log_info "Existing backups:"
    
    if [[ -d "$BACKUP_DIR" ]]; then
        ls -la "$BACKUP_DIR"/*.tar.gz 2>/dev/null || log_warning "No backups found"
    else
        log_warning "Backup directory doesn't exist"
    fi
}

# Cleanup old backups (keep last 10)
cleanup_old_backups() {
    log_info "Cleaning up old backups (keeping last 10)..."
    
    if [[ -d "$BACKUP_DIR" ]]; then
        # Remove old backups, keep last 10
        ls -t "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm -f
        log_success "Old backups cleaned up"
    fi
}

# Main backup function
main() {
    cd "$PROJECT_DIR"
    
    log_info "Starting backup process..."
    log_info "Backup name: $BACKUP_NAME"
    
    create_backup_dir
    backup_vector_store
    backup_logs
    backup_configuration
    create_full_backup
    cleanup_old_backups
    
    log_success "Backup process completed successfully!"
    log_info "Backup files are stored in: $BACKUP_DIR"
    
    list_backups
}

# Show help
show_help() {
    cat << EOF
RAG Telegram Bot Backup Script

Usage: $0 [backup_name]

Arguments:
  backup_name  - Optional name for the backup (default: backup_YYYYMMDD_HHMMSS)

Examples:
  $0                    # Create backup with timestamp
  $0 before_update      # Create backup with custom name
  $0 production_backup  # Create production backup

The script creates the following backups:
  - Vector store data (FAISS indices)
  - Application logs
  - Configuration files (without sensitive data)
  - Full application backup

Backups are stored in the 'backups' directory and old backups are automatically cleaned up.

EOF
}

# Handle help flag
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    show_help
    exit 0
fi

# Run main function
main "$@"