Phony: sync

sync:
	uv sync

run:
	uv run python main.py

test:
	uv run pytest tests/ -v