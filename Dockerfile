# Imagem da API (e do front estático). Python 3.14 com uv para instalar as dependências.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /srv

# Dependências primeiro: a camada só é refeita quando pyproject/uv.lock mudam.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY frontend ./frontend

ENV PATH="/srv/.venv/bin:$PATH"
EXPOSE 8000

# Sobe a API
CMD ["sh", "-c", "vicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
