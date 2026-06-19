#!/bin/bash
set -e

echo "=== Installing dependencies ==="
uv sync --group dev

echo ""
echo "=== Running lint ==="
uv run ruff check app/

echo ""
echo "=== Running tests ==="
uv run pytest -v --cov --cov-report=term-missing "$@"

echo ""
echo "=== All checks passed ==="
