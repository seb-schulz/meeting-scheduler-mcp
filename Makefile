# Makefile for meeting-scheduler-mcp

.PHONY: test lint clean

# Install project in editable mode with dev dependencies
install:
	uv pip install -e ".[dev]"

# Run tests
test:
	uv run pytest tests/ -v

# Run linter
lint:
	uv run ruff check . --fix

# Clean up
clean:
	rm -rf .pytest_cache
	rm -rf __pycache__
	rm -rf tests/__pycache__
	rm -f test_calendar.yaml

# Run both test and lint
check: test lint

# Run server
run:
	uv run python -m meeting_scheduler_mcp
