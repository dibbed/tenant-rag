#!/bin/bash

# TenantRAG Deployment Script
# Usage: ./scripts/deploy.sh [environment] [options]
# Environments: development, staging, production
# Options: --build, --pull, --logs, --status, --stop

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DEFAULT_ENV="development"
ENVIRONMENT="${1:-$DEFAULT_ENV}"

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

# Help function
show_help() {
    cat << EOF
TenantRAG Deployment Script

Usage: $0 [environment] [options]

Environments:
  development  - Local development environment (default)
  staging      - Staging environment
  production   - Production environment

Options:
  --build      - Force rebuild of Docker images
  --pull       - Pull latest images before deployment
  --logs       - Show logs after deployment
  --status     - Show deployment status
  --stop       - Stop the deployment
  --help       - Show this help message

Examples:
  $0 development --build --logs
  $0 production --pull
  $0 staging --status
  $0 production --stop

EOF
}

# Validate environment
validate_environment() {
    case "$ENVIRONMENT" in
        development|staging|production)
            log_info "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: development, staging, production"
            exit 1
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker is not running"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Setup environment file
setup_environment() {
    local env_file=".env.$ENVIRONMENT"
    local target_env=".env"
    
    log_info "Setting up environment configuration..."
    
    if [[ ! -f "$env_file" ]]; then
        if [[ -f ".env.example" ]]; then
            log_warning "Environment file $env_file not found, copying from .env.example"
            cp ".env.example" "$env_file"
            log_warning "Please edit $env_file with your actual configuration"
        else
            log_error "Neither $env_file nor .env.example found"
            exit 1
        fi
    fi
    
    # Copy environment file
    cp "$env_file" "$target_env"
    log_success "Environment configuration set up"
}

# Validate configuration
validate_configuration() {
    log_info "Validating configuration..."
    
    if [[ ! -f ".env" ]]; then
        log_error "Environment file .env not found"
        exit 1
    fi
    
    # Check required variables
    local required_vars=("OPENAI_API_KEY")
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" .env || grep -q "^$var=$" .env; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            log_error "  - $var"
        done
        log_error "Please update your .env file"
        exit 1
    fi
    
    log_success "Configuration validation passed"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    local compose_files=("-f" "docker-compose.yml")
    
    case "$ENVIRONMENT" in
        development)
            compose_files+=("-f" "docker-compose.dev.yml")
            ;;
        production)
            compose_files+=("-f" "docker-compose.prod.yml")
            ;;
    esac
    
    docker-compose "${compose_files[@]}" build
    log_success "Docker images built successfully"
}

# Pull Docker images
pull_images() {
    log_info "Pulling Docker images..."
    
    local compose_files=("-f" "docker-compose.yml")
    
    case "$ENVIRONMENT" in
        development)
            compose_files+=("-f" "docker-compose.dev.yml")
            ;;
        production)
            compose_files+=("-f" "docker-compose.prod.yml")
            ;;
    esac
    
    docker-compose "${compose_files[@]}" pull
    log_success "Docker images pulled successfully"
}

# Deploy the application
deploy() {
    log_info "Deploying TenantRAG..."
    
    local compose_files=("-f" "docker-compose.yml")
    local compose_args=()
    
    case "$ENVIRONMENT" in
        development)
            compose_files+=("-f" "docker-compose.dev.yml")
            ;;
        production)
            compose_files+=("-f" "docker-compose.prod.yml")
            compose_args+=("--remove-orphans")
            ;;
    esac
    
    # Create necessary directories
    mkdir -p data/vector_stores logs
    
    # Deploy
    docker-compose "${compose_files[@]}" up -d "${compose_args[@]}"
    
    log_success "Deployment completed successfully"
}

# Show deployment status
show_status() {
    log_info "Deployment status:"
    
    local compose_files=("-f" "docker-compose.yml")
    
    case "$ENVIRONMENT" in
        development)
            compose_files+=("-f" "docker-compose.dev.yml")
            ;;
        production)
            compose_files+=("-f" "docker-compose.prod.yml")
            ;;
    esac
    
    docker-compose "${compose_files[@]}" ps
    
    # Show health status
    log_info "Health checks:"
    docker-compose "${compose_files[@]}" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
}

# Show logs
show_logs() {
    log_info "Showing logs (press Ctrl+C to exit)..."
    
    local compose_files=("-f" "docker-compose.yml")
    
    case "$ENVIRONMENT" in
        development)
            compose_files+=("-f" "docker-compose.dev.yml")
            ;;
        production)
            compose_files+=("-f" "docker-compose.prod.yml")
            ;;
    esac
    
    docker-compose "${compose_files[@]}" logs -f
}

# Stop deployment
stop_deployment() {
    log_info "Stopping deployment..."
    
    local compose_files=("-f" "docker-compose.yml")
    
    case "$ENVIRONMENT" in
        development)
            compose_files+=("-f" "docker-compose.dev.yml")
            ;;
        production)
            compose_files+=("-f" "docker-compose.prod.yml")
            ;;
    esac
    
    docker-compose "${compose_files[@]}" down
    log_success "Deployment stopped"
}

# Main deployment function
main() {
    cd "$PROJECT_DIR"
    
    # Parse options
    local build_flag=false
    local pull_flag=false
    local logs_flag=false
    local status_flag=false
    local stop_flag=false
    
    for arg in "$@"; do
        case $arg in
            --build)
                build_flag=true
                shift
                ;;
            --pull)
                pull_flag=true
                shift
                ;;
            --logs)
                logs_flag=true
                shift
                ;;
            --status)
                status_flag=true
                shift
                ;;
            --stop)
                stop_flag=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
        esac
    done
    
    # Handle stop flag
    if [[ "$stop_flag" == true ]]; then
        validate_environment
        stop_deployment
        exit 0
    fi
    
    # Handle status flag
    if [[ "$status_flag" == true ]]; then
        validate_environment
        show_status
        exit 0
    fi
    
    # Main deployment flow
    validate_environment
    check_prerequisites
    setup_environment
    validate_configuration
    
    if [[ "$pull_flag" == true ]]; then
        pull_images
    fi
    
    if [[ "$build_flag" == true ]]; then
        build_images
    fi
    
    deploy
    show_status
    
    if [[ "$logs_flag" == true ]]; then
        show_logs
    fi
    
    log_success "Deployment script completed successfully!"
    log_info "You can check logs with: docker-compose logs -f"
    log_info "You can stop the deployment with: $0 $ENVIRONMENT --stop"
}

# Run main function
main "$@"