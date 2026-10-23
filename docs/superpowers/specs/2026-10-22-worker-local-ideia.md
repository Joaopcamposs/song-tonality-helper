# App na nuvem + worker local de scrap — ideia (não implementada)

Registro de uma arquitetura para quando um projeto precisar de scrap/download que só funciona bem de casa (ex.: `yt-dlp` é bloqueado em IP de datacenter). Serve para este projeto e para outros.

## Desenho
- **Nuvem (FastAPI Cloud):** front, API e leitura. Recebe o pedido, grava um job `pending` no Postgres (ex.: Neon) e serve o resultado.
- **Worker local (em casa):** consulta o Postgres a cada poucos segundos (polling), pega o job, faz download e análise e grava o resultado. Só faz chamadas de saída: sem tunnel, sem porta aberta.
- **Postgres:** único ponto de encontro. Guarda jobs (estado) e resultados (aqui, as features puras por id do vídeo; o relatório é montado na leitura).

## Por que o worker puxa em vez de a nuvem chamar a API local
- A casa não precisa estar exposta à internet.
- Análise leva dezenas de segundos: resposta JSON direta estoura timeout e perde o andamento. Job + id + busca do resultado evita isso.
- Itens já resolvidos respondem na hora, mesmo com o computador desligado.

## Custos
- Estado do job sai da memória e vai para o banco; SQLite vira Postgres (`asyncpg`).
- Dois processos para publicar; versão do algoritmo (`ALGO_VERSION`) igual nos dois.
- Alguns segundos de espera pelo polling em item novo.
- Sem login, qualquer pessoa enfileira job na máquina de casa: precisa de limite de requisições ou acesso restrito.

## Quando vale
Se só publicar o app já basta, o Cloudflare Tunnel atual resolve. Vale se o app deve ficar disponível com a máquina desligada ou se não se quer expor a casa. Seria uma fase própria: 1) Postgres + jobs no banco; 2) worker.
