#!/bin/bash

# Final Validation Script for RAG Telegram Assistant
# Runs comprehensive validation including all tests and system checks

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VALIDATION_RESULTS_DIR="$PROJECT_DIR/validation_results"
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

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
FAILED_TEST_SUITES=()

# Test result functions
test_suite_passed() {
    ((PASSED_TESTS++))
    ((TOTAL_TESTS++))
    log_success "✓ $1"
}

test_suite_failed() {
    ((FAILED_TESTS++))
    ((TOTAL_TESTS++))
    FAILED_TEST_SUITES+=("$1")
    log_error "✗ $1"
}

# Setup validation environment
setup_validation_environment() {
    log_info "Setting up validation environment..."
    
    cd "$PROJECT_DIR"
    
    # Create validation results directory
    mkdir -p "$VALIDATION_RESULTS_DIR"
    
    # Create test environment
    if [[ ! -f ".env.testing" ]]; then
        cp ".env.example" ".env.testing"
        
        # Set test-specific values
        cat >> ".env.testing" << EOF

# Test configuration
BOT_TOKEN=test_bot_token_123456789
OPENAI_API_KEY=test_openai_key_sk-123456789
DEFAULT_LANG=fa
LOG_LEVEL=DEBUG
TESTING=true
EOF
    fi
    
    log_success "Validation environment setup completed"
}

# Run system validation
run_system_validation() {
    log_info "Running system validation..."
    
    if ./scripts/validate_system.sh > "$VALIDATION_RESULTS_DIR/system_validation_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "System Validation"
    else
        test_suite_failed "System Validation"
    fi
}

# Run unit tests
run_unit_tests() {
    log_info "Running unit tests..."
    
    if python -m pytest tests/unit/ -v --cov=ragbot --cov-report=html --cov-report=xml \
        --junit-xml="$VALIDATION_RESULTS_DIR/unit_tests_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/unit_tests_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Unit Tests"
    else
        test_suite_failed "Unit Tests"
    fi
}

# Run integration tests
run_integration_tests() {
    log_info "Running integration tests..."
    
    if python -m pytest tests/integration/ -v \
        --junit-xml="$VALIDATION_RESULTS_DIR/integration_tests_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/integration_tests_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Integration Tests"
    else
        test_suite_failed "Integration Tests"
    fi
}

# Run end-to-end tests
run_e2e_tests() {
    log_info "Running end-to-end tests..."
    
    if python -m pytest tests/e2e/ -v \
        --junit-xml="$VALIDATION_RESULTS_DIR/e2e_tests_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/e2e_tests_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "End-to-End Tests"
    else
        test_suite_failed "End-to-End Tests"
    fi
}

# Run performance tests
run_performance_tests() {
    log_info "Running performance tests..."
    
    if python -m pytest tests/performance/ -v \
        --junit-xml="$VALIDATION_RESULTS_DIR/performance_tests_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/performance_tests_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Performance Tests"
    else
        test_suite_failed "Performance Tests"
    fi
}

# Run final validation tests
run_final_validation_tests() {
    log_info "Running final validation tests..."
    
    # Complete system integration tests
    if python -m pytest tests/final_validation/test_complete_system.py -v \
        --junit-xml="$VALIDATION_RESULTS_DIR/complete_system_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/complete_system_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Complete System Integration"
    else
        test_suite_failed "Complete System Integration"
    fi
    
    # Security audit tests
    if python -m pytest tests/final_validation/test_security_audit.py -v \
        --junit-xml="$VALIDATION_RESULTS_DIR/security_audit_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/security_audit_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Security Audit"
    else
        test_suite_failed "Security Audit"
    fi
    
    # Load performance tests
    if python -m pytest tests/final_validation/test_load_performance.py -v \
        --junit-xml="$VALIDATION_RESULTS_DIR/load_performance_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/load_performance_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Load Performance"
    else
        test_suite_failed "Load Performance"
    fi
    
    # Multi-language support tests
    if python -m pytest tests/final_validation/test_multilingual_support.py -v \
        --junit-xml="$VALIDATION_RESULTS_DIR/multilingual_$TIMESTAMP.xml" \
        > "$VALIDATION_RESULTS_DIR/multilingual_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Multi-language Support"
    else
        test_suite_failed "Multi-language Support"
    fi
}

# Run integration test script
run_integration_script() {
    log_info "Running integration test script..."
    
    if ./scripts/integration_test.sh > "$VALIDATION_RESULTS_DIR/integration_script_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Integration Test Script"
    else
        test_suite_failed "Integration Test Script"
    fi
}

# Run code quality checks
run_code_quality_checks() {
    log_info "Running code quality checks..."
    
    # Linting with ruff
    if ruff check ragbot tests > "$VALIDATION_RESULTS_DIR/ruff_check_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Code Linting (Ruff)"
    else
        test_suite_failed "Code Linting (Ruff)"
    fi
    
    # Type checking with mypy
    if mypy ragbot > "$VALIDATION_RESULTS_DIR/mypy_check_$TIMESTAMP.log" 2>&1; then
        test_suite_passed "Type Checking (MyPy)"
    else
        test_suite_failed "Type Checking (MyPy)"
    fi
    
    # Security scanning with bandit
    if bandit -r ragbot -f json -o "$VALIDATION_RESULTS_DIR/bandit_report_$TIMESTAMP.json" > /dev/null 2>&1; then
        test_suite_passed "Security Scanning (Bandit)"
    else
        test_suite_failed "Security Scanning (Bandit)"
    fi
}

# Test Docker build
test_docker_build() {
    log_info "Testing Docker build..."
    
    if command -v docker &> /dev/null; then
        if docker build -t ragbot-validation-test . > "$VALIDATION_RESULTS_DIR/docker_build_$TIMESTAMP.log" 2>&1; then
            test_suite_passed "Docker Build"
            
            # Clean up test image
            docker rmi ragbot-validation-test > /dev/null 2>&1 || true
        else
            test_suite_failed "Docker Build"
        fi
    else
        log_warning "Docker not available, skipping Docker build test"
    fi
}

# Generate comprehensive validation report
generate_validation_report() {
    log_info "Generating comprehensive validation report..."
    
    local success_rate=0
    if [[ $TOTAL_TESTS -gt 0 ]]; then
        success_rate=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
    fi
    
    # Create comprehensive report
    cat > "$VALIDATION_RESULTS_DIR/final_validation_report_$TIMESTAMP.md" << EOF
# RAG Telegram Assistant - Final Validation Report

**Generated:** $(date)  
**Validation ID:** $TIMESTAMP

## Executive Summary

- **Total Test Suites:** $TOTAL_TESTS
- **Passed:** $PASSED_TESTS
- **Failed:** $FAILED_TESTS
- **Success Rate:** $success_rate%

## Test Results Summary

### Passed Test Suites ✅
$(for i in $(seq 0 $((${#FAILED_TEST_SUITES[@]} - 1))); do
    echo "- ${FAILED_TEST_SUITES[i]}"
done)

### Failed Test Suites ❌
$(if [[ $FAILED_TESTS -gt 0 ]]; then
    for suite in "${FAILED_TEST_SUITES[@]}"; do
        echo "- $suite"
    done
else
    echo "None"
fi)

## Detailed Results

### System Validation
- Configuration validation
- Project structure verification
- Dependency checks
- Security configuration

### Code Quality
- Linting (Ruff)
- Type checking (MyPy)
- Security scanning (Bandit)

### Testing Coverage
- Unit tests
- Integration tests
- End-to-end tests
- Performance tests
- Security audit
- Multi-language support

### Infrastructure
- Docker build validation
- Deployment configuration
- Monitoring setup

## System Status

$(if [[ $FAILED_TESTS -eq 0 ]]; then
    echo "🎉 **SYSTEM READY FOR PRODUCTION DEPLOYMENT**"
    echo ""
    echo "All validation tests have passed successfully. The RAG Telegram Assistant is ready for production deployment."
elif [[ $success_rate -ge 80 ]]; then
    echo "⚠️ **SYSTEM READY WITH WARNINGS**"
    echo ""
    echo "Most validation tests have passed, but some issues need attention before production deployment."
else
    echo "❌ **SYSTEM NOT READY FOR DEPLOYMENT**"
    echo ""
    echo "Critical issues found that must be resolved before deployment."
fi)

## Next Steps

$(if [[ $FAILED_TESTS -eq 0 ]]; then
    echo "1. Proceed with production deployment"
    echo "2. Set up monitoring and alerting"
    echo "3. Configure backup procedures"
    echo "4. Establish maintenance schedule"
else
    echo "1. Review failed test suites and resolve issues"
    echo "2. Re-run validation after fixes"
    echo "3. Update documentation as needed"
    echo "4. Consider additional testing if major changes made"
fi)

## Files Generated

- System validation log: \`system_validation_$TIMESTAMP.log\`
- Unit test results: \`unit_tests_$TIMESTAMP.xml\`
- Integration test results: \`integration_tests_$TIMESTAMP.xml\`
- Performance test results: \`performance_tests_$TIMESTAMP.xml\`
- Security audit results: \`security_audit_$TIMESTAMP.xml\`
- Code coverage report: \`htmlcov/index.html\`

## Contact

For questions about this validation report, please contact the development team.

---
*Generated by RAG Telegram Assistant Final Validation System*
EOF

    # Create summary file
    cat > "$VALIDATION_RESULTS_DIR/validation_summary_$TIMESTAMP.txt" << EOF
RAG Telegram Assistant - Validation Summary
==========================================

Timestamp: $TIMESTAMP
Total Tests: $TOTAL_TESTS
Passed: $PASSED_TESTS
Failed: $FAILED_TESTS
Success Rate: $success_rate%

Status: $(if [[ $FAILED_TESTS -eq 0 ]]; then
    echo "READY FOR DEPLOYMENT ✅"
elif [[ $success_rate -ge 80 ]]; then
    echo "READY WITH WARNINGS ⚠️"
else
    echo "NOT READY - ISSUES MUST BE RESOLVED ❌"
fi)
EOF

    log_success "Validation report generated: $VALIDATION_RESULTS_DIR/final_validation_report_$TIMESTAMP.md"
}

# Display final results
display_final_results() {
    echo
    echo "=========================================="
    echo "    FINAL VALIDATION RESULTS"
    echo "=========================================="
    echo "Total Test Suites: $TOTAL_TESTS"
    echo "Passed: $PASSED_TESTS"
    echo "Failed: $FAILED_TESTS"
    echo "Success Rate: $(( TOTAL_TESTS > 0 ? (PASSED_TESTS * 100) / TOTAL_TESTS : 0 ))%"
    echo
    
    if [[ $FAILED_TESTS -gt 0 ]]; then
        echo "Failed Test Suites:"
        for suite in "${FAILED_TEST_SUITES[@]}"; do
            echo "  - $suite"
        done
        echo
    fi
    
    if [[ $FAILED_TESTS -eq 0 ]]; then
        log_success "🎉 ALL VALIDATIONS PASSED!"
        log_success "The RAG Telegram Assistant is ready for production deployment."
    elif [[ $(( (PASSED_TESTS * 100) / TOTAL_TESTS )) -ge 80 ]]; then
        log_warning "⚠️  VALIDATION COMPLETED WITH WARNINGS"
        log_warning "Most tests passed, but some issues need attention."
    else
        log_error "❌ VALIDATION FAILED"
        log_error "Critical issues must be resolved before deployment."
    fi
    
    echo
    log_info "Detailed results available in: $VALIDATION_RESULTS_DIR/"
    log_info "Main report: final_validation_report_$TIMESTAMP.md"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up validation environment..."
    
    # Remove temporary test files
    [[ -f ".env.testing" ]] && rm -f ".env.testing"
    
    # Clean up any test containers
    docker ps -a --filter "name=ragbot-validation" --format "{{.ID}}" | xargs -r docker rm -f > /dev/null 2>&1 || true
    
    log_info "Cleanup completed"
}

# Set up cleanup trap
trap cleanup EXIT

# Main validation function
main() {
    log_info "Starting comprehensive final validation of RAG Telegram Assistant..."
    echo "This will run all tests and validations to ensure system readiness."
    echo
    
    # Setup environment
    setup_validation_environment
    
    # Run all validations
    run_system_validation
    run_code_quality_checks
    test_docker_build
    run_unit_tests
    run_integration_tests
    run_e2e_tests
    run_performance_tests
    run_final_validation_tests
    run_integration_script
    
    # Generate comprehensive report
    generate_validation_report
    
    # Display results
    display_final_results
    
    # Exit with appropriate code
    if [[ $FAILED_TESTS -eq 0 ]]; then
        exit 0
    else
        exit 1
    fi
}

# Run main function
main "$@"