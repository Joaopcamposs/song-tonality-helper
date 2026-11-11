# Plano futuro: o repertorio absorve o Tonalidade

**Status:** adiado (2026-11-11). Motivos: o peso da imagem do repertorio e abrir mão do `extract_now` na nuvem. Retomar quando houver tempo. Enquanto isso, o Tonalidade ganha login próprio (ver a spec de autenticação), feito de forma que a absorção seja simples.

## Ideia

Trazer toda a funcionalidade do Tonalidade para o repo e o deploy do `repertorio`, numa tela separada, com um botão interno no repertorio para abrir o Tonalidade e um link de volta. Elimina um deploy, um app no FastAPI Cloud e o retrabalho de auth. O código do Tonalidade fica num módulo isolado.

## Desenho proposto

- **Código isolado:** `app/tonalidade/` (domínio, serviços, router e worker) e `frontend/tonalidade/` (página própria, mesma origem, mesmo cookie de sessão). O repertorio ganha só o `include_router`, o botão e o link de volta.
- **Auth e tenant:** o módulo usa o `CurrentUserDep` e a tabela de usuários do repertorio. A lista "minhas músicas" é por `user_id` (tabela `user_analyses`, ligando `user_id` a `video_id`). As features de áudio seguem compartilhadas por `video_id`, como o catálogo do repertorio; o `jobs` é global.
- **Banco:** schema próprio `tonalidade`, com `MetaData` separada incluída no `alembic/env.py` do repertorio (`include_name` passa a aceitar os dois schemas). Cadeia de migrações única do repertorio.
- **Peso da imagem:** hoje a imagem do Tonalidade tem ~1,5 GB (`librosa`, `scipy`, `soundfile`, `yt-dlp`, `ffmpeg`). Só `pitch.py` e `download.py` (e o worker) usam essas libs; o resto só precisa de `numpy`. Proposta: grupo opcional `audio` no `pyproject.toml`, instalado só no worker local (IP residencial); a API na nuvem fica leve. Isso exige **remover o `extract_now`** da nuvem (a API não baixa mais; todo pedido entra na fila).
- **Front:** o `sw.js` do repertorio cacheia o front e não intercepta `/api/`; a página `/tonalidade/` precisa ficar fora desse cache. A CSP do repertorio (`script-src 'self'`) já serve a página, que não usa script inline.
- **Limites e envs:** limite de pedidos por usuário (slowapi) no lugar do por IP; some `APP_PASSPHRASE`; ficam `PROXY_*` (só se o `extract_now` voltar) e `WORKER_POLL_SECONDS`.
- **Domínio e repos:** o app passa a viver em `repertorio.joaopcamposs.com.br/tonalidade/`. O repo `tonalidade` seria arquivado e o app dele no FastAPI Cloud, apagado.
- **Dados:** perder os dados atuais é aceitável; as tabelas são recriadas por migração.

## Para a absorção ser simples (vale já no login do Tonalidade)

- Alembic desde já, com schema próprio `tonalidade` e a mesma estrutura de `alembic/env.py` do repertorio.
- Tabelas de usuário e tokens com os mesmos nomes e colunas do repertorio (`users`, `auth_tokens`), para a troca ser só apontar para as do repertorio.
- Tudo que é do Tonalidade em pastas próprias, sem espalhar regra de auth pelas rotas (usar uma dependência `CurrentUserDep` equivalente).

## Riscos e decisões abertas

- Deploy e cold start mais lentos se a imagem engordar; por isso o grupo opcional `audio`.
- Reescrever o módulo no estilo do repertorio (agregados, mapeamento imperativo, um repositório por entidade) não é obrigatório; a sugestão é manter a estrutura interna e padronizar só Alembic, docstrings, ruff e testes.
- Decidir, na hora, se o `extract_now` ainda é importante.
