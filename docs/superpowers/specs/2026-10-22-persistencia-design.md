# Persistência das análises — design

Complementa `2026-10-22-song-tonality-helper-design.md` (V0). Onde houver conflito, este documento vale para persistência, API de análises e front da lista.

## Intenção
Guardar cada análise para (1) não refazer download e análise quando o mesmo vídeo voltar, (2) regerar o relatório a qualquer hora com **outro tom teto**, sem rede, e (3) manter uma lista das músicas já analisadas.

## Objetivos
- Mesmo vídeo = mesma análise, qualquer que seja a forma do link (`youtu.be/X`, `watch?v=X`, `music.youtube.com/watch?v=X&list=...`, `/shorts/X`).
- Ao colar um link já analisado, o app **avisa** ("Você já analisou esta música em <data>") e mostra o resultado salvo na hora.
- A análise é **pura**: o que se grava não depende do teto. O relatório é sempre calculado na leitura, para o teto escolhido naquele momento. Trocar a lista suspensa com um relatório aberto o atualiza na hora.
- Lista das músicas analisadas na tela (mais recentes primeiro): título, duração, nota mais aguda, data. Clicar abre o relatório com o teto atual.

## Não objetivos
- Apagar, renomear ou exportar análises (fica para depois; arquivo SQLite pode ser apagado à mão).
- Multiusuário, login, sincronização.
- Guardar o áudio.

## Anti-objetivos
- Gravar o relatório pronto (preso a um teto) em vez das features.
- Guardar análise com erro: o mesmo link deve poder ser tentado de novo.
- Mostrar relatório de um algoritmo antigo como se fosse atual.

## Decisões minhas (a confirmar)
1. **SQLite com SQLAlchemy 2.0 assíncrono (`AsyncSession` + driver `aiosqlite`; ORM tipado)**, a pedido do usuário. Escolhi SQLAlchemy em vez de SQLModel por compatibilidade comprovada com o Python 3.14; a primeira tarefa do plano confirma a instalação de `sqlalchemy`, `aiosqlite` e do plugin de testes assíncronos (se falhar, reavaliar). Modelo `Analysis` em `app/services/store.py` com `DeclarativeBase` e `Mapped[...]`; tabelas criadas por `create_all` na subida (sem Alembic: um esquema só, e a coluna `algo_version` cobre mudanças de algoritmo). Arquivo em `data/analyses.db`, caminho configurável por `DATABASE_PATH`. Uma `AsyncSession` curta por operação (`async_sessionmaker`, `expire_on_commit=False`). Rotas e leituras do banco são `async def`; o trabalho bloqueante (download e análise do áudio) continua fora do laço de eventos, via `asyncio.to_thread`, e o job de segundo plano é uma corrotina que grava o resultado com sessão própria. `create_all` roda no `lifespan` do FastAPI. Os testes usam `pytest-asyncio` (ou `anyio`) com banco em arquivo temporário. `data/` no `.gitignore`; no Docker, volume em `/srv/data`.
2. **Chave = id do vídeo** (11 caracteres `[A-Za-z0-9_-]`), extraído da URL antes de qualquer trabalho. Link sem id de vídeo (playlist, canal) é recusado com 422 já no `POST`. O download usa a URL canônica `https://www.youtube.com/watch?v=<id>`, o que elimina o problema de playlist do `yt-dlp`.
3. **Tabela `analyses`:** `video_id` (PK), `title`, `duration_seconds`, `top_midi`, `ranking`, `top_times`, `chroma_profile` (colunas `JSON`; o perfil são 12 números = média do chroma no tempo, que é tudo que a detecção de tom usa), `algo_version`, `created_at` (ISO, UTC). `AudioFeatures` troca `chroma` (12 × T) por `chroma_profile` (12); `detect_key` passa a receber o perfil.
4. **Versão do algoritmo:** constante `ALGO_VERSION` em `pitch.py`. Se o registro tem versão diferente, o `POST` reanalisa e sobrescreve; a leitura de um registro antigo continua funcionando.
5. **API** (substitui o `job_id` aleatório pelo id do vídeo; ainda não há consumidores além do front):
   - `POST /api/analyses` `{url, ceiling_midi}` → `{video_id, already_analyzed, analyzed_at}`. Já analisado: 200 com `already_analyzed=true`. Novo: 202 e processamento em segundo plano.
   - `GET /api/analyses/{video_id}?ceiling_midi=N` → `{video_id, status, error, title, report}`; `status` = `downloading | analyzing | done | error`. `done` lê do banco e monta o relatório para o teto pedido (padrão 66); 404 se não existe nem está em andamento.
   - `GET /api/analyses` → lista `{video_id, title, duration_seconds, top_note, created_at}`, mais recentes primeiro.
   - Estado de andamento/erro fica em memória por `video_id` (substitui o dicionário de jobs); um segundo `POST` do mesmo vídeo durante a análise reaproveita a execução em curso. Erro some quando o usuário tenta de novo.
6. **Título e duração** vêm dos metadados que o `yt-dlp` já consulta; `download_audio` devolve também esses dois campos.
7. **Front:** aviso de "já analisado" acima do relatório; lista abaixo do formulário, recarregada após cada análise; `change` no teto, com relatório aberto, refaz só o `GET` com o novo `ceiling_midi` (e continua salvando o teto no `localStorage`).

## Restrições
- Mesmas do design da V0 (Python 3.14, numeração dupla, 10 min máximos, front sem `innerHTML`).
- Gravação só depois de a análise terminar com sucesso, numa única transação.

## Para o construtor decidir
- Esquema de nomes das funções do repositório, formato exato da data na lista, layout da lista.
- Testes: banco SQLite em arquivo temporário por teste; cache hit comprovado com `download_audio` que levanta erro se for chamado.

## Plano por fases (visão geral)
1. Domínio: `AudioFeatures` com `chroma_profile`, `ALGO_VERSION`, extração do id do vídeo.
2. Repositório SQLite (`app/services/store.py`) com testes.
3. API: novo fluxo por `video_id`, cache, aviso, lista, `ceiling_midi` na leitura.
4. Front: aviso, lista, refazer com outro teto.
5. Docs, Docker (volume) e aceite com música real (analisar duas vezes e conferir o cache).
