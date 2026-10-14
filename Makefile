-include .env
export

LOCAL_DB = DB_HOST=localhost DB_PORT=55432
BACKEND = uv run --project backend

.PHONY: up down logs migrate ingest test lint fmt build deploy invoke-migrate

up:
	docker compose --profile local up -d --wait postgres
	$(MAKE) migrate
	docker compose up -d n8n

down:
	docker compose --profile local down

logs:
	docker compose logs -f n8n

migrate:
	$(LOCAL_DB) $(BACKEND) python -m loan_engine.migrate db/migrations

ingest:
	$(LOCAL_DB) $(BACKEND) python scripts/ingest_local.py $(FILE)

test:
	$(LOCAL_DB) $(BACKEND) pytest backend/tests -q

lint:
	$(BACKEND) ruff check backend scripts
	$(BACKEND) ruff format --check backend scripts

fmt:
	$(BACKEND) ruff check --fix backend scripts
	$(BACKEND) ruff format backend scripts

build:
	rm -rf .build && mkdir -p .build/lambda
	cd backend && uv export --no-dev --no-hashes --no-emit-project -q > ../.build/requirements.txt
	uv pip install -q --target .build/lambda --python-platform x86_64-manylinux2014 --python-version 3.12 -r .build/requirements.txt
	cp -r backend/src/loan_engine .build/lambda/
	cp -r db/migrations .build/lambda/loan_engine/migrations
	cd .build/lambda && zip -qr ../lambda.zip . -x '*__pycache__*'

deploy: build
	npx serverless@4 deploy --stage $(or $(STAGE),dev)

invoke-migrate:
	npx serverless@4 invoke --function migrate --stage $(or $(STAGE),dev)
