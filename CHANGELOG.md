# Changelog

## Não lançado

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
