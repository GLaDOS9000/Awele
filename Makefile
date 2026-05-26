.PHONY: install lint test ci play play-random pre-commit

install:
	uv sync --all-extras
	uv run pre-commit install

lint:
	uv run ty check

test:
	uv run pytest tests/ -q

ci: lint test

play:
	uv run main.py --mode gui

play-random:
	uv run main.py --mode gui --p0 random --p1 random

pre-commit:
	uv run pre-commit run --all-files
