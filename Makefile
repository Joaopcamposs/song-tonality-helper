# Atalhos de desenvolvimento. Uso: make <alvo>.
.PHONY: db run worker worker-remote worker-remote-logs worker-remote-down test ruff ty up down build-up deploy

# Postgres local do compose (porta 5432). Sobrescreva no ambiente para usar outro banco.
export DATABASE_URL ?= postgresql+asyncpg://postgres:dev@localhost:5432/song_tonality
# Banco separado para os testes, porque a fixture apaga o schema a cada teste.
export TEST_DATABASE_URL ?= postgresql+asyncpg://postgres:dev@localhost:5432/song_tonality_test
UV_RUN = uv run

# Sobe só o Postgres do compose e garante o banco de testes (idempotente).
db:
	docker compose up -d --wait db
	docker compose exec -T db psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='song_tonality_test'" | grep -q 1 || docker compose exec -T db createdb -U postgres song_tonality_test

# Sobe a API local com recarga automática (http://localhost:8007).
run: db
	$(UV_RUN) uvicorn app.main:app --reload --port 8007

# Sobe o worker local, que processa os jobs pendentes do banco (precisa da API gravando no mesmo DATABASE_URL).
worker: db
	$(UV_RUN) python -m app.worker

# Roda só o teste informado: make test T=tests/test_notes.py
test: db
	$(UV_RUN) pytest -x --tb=short -q $(T)

# Lint + formatação.
ruff:
	$(UV_RUN) ruff check . && $(UV_RUN) ruff format --check .

# Checagem de tipos.
ty:
	$(UV_RUN) ty check app tests

# Sobe o worker no Docker (em segundo plano) contra o banco remoto: DATABASE_URL e PROXY_* vêm do .env.
# Reinicia sozinho; veja o log com `make worker-remote-logs` e pare com `make worker-remote-down`.
worker-remote:
	@test -f .env || { echo "Crie o .env com DATABASE_URL=<banco remoto>"; exit 1; }
	docker compose --profile remote up -d --build worker-remote

# Acompanha o log do worker remoto (Ctrl+C só sai do log, o worker continua rodando).
worker-remote-logs:
	docker compose --profile remote logs -f --tail=50 worker-remote

# Para e remove o contêiner do worker remoto.
worker-remote-down:
	docker compose --profile remote rm -sf worker-remote

# Sobe tudo pelo compose (db, API e worker) sem reconstruir a imagem.
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
