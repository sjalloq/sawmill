#!/usr/bin/env bash
#
# ralph-loop.sh - Autonomous development loop for Sawmill
#
# This script runs Claude Code in a Docker container, allowing it to
# implement the project one task at a time.
#
# Usage:
#   ./ralph-loop.sh [OPTIONS]
#
# Options:
#   --iterations N    Run N iterations (default: 1)
#   --continuous      Run until all tasks complete or error
#   --dry-run         Show what would be done without executing
#   --no-docker       Run directly on host (for testing)
#   --interactive     Drop into interactive shell after each iteration
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="sawmill"
DOCKER_IMAGE="sawmill-dev"
CONTAINER_NAME="sawmill-ralph-loop"
WORKSPACE_DIR="${SCRIPT_DIR}"
CLAUDE_AUTH_DIR="${HOME}/.claude"

# Get git config from host for use in container
GIT_USER_NAME="$(git config --global user.name 2>/dev/null || echo "Developer")"
GIT_USER_EMAIL="$(git config --global user.email 2>/dev/null || echo "developer@localhost")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
ITERATIONS=1
CONTINUOUS=false
DRY_RUN=false
USE_DOCKER=true
INTERACTIVE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        --continuous)
            CONTINUOUS=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --no-docker)
            USE_DOCKER=false
            shift
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        --help|-h)
            head -20 "$0" | tail -18
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check for required files
    local required_files=("PRD.md" "PROMPT.md" "STATUS.md")
    for file in "${required_files[@]}"; do
        if [[ ! -f "${WORKSPACE_DIR}/${file}" ]]; then
            log_error "Required file missing: ${file}"
            exit 1
        fi
    done

    if [[ "$USE_DOCKER" == true ]]; then
        # Check Docker
        if ! command -v docker &> /dev/null; then
            log_error "Docker is not installed"
            exit 1
        fi

        # Check if Docker daemon is running
        if ! docker info &> /dev/null; then
            log_error "Docker daemon is not running"
            exit 1
        fi
    fi

    # Check for Claude Code auth (Max plan uses ~/.claude/)
    if [[ ! -d "${CLAUDE_AUTH_DIR}" ]]; then
        log_error "Claude auth directory not found: ${CLAUDE_AUTH_DIR}"
        log_error "Please ensure Claude Code is installed and you're logged in"
        exit 1
    fi

    if [[ ! -f "${CLAUDE_AUTH_DIR}/.credentials.json" ]]; then
        log_error "Claude credentials not found. Please run 'claude' and log in first."
        exit 1
    fi

    log_success "Prerequisites check passed"
    log_info "Using Claude auth from: ${CLAUDE_AUTH_DIR}"
}

# Build Docker image
build_docker_image() {
    if [[ "$USE_DOCKER" != true ]]; then
        return 0
    fi

    log_info "Building Docker image: ${DOCKER_IMAGE}..."

    if [[ "$DRY_RUN" == true ]]; then
        echo "Would run: docker build -t ${DOCKER_IMAGE} ${WORKSPACE_DIR}"
        return 0
    fi

    docker build -t "${DOCKER_IMAGE}" "${WORKSPACE_DIR}"
    log_success "Docker image built successfully"
}

# Get current task from STATUS.md
get_current_task() {
    grep -E "^\| \*\*current_task\*\*" "${WORKSPACE_DIR}/STATUS.md" | \
        sed 's/.*`\([^`]*\)`.*/\1/' || echo "unknown"
}

# Check if project is complete
is_project_complete() {
    local status_file="${WORKSPACE_DIR}/STATUS.md"
    # Check if all tasks are marked complete (no unchecked boxes in progress section)
    local incomplete=$(grep -E "^- \[ \]" "$status_file" | wc -l)
    [[ "$incomplete" -eq 0 ]]
}

# Check if current task is blocked
is_blocked() {
    grep -q "blocked.*true" "${WORKSPACE_DIR}/STATUS.md"
}

# Run single iteration
run_iteration() {
    local iteration_num=$1
    local current_task=$(get_current_task)

    log_info "=== Iteration ${iteration_num} ==="
    log_info "Current task: ${current_task}"

    if is_blocked; then
        log_warning "Task is blocked. Check STATUS.md for details."
        if [[ "$CONTINUOUS" != true ]]; then
            return 1
        fi
    fi

    # Prepare the prompt for Claude
    local claude_prompt="Read PROMPT.md for instructions, then read STATUS.md to understand current state. Work on the current task (${current_task}) following the loop protocol. When complete, update STATUS.md and commit your changes."

    if [[ "$DRY_RUN" == true ]]; then
        echo "Would run Claude Code with prompt:"
        echo "  ${claude_prompt}"
        return 0
    fi

    if [[ "$USE_DOCKER" == true ]]; then
        run_in_docker "$claude_prompt"
    else
        run_on_host "$claude_prompt"
    fi

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_success "Iteration ${iteration_num} completed successfully"
    else
        log_error "Iteration ${iteration_num} failed with exit code ${exit_code}"
    fi

    return $exit_code
}

# Run Claude Code in Docker
run_in_docker() {
    local prompt="$1"

    log_info "Starting Docker container..."

    # Stop any existing container
    docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

    # Run Claude Code in container
    # Mount both workspace and Claude auth directory
    # Note: .claude directory needs write access for session data, todos, etc.
    # --dangerously-skip-permissions: Allow autonomous operation without prompts
    # -p: Non-interactive mode with prompt (streams output so you can Ctrl-C if needed)
    docker run \
        --name "${CONTAINER_NAME}" \
        --rm \
        -it \
        -v "${WORKSPACE_DIR}:/workspace" \
        -v "${CLAUDE_AUTH_DIR}:/home/developer/.claude" \
        -e "HOME=/home/developer" \
        -e "PYTHONUNBUFFERED=1" \
        -e "GIT_USER_NAME=${GIT_USER_NAME}" \
        -e "GIT_USER_EMAIL=${GIT_USER_EMAIL}" \
        -w /workspace \
        "${DOCKER_IMAGE}" \
        bash -c "git config --global user.name \"\${GIT_USER_NAME}\" && git config --global user.email \"\${GIT_USER_EMAIL}\" && claude --dangerously-skip-permissions -p \"${prompt}\""

    return $?
}

# Run Claude Code directly on host
run_on_host() {
    local prompt="$1"

    log_info "Running Claude Code on host..."

    cd "${WORKSPACE_DIR}"
    claude \
        --dangerously-skip-permissions \
        --print \
        "${prompt}"

    return $?
}

# Interactive mode - drop into shell
run_interactive() {
    if [[ "$USE_DOCKER" == true ]]; then
        log_info "Starting interactive Docker shell..."
        docker run \
            --name "${CONTAINER_NAME}-interactive" \
            --rm \
            -it \
            -v "${WORKSPACE_DIR}:/workspace" \
            -v "${CLAUDE_AUTH_DIR}:/home/developer/.claude" \
            -e "HOME=/home/developer" \
            -e "GIT_USER_NAME=${GIT_USER_NAME}" \
            -e "GIT_USER_EMAIL=${GIT_USER_EMAIL}" \
            -w /workspace \
            "${DOCKER_IMAGE}" \
            bash -c "git config --global user.name \"\${GIT_USER_NAME}\" && git config --global user.email \"\${GIT_USER_EMAIL}\" && exec bash"
    else
        log_info "Starting interactive shell..."
        cd "${WORKSPACE_DIR}"
        exec bash
    fi
}

# Main loop
main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║           RALPH LOOP - Autonomous Development             ║"
    echo "║                    Project: Sawmill                       ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""

    check_prerequisites

    if [[ "$USE_DOCKER" == true ]]; then
        build_docker_image
    fi

    local iteration=1
    local max_iterations=$ITERATIONS

    if [[ "$CONTINUOUS" == true ]]; then
        max_iterations=999  # Effectively unlimited
    fi

    while [[ $iteration -le $max_iterations ]]; do
        # Check if project is complete
        if is_project_complete; then
            log_success "🎉 All tasks complete! Project finished."
            break
        fi

        # Run iteration
        if ! run_iteration $iteration; then
            if [[ "$CONTINUOUS" != true ]]; then
                log_error "Iteration failed. Stopping."
                exit 1
            fi
            log_warning "Iteration failed but continuing (--continuous mode)"
        fi

        # Interactive pause if requested
        if [[ "$INTERACTIVE" == true ]]; then
            echo ""
            read -p "Press Enter to continue, 'i' for interactive shell, 'q' to quit: " choice
            case $choice in
                i|I)
                    run_interactive
                    ;;
                q|Q)
                    log_info "Quitting at user request"
                    exit 0
                    ;;
            esac
        fi

        ((iteration++))

        # Small delay between iterations
        if [[ $iteration -le $max_iterations ]]; then
            sleep 2
        fi
    done

    echo ""
    log_info "=== Loop Summary ==="
    log_info "Iterations completed: $((iteration - 1))"
    log_info "Final task: $(get_current_task)"

    if is_project_complete; then
        log_success "Project status: COMPLETE"
    else
        log_info "Project status: IN PROGRESS"
    fi
}

# Run main
main
