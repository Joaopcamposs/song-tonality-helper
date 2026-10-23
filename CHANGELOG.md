# Changelog

## Não lançado

- **Palavra secreta opcional:** com `APP_PASSPHRASE` definida, toda rota `/api` (menos `/api/health`) exige o cabeçalho `X-App-Passphrase` (401 sem ele ou errado; 429 após 10 erros por hora por IP). A tela pede a palavra ao receber 401 e a guarda no `localStorage`. Sem a variável, nada muda.
- **Schema próprio no Postgres:** as tabelas `analyses` e `jobs` agora vivem no schema `song-tonality-helper` (criado na subida); no SQLite nada muda. Quem já tinha tabelas no schema `public` precisa recriá-las ou movê-las (`ALTER TABLE ... SET SCHEMA`).
- **Worker local:** a API agora só enfileira o pedido (job `pending`, "Na fila" na tela); `python -m app.worker` (`make worker`, serviço `worker` no `compose.yaml`) baixa, analisa e grava, consultando o banco a cada `WORKER_POLL_SECONDS` (padrão 5). Ao subir, o worker devolve à fila jobs interrompidos; a API não marca mais jobs como "interrompidos" na subida.
- Limite de pedidos: no máximo `MAX_REQUESTS_PER_HOUR` (padrão 20) novos pedidos por IP por hora, com 429 ao exceder; análise já guardada ou job em curso não conta.
- **Mudança de configuração:** `DATABASE_PATH` foi substituída por `DATABASE_URL` (SQLite ou Postgres via `asyncpg`; padrão `sqlite+aiosqlite:///data/analyses.db`). O andamento dos jobs agora fica na tabela `jobs` do banco, e jobs interrompidos por reinício viram erro ("Análise interrompida, tente de novo.").
- Metadados de web app: favicon, ícone do iOS (`apple-touch-icon`), `manifest.webmanifest` e imagem de compartilhamento, para instalar na tela inicial do iPhone e abrir em tela cheia.
- `compose.yaml` com a API e o Cloudflare Tunnel para publicar o app em casa (token em `.env`, modelo em `.env.example`).
- Apagar uma música da lista (botão com confirmação na tela; `DELETE /api/analyses/{video_id}`, 204, 404 se não existe e 409 se está em análise).
- Ajustes: o andamento em curso não é descartado ao passar de 50 análises; dois pedidos simultâneos não baixam o mesmo vídeo duas vezes; links `/live/` e `/embed/` são aceitos e links de canal/playlist têm mensagem própria; o acompanhamento na tela para ao trocar de música e tolera falha de rede passageira.
- **Mudança na API e na tela:** a numeração do usuário (dó central = C3) saiu; notas e tetos usam só a padrão (dó central = C4). As notas da API e as opções de teto agora têm `midi` e `name`; a lista de teto vai de C3 a C5 (os mesmos números MIDI de antes, com teto padrão F#4).
- Corrige "Não encontrei uma melodia detectável" em músicas com muitas notas agudas esparsas: a nota mais aguda sustentada agora é escolhida entre todas as notas, e o ranking mostra só as sustentadas.
- Logo (palheta verde-água com nota e seta para cima) e front redesenhado na mesma linguagem visual do Repertório: tema escuro/claro, resultado em destaque, ranking em barras e lista de músicas em cartões.

## 0.2.0 — 2026-10-22

- Análises guardadas em SQLite (SQLAlchemy assíncrono): o mesmo vídeo não é baixado nem analisado de novo, e o app avisa quando o link já foi analisado.
- Guarda só as features puras (sem teto): o relatório é calculado na leitura, então trocar o teto atualiza o relatório na hora.
- Lista de músicas já analisadas na tela, para reabrir relatórios sem colar o link.
- Docker com volume para o banco (`DATABASE_PATH`).
- **Mudança na API:** o id da análise agora é o id do vídeo; `POST /api/analyses` recebe só `url`; `GET /api/analyses/{video_id}?ceiling_midi=N` monta o relatório; novo `GET /api/analyses` lista as análises.

## 0.1.0 — 2026-10-22

- Primeira versão: link do YouTube + tom teto → relatório com nota mais aguda, tom detectado, deslocamento, novo tom, grau e trechos.
- Teto em lista suspensa com cache no navegador; numeração do usuário e padrão mostradas juntas.
- API em jobs (`POST`/`GET /api/analyses`, `GET /api/ceilings`) e front estático.
