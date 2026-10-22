# AGENTS.md

Apresentação do produto em `README.md`; referência técnica, endpoints e plano por fases em `docs/TECNICO.md`; decisões da V0 em `docs/superpowers/specs/`. Projeto pessoal que evolui por fases pequenas. Código simples e direto; sem abstração antes da hora.

## Documentação

`README.md` (produto) e `docs/TECNICO.md` (técnico) fazem parte da entrega. Endpoint novo, tabela alterada ou fase concluída atualizam `docs/TECNICO.md`; recurso novo para o usuário atualiza também o `README.md` e a landing, no mesmo passo. Doc desatualizada é bug. Mudança notável entra no `CHANGELOG.md`.

## Regras de código

- **Simplicidade primeiro:** sem `Protocol`, interfaces abstratas, unit of work ou camadas extras até a complexidade pedir. Mudança mínima e focada; não refatore o que não foi pedido.
- **Estrutura:** `app/routers/` (HTTP; `errors.py` mapeia `DomainError` para status), `app/domain/` (agregados puros `user.py`, `song.py`, `user_song.py`, `key.py`, `status.py`, `quick_add.py`, `sorting.py`, `errors.py`, `security.py`, `artist.py`, `text.py`, `session.py`, `friend.py`; `schemas.py` = Pydantic), `app/services/handlers.py` (casos de uso como funções: o repositório busca, o agregado decide, o handler grava e faz commit), `app/services/friends.py` (casos de uso de amigos e link público), `app/services/spotify.py` (cliente do Spotify), `app/repository/{users,songs,artists,sessions,friends}.py` (um `*Repository` por entidade, sobre `base.Repository`; consultas ORM aqui, commit no handler), `app/repository/orm/tables.py` (tabelas Core) e `mapping.py` (mapeamento imperativo), `app/infra/` (`database`, `settings`, `rate_limit`), `alembic/`, `frontend/`, `scripts/`. Router só traduz HTTP; sem SQL/ORM direto nele. Toda rota de música usa `CurrentUserDep` e filtra por `user_id` do token.
- **Login:** todo router protegido declara `dependencies=[Depends(get_current_user)]` no `APIRouter`; só `register`, `login`, `logout` e `health` são públicos (`tests/test_route_auth.py` varre as rotas). **Remoção:** música do repertório sai por soft-delete (`deleted_at`); consultas do repertório ignoram as removidas, o histórico das sessões não.
- **Tipagem:** tudo tipado, sintaxe moderna do Python 3.14 (`list[X]`, `X | None`). Sem `Any` implícito nem `dict` solto onde um modelo cabe.
- **Agregados:** classes puras em `app/domain` (dataclass, sem SQLAlchemy/FastAPI) carregam as regras (`User.register`, `Song.create`, `UserSong.create`, `Key.parse`). Erros de regra são `DomainError`; handlers e agregados só os levantam (nada de `HTTPException` fora dos routers). Persistência por **mapeamento imperativo** (`registry.map_imperatively`). Em consultas use `tables.x.c.coluna`.
- **ORM only:** SQLAlchemy 2.0 (`select()`, `Table`/`Column`); proibido SQL em string.
- **Ids:** UUID v7 (`uuid_utils.compat.uuid7`), gerado na aplicação. O tom é digitado pelo usuário, nunca importado do Spotify nem de cifra; a única exceção é copiar músicas do repertório de um amigo. Só "quero aprender" pode ficar sem tom (`KeyRequired`).
- **Schema:** Alembic. Schema mudou: nova migração (`uv run alembic revision --autogenerate -m "..."`), revisada à mão. Sem `create_all`. Todas as tabelas vivem no schema `repertorio` (`tables.SCHEMA`; `alembic/env.py` o cria): tabela nova usa o `metadata` existente e FK com `f"{SCHEMA}.tabela.id"`.
- **Front:** HTML/JS/CSS puros em `frontend/`, sem build. Dado do usuário entra na página só por `textContent`, nunca `innerHTML`; links só se começarem com `http`.
- **Nomes em inglês; comentários e docstrings em português.** Todo arquivo tem docstring de módulo; toda função/classe tem docstring que explica o propósito, sem repetir o nome (`ruff` `D1` barra ausência). Dockerfile, compose e Makefile têm comentários equivalentes.
- Sem código morto, sem `print`; log com `logging` quando houver o que logar.
- Swagger: toda rota tem `summary` e `description`, e o router tem `tags`.

## Testes

- Todo código novo ou alterado leva teste. Testes usam Postgres real num compose separado (`docker-compose.test.yml`, porta 5433, tmpfs; `make test` sobe sozinho) com `alembic upgrade head` uma vez por sessão e `TRUNCATE` entre testes (`tests/conftest.py`).
- Rode só o teste relacionado: `make test T=tests/test_songs_api.py` (`pytest -x --tb=short -q`). Nunca a suíte inteira por padrão.
- Máximo 2 tentativas no mesmo teste que falha; se continuar, pare e explique.
- Só testes que protegem comportamento real (validação, isolamento entre usuários, 404/409/422, filtros). Sem testes que espelham a implementação.

## Fluxo de trabalho

- Uma fase do plano por vez.
- Antes de dar uma tarefa como pronta: `make ruff` e `make ty` limpos, testes relacionados passando e o fluxo exercitado.
- **Conventional Commits** em commits e no título do PR (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`, `chore:`), em português e no imperativo curto. O título do PR vira a mensagem do merge, então ele também segue o padrão.
- Commit livre; nunca faça push sem o humano autorizar.
