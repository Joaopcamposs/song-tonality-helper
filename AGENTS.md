# AGENTS.md

Apresentação do produto em `README.md`; decisões em `docs/superpowers/specs/`. Projeto pessoal que evolui por fases pequenas. Código simples e direto; sem abstração antes da hora.

## Regras de código

- **Simplicidade primeiro:** sem `Protocol`, interfaces abstratas ou camadas extras até a complexidade pedir. Mudança mínima e focada; não refatore o que não foi pedido.
- **Estrutura:** `app/routers/` (HTTP; traduz `DomainError` em status), `app/domain/` (regras puras: `notes`, `features`, `pitch`, `key`, `transposition`, `errors`, `schemas`), `app/services/` (`youtube`, `download`, `jobs`, `report`, `store`), `app/worker.py` (execução dos jobs), `frontend/` (estático), `tests/`. Router só traduz HTTP; sem regra de negócio nele.
- **Módulos de áudio:** `yt-dlp`, `librosa`, `scipy` e `soundfile` são dependências normais (a API na nuvem também baixa, no experimento do proxy). Só `app/worker.py`, `app/domain/pitch.py` e `app/services/download.py` as importam. `ALGO_VERSION` e `AudioFeatures` vivem em `app/domain/features.py`.
- **Extração na API (`extract_now`):** por padrão o `POST /api/analyses` só enfileira; a API nunca baixa sozinha. Com `extract_now`, agenda `worker.extract_in_api`, com prazo de `EXTRACT_TIMEOUT_SECONDS` (60 s) para download e análise juntos; estourou ou falhou o download, o job volta a `pending` para o worker. A thread do `asyncio.to_thread` não é cancelável: ela é dona do diretório temporário e a gravação no banco só ocorre depois do `wait_for`, para o resultado tardio ser descartado. O worker também reivindica jobs em `downloading`/`analyzing` parados há mais de `jobs.STALE_SECONDS`.
- **Proxy:** `PROXY_USERNAME`/`PROXY_PASSWORD` (`services/proxy.py`, mesmo modelo do job_scrapper) são segredo, e a URL montada também: nunca em log nem em mensagem de erro (use `download.redact`; sem `logger.exception` quando há proxy). Só a extração na API (`extract_now`) o usa.
- **Persistência:** só Postgres, com SQLAlchemy assíncrono em `app/services/store.py` (`DATABASE_URL` obrigatória, `postgresql+asyncpg://`; local via `make db`, nuvem via Neon; as tabelas vivem no schema próprio `"song-tonality-helper"`, criado na subida). Guarda só as features puras da análise, chaveadas pelo id do vídeo; o relatório é montado na leitura, para o teto pedido. Mudou o critério da análise? Suba `ALGO_VERSION` em `features.py`. Andamento e erros ficam na tabela `jobs` do mesmo banco (`app/services/jobs.py`); o áudio vive em diretório temporário, sempre apagado. Sem login; a proteção opcional é só a palavra secreta `APP_PASSPHRASE` (`app/services/auth.py`, cabeçalho `X-App-Passphrase`).
- **Notas:** o código usa só a numeração padrão (MIDI; dó central = C4 = 60). Não existe numeração alternativa: UI, API e relatório mostram só a padrão.
- **Tipagem:** tudo tipado, sintaxe moderna do Python 3.14 (`list[X]`, `X | None`). Sem `Any` implícito nem `dict` solto onde um modelo cabe.
- **Erros:** regras violadas são `DomainError` (domínio e serviços); `HTTPException` só nos routers.
- **Front:** HTML/JS/CSS puros em `frontend/`, sem build. Dado externo entra na página só por `textContent`, nunca `innerHTML`.
- **Nomes em inglês; comentários e docstrings em português.** Todo arquivo tem docstring de módulo; toda função/classe tem docstring que explica o propósito, sem repetir o nome (`ruff` `D1` barra ausência). Dockerfile e Makefile têm comentários equivalentes.
- Sem código morto, sem `print`; log com `logging` quando houver o que logar.
- Swagger: toda rota tem `summary` e `description`, e o router tem `tags`.

## Testes

- Todo código novo ou alterado leva teste. Nenhum teste baixa do YouTube: o `yt-dlp` é substituído por duplo e o áudio vem de sinais sintéticos gerados em código.
- Rode só o teste relacionado: `make test T=tests/test_notes.py` (`pytest -x --tb=short -q`). Nunca a suíte inteira por padrão.
- Máximo 2 tentativas no mesmo teste que falha; se continuar, pare e explique.
- Só testes que protegem comportamento real. Sem testes que espelham a implementação.

## Fluxo de trabalho

- Uma fase do plano por vez.
- Antes de dar uma tarefa como pronta: `make ruff` e `make ty` limpos, testes relacionados passando e o fluxo exercitado.
- **Conventional Commits** em commits e no título do PR (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`, `chore:`), em português e no imperativo curto.
- Commit livre; nunca faça push sem o humano autorizar.
- Mudança notável entra no `CHANGELOG.md`; recurso novo atualiza o `README.md`.
