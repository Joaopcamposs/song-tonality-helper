# Atalhos de desenvolvimento. Uso: make <alvo>.
.PHONY: run test ruff ty up down

# Sobe a API local com recarga automática (http://localhost:8007).
run:
	uv run uvicorn app.main:app --reload --port 8007

# Roda só o teste informado: make test T=tests/test_notes.py
test:
	uv run pytest -x --tb=short -q $(T)

# Lint + formatação.
ruff:
	uv run ruff check . && uv run ruff format --check .

# Checagem de tipos.
ty:
	uv run ty check app tests

# Sobe a API no Docker (http://localhost:8007), reconstruindo a imagem e trocando o contêiner
# anterior, se houver; o banco fica no volume.
up:
	docker build -t song-tonality-helper . && (docker rm -f song-tonality-helper >/dev/null 2>&1 || true) && docker run -d --rm --name song-tonality-helper -p 8007:8000 -v song-tonality-data:/srv/data song-tonality-helper

# Derruba o contêiner da API.
down:
	docker stop song-tonality-helper

build-up:
	docker compose up -d --build
