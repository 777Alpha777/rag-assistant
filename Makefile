.PHONY: install migrate ingest run test lint eval up down

install:
	pip install -e ".[dev]"

migrate:
	alembic upgrade head

ingest:
	python -m scripts.ingest_corpus

run:
	uvicorn app.main:app --reload --port 8000

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .

eval:
	python -m scripts.evaluate

up:
	docker compose up --build -d

down:
	docker compose down -v
