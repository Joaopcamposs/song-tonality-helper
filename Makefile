# Atalhos de desenvolvimento. Uso: make <alvo>.
.PHONY: db run worker test ruff ty up down build-up deploy

# Postgres local do compose (porta 5432). Sobrescreva no ambiente para usar outro banco.
export DATABASE_URL ?= postgresql+asyncpg://postgres:dev@localhost:5432/song_tonality
# Banco separado para os testes, porque a fixture apaga o schema a cada teste.
export TEST_DATABASE_URL ?= postgresql+asyncpg://postgres:dev@localhost:5432/song_tonality_test

# Sobe só o Postgres do compose e garante o banco de testes (idempotente).
db:
	docker compose up -d --wait db
	docker compose exec -T db psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='song_tonality_test'" | grep -q 1 || docker compose exec -T db createdb -U postgres song_tonality_test

# Sobe a API local com recarga automática (http://localhost:8007).
run: db
	uv run uvicorn app.main:app --reload --port 8007

# Sobe o worker local, que processa os jobs pendentes do banco (precisa da API gravando no mesmo DATABASE_URL).
worker: db
	uv run python -m app.worker

# Roda só o teste informado: make test T=tests/test_notes.py
test: db
	uv run pytest -x --tb=short -q $(T)

# Lint + formatação.
ruff:
	uv run ruff check . && uv run ruff format --check .

# Checagem de tipos.
ty:
	uv run ty check app tests

# Sobe tudo pelo compose (db, API, worker e túnel) sem reconstruir a imagem.
up:
	docker compose up -d

# Derruba os serviços do compose; o volume do banco é mantido.
down:
	docker compose down

# Sobe tudo pelo compose, reconstruindo a imagem.
build-up:
	docker compose up -d --build

# Publica a API no FastAPI Cloud (DATABASE_URL e APP_PASSPHRASE ficam nas variáveis do app na nuvem).
deploy:
	uv run fastapi deploy
