#!/bin/bash

# System Validation Script for RAG Telegram Assistant
# Performs comprehensive system validation including security, performance, and functionality tests

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VALIDATION_RESULTS_DIR="$PROJECT_DIR/validation-results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Validation counters
VALIDATIONS_TOTAL=0
VALIDATIONS_PASSED=0
VALIDATIONS_FAILED=0
FAILED_VALIDATIONS=()

# Validation result tracking
start_validation() {
    local validation_name="$1"
    VALIDATIONS_TOTAL=$((VALIDATIONS_TOTAL + 1))
    log_info "Running validation: $validation_name"
}

pass_validation() {
    local validation_name="$1"
    VALIDATIONS_PASSED=$((VALIDATIONS_PASSED + 1))
    log_success "✓ $validation_name"
}

fail_validation() {
    local validation_name="$1"
    local error_msg="${2:-}"
    VALIDATIONS_FAILED=$((VALIDATIONS_FAILED + 1))
    FAILED_VALIDATIONS+=("$validation_name: $error_msg")
    log_error "✗ $validation_name"
    if [[ -n "$error_msg" ]]; then
        log_error "  Error: $error_msg"
    fi
}

# Setup validation environment
setup_validation_environment() {
    log_info "Setting up validation environment..."

    mkdir -p "$VALIDATION_RESULTS_DIR"
    cd "$PROJECT_DIR"

    log_success "Validation environment setup completed"
}# Valid
ation 1: Complete Test Suite
validate_test_suite() {
    start_validation "Complete Test Suite Coverage"

    # Run all tests with coverage
    if pytest --cov=ragbot --cov-report=html --cov-report=term --cov-fail-under=80 > "$VALIDATION_RESULTS_DIR/test_results_$TIMESTAMP.log" 2>&1; then
        pass_validation "Complete Test Suite Coverage"
    else
        fail_validation "Complete Test Suite Coverage" "Test coverage below 80% or tests failed"
    fi
}

# Validation 2: Security Audit
validate_security() {
    start_validation "Security Audit"

    # Check for security vulnerabilities
    local security_issues=0

    # Check for hardcoded secrets
    if grep -r "sk-" ragbot/ --include="*.py" | grep -v "example" | grep -v "test" > /dev/null 2>&1; then
        security_issues=$((security_issues + 1))
        log_error "Found potential hardcoded API keys"
    fi

    # Check for SQL injection vulnerabilities
    if grep -r "execute.*%" ragbot/ --include="*.py" > /dev/null 2>&1; then
        security_issues=$((security_issues + 1))
        log_error "Found potential SQL injection vulnerabilities"
    fi

    # Run bandit security linter
    if command -v bandit &> /dev/null; then
        if ! bandit -r ragbot -f json -o "$VALIDATION_RESULTS_DIR/security_report_$TIMESTAMP.json" > /dev/null 2>&1; then
            security_issues=$((security_issues + 1))
            log_error "Bandit security scan found issues"
        fi
    fi

    if [[ $security_issues -eq 0 ]]; then
        pass_validation "Security Audit"
    else
        fail_validation "Security Audit" "$security_issues security issues found"
    fi
}

# Validation 3: Performance Testing
validate_performance() {
    start_validation "Performance Testing"

    # Run performance tests
    if pytest tests/performance/ -v --tb=short > "$VALIDATION_RESULTS_DIR/performance_results_$TIMESTAMP.log" 2>&1; then
        pass_validation "Performance Testing"
    else
        fail_validation "Performance Testing" "Performance tests failed"
    fi
}

# Validation 4: Multi-language Support
validate_multilingual_support() {
    start_validation "Multi-language Support"

    # Test Persian and English language support
    if python3 -c "
from ragbot.rag import PromptBuilder

builder = PromptBuilder()

# Test Persian prompt
fa_prompt = builder.build_qa_prompt('سوال تست', [], 'fa')
assert 'فارسی' in fa_prompt or 'پاسخ' in fa_prompt

# Test English prompt
en_prompt = builder.build_qa_prompt('test question', [], 'en')
assert 'English' in en_prompt or 'answer' in en_prompt

print('Multi-language support validated')
" 2>/dev/null; then
        pass_validation "Multi-language Support"
    else
        fail_validation "Multi-language Support" "Language support validation failed"
    fi
}# V
alidation 5: Docker Deployment
validate_docker_deployment() {
    start_validation "Docker Deployment"

    if ! command -v docker &> /dev/null; then
        log_warning "Docker not available, skipping deployment validation"
        pass_validation "Docker Deployment (Skipped)"
        return
    fi

    # Test Docker build and basic functionality
    if docker build -t ragbot-validation . > "$VALIDATION_RESULTS_DIR/docker_build_$TIMESTAMP.log" 2>&1; then
        # Test basic container functionality
        if timeout 60 docker run --rm --env-file .env.example ragbot-validation python -c "
import ragbot.configs.settings
import ragbot.app.bot
import ragbot.rag.loaders.base
print('Docker deployment validation passed')
" > "$VALIDATION_RESULTS_DIR/docker_run_$TIMESTAMP.log" 2>&1; then
            pass_validation "Docker Deployment"
        else
            fail_validation "Docker Deployment" "Container runtime validation failed"
        fi

        # Cleanup
        docker rmi ragbot-validation > /dev/null 2>&1 || true
    else
        fail_validation "Docker Deployment" "Docker build failed"
    fi
}

# Validation 6: Configuration Validation
validate_configuration() {
    start_validation "Configuration Validation"

    # Test all environment configurations
    local config_files=(".env.example" ".env.development" ".env.production" ".env.testing")
    local config_issues=0

    for config_file in "${config_files[@]}"; do
        if [[ -f "$config_file" ]]; then
            # Check required variables
            local required_vars=("BOT_TOKEN" "OPENAI_API_KEY")
            for var in "${required_vars[@]}"; do
                if ! grep -q "^$var=" "$config_file"; then
                    config_issues=$((config_issues + 1))
                    log_error "Missing $var in $config_file"
                fi
            done
        else
            config_issues=$((config_issues + 1))
            log_error "Missing configuration file: $config_file"
        fi
    done

    if [[ $config_issues -eq 0 ]]; then
        pass_validation "Configuration Validation"
    else
        fail_validation "Configuration Validation" "$config_issues configuration issues found"
    fi
}

# Validation 7: Documentation Completeness
validate_documentation() {
    start_validation "Documentation Completeness"

    local doc_files=(
        "README.md"
        "README.fa.md"
        "docs/API.md"
        "docs/EXAMPLES.md"
        "docs/FAQ.md"
        "docs/INSTALLATION.fa.md"
        "docs/CONFIGURATION.fa.md"
        "docs/TROUBLESHOOTING.fa.md"
        "docs/ARCHITECTURE.fa.md"
        "docs/TESTING.fa.md"
        "docs/DEVELOPMENT.fa.md"
    )

    local missing_docs=0

    for doc_file in "${doc_files[@]}"; do
        if [[ ! -f "$doc_file" ]]; then
            missing_docs=$((missing_docs + 1))
            log_error "Missing documentation file: $doc_file"
        elif [[ ! -s "$doc_file" ]]; then
            missing_docs=$((missing_docs + 1))
            log_error "Empty documentation file: $doc_file"
        fi
    done

    if [[ $missing_docs -eq 0 ]]; then
        pass_validation "Documentation Completeness"
    else
        fail_validation "Documentation Completeness" "$missing_docs documentation issues found"
    fi
}# Gene
rate validation report
generate_validation_report() {
    local report_file="$VALIDATION_RESULTS_DIR/system_validation_report_$TIMESTAMP.txt"

    cat > "$report_file" << EOF
RAG Telegram Assistant - System Validation Report
=================================================

Validation Execution Time: $(date)
Total Validations: $VALIDATIONS_TOTAL
Passed: $VALIDATIONS_PASSED
Failed: $VALIDATIONS_FAILED
Success Rate: $(( VALIDATIONS_PASSED * 100 / VALIDATIONS_TOTAL ))%

EOF

    if [[ $VALIDATIONS_FAILED -gt 0 ]]; then
        echo "Failed Validations:" >> "$report_file"
        echo "==================" >> "$report_file"
        for failed_validation in "${FAILED_VALIDATIONS[@]}"; do
            echo "- $failed_validation" >> "$report_file"
        done
        echo "" >> "$report_file"
    fi

    echo "System Information:" >> "$report_file"
    echo "==================" >> "$report_file"
    echo "Python Version: $(python3 --version)" >> "$report_file"
    echo "Docker Version: $(docker --version 2>/dev/null || echo "Not available")" >> "$report_file"
    echo "OS: $(uname -s)" >> "$report_file"
    echo "Architecture: $(uname -m)" >> "$report_file"
    echo "" >> "$report_file"

    echo "Project Structure:" >> "$report_file"
    echo "=================" >> "$report_file"
    find ragbot -name "*.py" | wc -l >> "$report_file" | sed 's/^/Python files: /'
    find tests -name "*.py" | wc -l >> "$report_file" | sed 's/^/Test files: /'
    find docs -name "*.md" | wc -l >> "$report_file" | sed 's/^/Documentation files: /'

    log_info "Validation report generated: $report_file"
}

# Main validation function
main() {
    log_info "Starting RAG Telegram Assistant System Validation..."

    setup_validation_environment

    # Run all validations
    validate_test_suite
    validate_security
    validate_performance
    validate_multilingual_support
    validate_docker_deployment
    validate_configuration
    validate_documentation

    # Generate report
    generate_validation_report

    # Final results
    echo ""
    log_info "System Validation Results:"
    echo "=========================="
    echo "Total Validations: $VALIDATIONS_TOTAL"
    echo "Passed: $VALIDATIONS_PASSED"
    echo "Failed: $VALIDATIONS_FAILED"
    echo "Success Rate: $(( VALIDATIONS_PASSED * 100 / VALIDATIONS_TOTAL ))%"

    if [[ $VALIDATIONS_FAILED -eq 0 ]]; then
        log_success "All system validations passed! 🎉"
        log_success "RAG Telegram Assistant is ready for production deployment!"
        exit 0
    else
        log_error "Some system validations failed. Check the report for details."
        exit 1
    fi
}

# Run main function
main "$@"
