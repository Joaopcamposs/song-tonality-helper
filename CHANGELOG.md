# Changelog

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
