# Changelog

## Não lançado

- **Abandono em 61 s:** `STALE_SECONDS` caiu de 300 para 61, logo acima do prazo de 60 s do `extract_now`; se a API for cortada no meio da extração, o worker retoma o job em cerca de um minuto.
- **`extract_now` aguarda na requisição:** a API extrai antes de responder (até 60 s) em vez de usar `BackgroundTasks`, para a plataforma não cortar a instância no meio do trabalho. A resposta continua 202; a tela mostra "Extraindo..." enquanto espera.
- **Pedidos visíveis:** nova seção "Pedidos em andamento" na tela com os pedidos na fila, em curso ou com erro (com a mensagem do worker) e botão "Dispensar" nos erros. API: `GET /api/jobs` e `DELETE /api/jobs/{video_id}` (só remove a falha; 409 se o pedido está na fila ou em curso; não toca na análise guardada).
- **Worker remoto no Docker:** `make worker-remote` sobe o worker em segundo plano (perfil `remote`, lê `DATABASE_URL` e `PROXY_*` do `.env`), com `make worker-remote-logs` e `make worker-remote-down`. Os serviços `app` e `worker` do compose passam a usar sempre o Postgres do compose e não leem mais `DATABASE_URL` do `.env`.
- **Front:** se a API responder com erro (que não seja 401) ou a rede falhar, o app aparece com a mensagem em vez de uma tela vazia; assets versionados (`?v=`) para furar o cache.
- **Removido o Cloudflare Tunnel:** saem o serviço `tunnel` do compose, o `TUNNEL_TOKEN` e a leitura de `CF-Connecting-IP`; o limite de pedidos e o bloqueio por senha errada usam o IP da conexão.
- **Front:** sem "Extrair agora", o pedido para (202) e a tela só avisa que a música é processada em segundo plano e some com o status; a lista traz a música quando ela fica pronta. Com o switch ligado, a tela continua aguardando o resultado. O "Extrair agora" virou o switch on/off "Método de extração", com descrição do que cada estado faz. Antes da primeira chamada aceita pela API, o app fica oculto (`hidden` + `inert`) e só aparece o card da palavra secreta; sem `APP_PASSPHRASE` o app aparece direto. A lista de músicas analisadas virou uma caixa rolável (máx. 22rem / 50vh), destaca a música aberta, ganhou o botão "Atualizar" e se atualiza sozinha a cada 10 s com a aba visível, ao voltar à aba e quando a música acompanhada conclui; o polling automático para após 3 falhas seguidas (401/429/rede) até uma ação manual.
- **Extrair agora (`extract_now`):** `AnalysisRequest` ganha `extract_now` (padrão `false`). A API deixa de tentar baixar sozinha (antes, bastava ter `PROXY_*`): só com `extract_now` ela extrai em segundo plano, pelo proxy se configurado, com prazo de 60 s para download e análise; estourou, o job volta para a fila e o worker assume (o resultado tardio é descartado). O yt-dlp ganha `socket_timeout` de 20 s. `worker.try_with_proxy` virou `worker.extract_in_api`. Limitação: o status `analyzing` não é mais gravado (download e análise rodam numa só thread). A tela ganha o switch "Extrair agora" (guardado no `localStorage`) e avisa "Está demorando: o worker pode estar desligado." após 5 minutos.
- **Job abandonado:** o worker reivindica também jobs em `downloading`/`analyzing` sem atualização há mais de 61 s (`STALE_SECONDS`, antes 5 minutos), p.ex. quando a API caiu no meio da extração. Novo alvo `make worker-remote`.
- **Experimento do proxy:** com `PROXY_USERNAME` e `PROXY_PASSWORD` (desligado sem eles; mesmo modelo `PROXY_*` do job_scrapper, em `app/services/proxy.py`), a API tenta baixar e analisar a música por um proxy residencial rotativo; se o download falhar, o job volta para `pending` e o worker local assume, sem erro para o usuário. `jobs.claim` aceita `video_id`; `download_audio` aceita `proxy`; novo `jobs.requeue`. `yt-dlp`, `librosa`, `scipy` e `soundfile` voltaram às dependências normais (sem extra `worker`), e `imageio-ffmpeg` foi adicionado: sem `ffmpeg` no sistema, o download usa o do pacote.
- Configuração para o FastAPI Cloud: `[tool.fastapi]` no `pyproject.toml`, `fastapi[standard]`, alvo `make deploy` e seção no README.
- **Correções da revisão:** o worker devolve à fila o job que ficou preso após falha do banco; o contador de limites descarta IPs expirados; cabeçalho de senha fora de latin-1 dá 401, não 500 (use senha ASCII).
- **Só Postgres:** o SQLite e o `aiosqlite` foram removidos. `DATABASE_URL` (`postgresql+asyncpg://...`) agora é obrigatória; o `compose.yaml` ganhou o serviço `db` (postgres:17, volume `song-tonality-db`) de que API e worker dependem, e `make db` o sobe sozinho. `make run`, `make worker` e `make test` usam o Postgres local por padrão. Dados do antigo `data/analyses.db` não são migrados.
- **Palavra secreta opcional:** com `APP_PASSPHRASE` definida, toda rota `/api` (menos `/api/health`) exige o cabeçalho `X-App-Passphrase` (401 sem ele ou errado; 429 após 10 erros por hora por IP). A tela pede a palavra ao receber 401 e a guarda no `localStorage`. Sem a variável, nada muda.
- **Schema próprio no Postgres:** as tabelas `analyses` e `jobs` agora vivem no schema `song-tonality-helper` (criado na subida);. Quem já tinha tabelas no schema `public` precisa recriá-las ou movê-las (`ALTER TABLE ... SET SCHEMA`).
- **Worker local:** a API agora só enfileira o pedido (job `pending`, "Na fila" na tela); `python -m app.worker` (`make worker`, serviço `worker` no `compose.yaml`) baixa, analisa e grava, consultando o banco a cada `WORKER_POLL_SECONDS` (padrão 5). Ao subir, o worker devolve à fila jobs interrompidos; a API não marca mais jobs como "interrompidos" na subida.
- Limite de pedidos: no máximo `MAX_REQUESTS_PER_HOUR` (padrão 20) novos pedidos por IP por hora, com 429 ao exceder; análise já guardada ou job em curso não conta.
- **Mudança de configuração:** `DATABASE_PATH` foi substituída por `DATABASE_URL` (Postgres via `asyncpg`). O andamento dos jobs agora fica na tabela `jobs` do banco, e jobs interrompidos por reinício viram erro ("Análise interrompida, tente de novo.").
- Metadados de web app: favicon, ícone do iOS (`apple-touch-icon`), `manifest.webmanifest` e imagem de compartilhamento, para instalar na tela inicial do iPhone e abrir em tela cheia.
- `compose.yaml` com o Postgres, a API e o worker para rodar em casa.
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
