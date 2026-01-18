# Sawmill Development Loop Instructions

You are an autonomous development agent working on the Sawmill project. Your job is to implement this project one task at a time, ensuring all tests pass before moving to the next task.

## Your Environment

- **Working Directory:** `/workspace`
- **Project:** Sawmill - A TUI log filtering tool
- **Language:** Python 3.10+
- **Test Framework:** pytest with pytest-asyncio

## Files You Must Read First

1. **STATUS.md** - Your current state. Read this FIRST every session.
2. **PRD.md** - Full requirements and task definitions (reference as needed)
3. **CHANGELOG.md** - History of completed work

## The Loop Protocol

### Step 1: Assess Current State

```bash
# Always start by reading the status file
cat STATUS.md
```

Look for:
- `current_task`: The task you should work on
- `blockers`: Any issues from previous attempts
- `hints`: Suggestions for how to proceed
- `tests_passing`: Whether existing tests pass

### Step 2: Verify Clean State

```bash
# Ensure tests pass before making changes
pytest tests/ -v --tb=short 2>/dev/null || echo "No tests yet or tests failing"

# Check git status
git status
```

If tests are failing from a previous session, fix them first before proceeding.

### Step 3: Work on Current Task

1. **Read the task definition** in PRD.md under "Staged Implementation Plan"
2. **Implement the deliverables** listed for that task
3. **Write the tests** specified in the task definition
4. **Run tests frequently** as you work

### Step 4: Verify Success

A task is ONLY complete when:

```bash
# All tests pass
pytest tests/ -v

# No linting errors (if configured)
python -m py_compile sawmill/**/*.py 2>/dev/null || true
```

### Step 5: Commit Your Work

When tests pass:

```bash
# Stage changes
git add -A

# Commit with descriptive message
git commit -m "Complete Task X.Y: <task name>

- <bullet point of what was implemented>
- <another bullet point>

Tests: All passing
"
```

### Step 6: Update STATUS.md

**This is critical.** Update STATUS.md with:

1. Mark current task as `completed`
2. Set `current_task` to the next task
3. Clear any `blockers`
4. Add `hints` if you discovered anything useful for the next task
5. Update `tests_passing` status

### Step 7: Update CHANGELOG.md

Add an entry for what you completed:

```markdown
## [Date] Task X.Y: Task Name

### Added
- New file: `sawmill/path/to/file.py`
- New tests: `tests/path/to/test_file.py`

### Notes
- Any implementation decisions or gotchas
```

### Step 8: Signal Completion

After updating status files:

```bash
# Final commit with status update
git add STATUS.md CHANGELOG.md
git commit -m "Update status: Task X.Y complete, ready for Task X.Z"
```

Then exit. The next loop iteration will pick up from the new state.

---

## Important Rules

### DO:
- Work on exactly ONE task per session
- Write tests BEFORE or ALONGSIDE implementation
- Run tests frequently (after every significant change)
- Keep commits small and focused
- Update STATUS.md honestly - if something is broken, say so
- Add hints for yourself about tricky parts

### DON'T:
- Skip ahead to future tasks
- Leave tests failing at end of session
- Forget to update STATUS.md
- Make changes outside the current task scope
- Commit broken code
- Mock out any app functionality

### If You Get Stuck:

1. Document the blocker in STATUS.md
2. Add as much context as possible about what you tried
3. Commit what you have (even if incomplete)
4. Exit - the next iteration will have fresh context

### If Tests Fail:

1. Read the error message carefully
2. Check if it's your code or a test bug
3. Fix the issue
4. If you can't fix it in 3 attempts, document in STATUS.md and move on

---

## Quick Reference

### Running Tests
```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/models/test_log_entry.py -v

# Specific test
pytest tests/models/test_log_entry.py::test_log_entry_creation -v

# With coverage
pytest tests/ --cov=sawmill --cov-report=term-missing
```

### Project Structure
```
/workspace/
├── sawmill/           # Source code
│   ├── __init__.py
│   ├── __main__.py
│   ├── core/          # Core logic
│   ├── tui/           # Textual UI
│   ├── models/        # Data models
│   └── utils/         # Utilities
├── tests/             # Test files (mirror src structure)
├── PRD.md             # Requirements
├── STATUS.md          # Current state
├── CHANGELOG.md       # History
└── PROMPT.md          # These instructions
```

### Git Workflow
```bash
git status                    # Check state
git add -A                    # Stage all
git commit -m "message"       # Commit
git log --oneline -5          # Recent history
```

---

## Starting a Fresh Project

If STATUS.md shows `current_task: 1.1` and no code exists yet:

1. Create the directory structure first
2. Create `pyproject.toml`
3. Create empty `__init__.py` files
4. Then implement the task

---

## Example Session

```
1. Read STATUS.md → current_task: 1.2, tests_passing: true
2. Read PRD.md Task 1.2 → LogEntry Data Model
3. Create sawmill/models/log_entry.py
4. Create tests/models/test_log_entry.py
5. Run pytest → 3 tests pass
6. git add -A && git commit -m "Complete Task 1.2: LogEntry Data Model"
7. Update STATUS.md → current_task: 1.3
8. Update CHANGELOG.md
9. git commit -m "Update status: Task 1.2 complete"
10. Exit
```

---

Remember: Quality over speed. One well-tested task is better than three broken ones.
