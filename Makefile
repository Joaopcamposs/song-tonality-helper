# Atalhos de desenvolvimento. Uso: make <alvo>.
.PHONY: up down db ruff ty

# Sobe API e Postgres no Docker (http://localhost:8000), reconstruindo a imagem.
up:
	docker compose up -d --build --wait

# Derruba o ambiente do Docker (os dados do Postgres ficam no volume).
down:
	docker compose down

# Sobe só o Postgres de desenvolvimento (para rodar a API local com `make run`).
db:
	docker compose up -d --wait postgres

# Lint + formatação.
ruff:
	uv run ruff check . && uv run ruff format --check .

# Checagem de tipos.
ty:
	uv run ty check app tests scripts
