# Imagem da API e do front estático. Python 3.14 com uv; ffmpeg é exigido pelo yt-dlp.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# ffmpeg converte o áudio baixado; libsndfile é usada pelo soundfile.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# Dependências primeiro: a camada só é refeita quando pyproject/uv.lock mudam.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY frontend ./frontend

# DATABASE_URL (Postgres) vem de fora: do compose ou do ambiente de nuvem.
ENV PATH="/srv/.venv/bin:$PATH"
EXPOSE 8000

# Sobe a API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
