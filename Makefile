.PHONY: test
test:
	uv run pytest tests

.PHONY: format
format:
	uv run ruff check --fix --select I
	uv run ruff check --fix
	uv run ruff format

.PHONY: lint
lint:
	uv run ruff check --select I
	uv run ruff chec
	uv run ruff format --check