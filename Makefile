.PHONY: init lint fmt test ci hooks

init:
	python -m pip install --upgrade pip
	pip install -r requirements.txt || true
	pip install -r requirements-dev.txt
	pre-commit install

lint:
	ruff check .
	isort --check-only .
	black --check .

fmt:
	isort .
	black .
	ruff check . --fix

test:
	pytest -q

ci: lint test

hooks:
	pre-commit run --all-files
