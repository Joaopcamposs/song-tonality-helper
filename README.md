# song-tonality-helper

Ferramenta pessoal de estudo musical: cole o link de uma música do YouTube, escolha o seu tom teto e o app descobre a nota mais aguda da melodia, o tom original e o tom em que cantá-la para que o topo caia no teto.

## Como usar

Requisitos: [uv](https://docs.astral.sh/uv/), `ffmpeg` (`brew install ffmpeg`) e Docker (para o Postgres local).

```bash
uv sync
make db           # Postgres do compose (porta 5432); `run`, `worker` e `test` já o sobem
make run          # API em http://localhost:8007
make worker       # em outro terminal: processa a fila de análises
```

1. Cole o link do YouTube (um vídeo de até 10 minutos).
2. Escolha o seu tom teto na lista (o valor fica salvo no navegador).
3. Clique em Analisar e leia o relatório: nota mais aguda, tom detectado, deslocamento em semitons, novo tom, grau da nota, trechos em que ela aparece e o ranking das notas.
4. A análise fica guardada: colar de novo o mesmo vídeo (em qualquer forma de link) avisa que já foi analisado e mostra o resultado na hora. A lista "Músicas já analisadas" reabre qualquer uma, e trocar o teto recalcula o relatório sem baixar nada. O botão "Apagar" (com confirmação) tira a música da lista.

As análises e o andamento dos jobs ficam num Postgres escolhido por `DATABASE_URL` (obrigatória, `postgresql+asyncpg://usuario:senha@host:5432/banco`). Localmente, `make db` sobe o Postgres do compose (banco `song_tonality`, senha `dev`, só em `127.0.0.1:5432`) e `make run`/`make worker` já usam essa URL; exporte `DATABASE_URL` para apontar para outro banco. Em produção na nuvem, `DATABASE_URL` vem do Neon (use `ssl=require` no lugar de `sslmode=require`); no compose, defina-a no `.env` para sobrescrever o serviço `db`. As tabelas ficam no schema próprio `song-tonality-helper`, criado automaticamente, o que permite dividir o banco com outros apps. Os testes usam o banco `song_tonality_test` (criado por `make db`; `TEST_DATABASE_URL` sobrescreve) porque a fixture apaga e recria o schema a cada teste.

A API só enfileira o pedido (status "na fila"); quem baixa e analisa é o worker (`python -m app.worker`, ou `make worker`). Sem o worker rodando, as análises ficam pendentes.

| Variável | Quem usa | Padrão |
| --- | --- | --- |
| `DATABASE_URL` | API e worker (o mesmo banco); obrigatória | nenhum (no `make`/compose, o Postgres local) |
| `PROXY_USERNAME`, `PROXY_PASSWORD` | API: experimento de proxy, veja abaixo; segredos | vazias (desligado) |
| `PROXY_HOST`, `PROXY_COUNTRY`, `PROXY_SESSION_MINUTES` | API: opções do proxy, veja abaixo | veja abaixo |
| `WORKER_POLL_SECONDS` | worker: intervalo entre consultas à fila | `5` |
| `APP_PASSPHRASE` | API: palavra secreta; se definida, toda rota `/api` (menos `/api/health`) exige o cabeçalho `X-App-Passphrase` e a tela pede a palavra (guardada no `localStorage`); 10 erros por hora por IP levam a 429. Vazia ou ausente: sem proteção. Use só ASCII (sem acentos): o cabeçalho HTTP é latin-1. O front estático continua público | vazia |
| `MAX_REQUESTS_PER_HOUR` | API: novos pedidos por IP por hora (429 ao exceder; reaproveitar análise guardada ou job em curso não conta) | `20` |

API na nuvem + worker em casa: aponte `DATABASE_URL` dos dois para o mesmo Postgres (ex.: Neon). Na nuvem rode só a API; em casa, só o worker (`docker compose up -d --build worker` ou `make worker`), já que o YouTube costuma bloquear IPs de nuvem. O worker só faz conexões de saída, sem túnel. Rode um único worker por banco: ao subir, ele devolve à fila os jobs que ficaram em andamento. Ctrl+C ou SIGTERM encerram depois do job atual.

Com Docker: `make up` sobe tudo pelo compose (Postgres, API, worker e túnel), `make build-up` reconstruindo a imagem e `make down` derruba tudo (o volume do banco fica).

### API

Documentação interativa em `/docs`.

| Rota | O que faz |
| --- | --- |
| `GET /api/ceilings` | Opções de teto e o padrão |
| `POST /api/analyses` | Pede a análise de um link (200 se já analisado, 202 se vai analisar) |
| `GET /api/analyses` | Lista as músicas analisadas |
| `GET /api/analyses/{video_id}` | Status e relatório para o `ceiling_midi` pedido |
| `DELETE /api/analyses/{video_id}` | Apaga uma música da lista |

### Numeração das notas

O app usa só a numeração padrão (a do librosa): o dó central é C4. A lista de teto vai de C3 a C5 e o relatório mostra as notas nessa mesma numeração. Se o seu instrumento usa o dó central como C3, some uma oitava ao ler (B4 aqui é B3 no seu).

### Limites

- O método não separa a voz dos instrumentos: acordeão, segundas vozes e instrumentos agudos podem aparecer como notas altas. Por isso o relatório mostra o ranking das notas, e a nota mais aguda é a mais alta que aparece em pelo menos 100 quadros (cerca de 2,3 s no total).
- O tom é detectado por estatística (correlação do chroma com os perfis de Krumhansl) e pode errar, principalmente entre relativos maior/menor ou em músicas com modulação. O deslocamento em semitons não depende dele; só o nome do novo tom.
- Do seu computador o YouTube costuma liberar o download. Em servidores na nuvem ele bloqueia com frequência, exigindo cookies do navegador, o que é frágil. Por isso o deploy é opcional.

Resultado de referência (aceite): "Dois Passarinhos" (Alan e Aladim), teto F#4 → nota mais aguda B4, tom G maior, -5 semitons, novo tom D maior; o topo cai em F#4.

---

## Publicar em casa

O app roda em casa (o YouTube costuma bloquear downloads de IPs de nuvem) e vai para a internet por um Cloudflare Tunnel, sem abrir portas no roteador.

1. No painel da Cloudflare (Zero Trust > Networks > Tunnels), crie um túnel e copie o token.
2. No túnel, adicione um *public hostname* (ex.: `song.seudominio.com.br`) com serviço `http://app:8000`.
3. Copie `.env.example` para `.env` e cole o token em `TUNNEL_TOKEN`.
4. Suba tudo (API, worker e túnel): `docker compose up -d --build`.
5. Como o app não tem login, proteja o subdomínio em Zero Trust > Access > Applications, liberando só o seu e-mail.

## Publicar no FastAPI Cloud

A API e o front podem ficar no FastAPI Cloud (`[tool.fastapi]` no `pyproject.toml` aponta o entrypoint), com o worker rodando em casa (`make worker` ou o serviço `worker` do compose) contra o mesmo Postgres (Neon).

1. `uv run fastapi login` e `uv run fastapi deploy` na primeira vez (cria o app e o `.fastapicloud/`, que não vai para o git). Depois, `make deploy`.
2. No painel do app, defina as variáveis `DATABASE_URL` (`postgresql+asyncpg://...` do Neon) e `APP_PASSPHRASE` (ASCII).
3. O worker em casa usa o mesmo `DATABASE_URL`. Fora do túnel da Cloudflare não existe `CF-Connecting-IP`, então o limite por IP cai para o IP visto pelo servidor.

### Experimento: baixar pela API com proxy (`PROXY_*`)

Desligado por padrão. Se `PROXY_USERNAME` e `PROXY_PASSWORD` estiverem definidas na API, cada pedido novo faz a própria API tentar baixar e analisar a música pelo proxy. Se o download falhar (bloqueio, proxy fora, rede), o job volta para "na fila" sem erro e o worker em casa assume; erros de análise (ex.: sem melodia) viram erro normalmente. O log diz se cada job foi resolvido "via proxy" ou "via worker".

| Variável | Padrão | O que faz |
|---|---|---|
| `PROXY_USERNAME`, `PROXY_PASSWORD` | vazio | proxy residencial (formato Oxylabs: o usuário vira `customer-<user>-cc-<país>`). Sem eles o download sai direto. Aqui só o download do yt-dlp usa |
| `PROXY_HOST` | `pr.oxylabs.io:7777` | endereço do proxy |
| `PROXY_COUNTRY` | vazio | país de saída (ex.: `br`) |
| `PROXY_SESSION_MINUTES` | vazio | vazio: IP novo a cada request (rotativo); número: IP fixo por esse tempo (sticky) |

- O proxy precisa ser **residencial e rotativo**: o YouTube bloqueia IPs de nuvem e de datacenter.
- Proxies residenciais costumam cobrar por tráfego (GB), e cada tentativa baixa o áudio do vídeo, então acompanhe o custo.
- Usuário e senha são segredo: defina-os só nas variáveis do app e nunca a coloque em log nem no git. O `ffmpeg` não precisa existir no sistema da nuvem: sem ele, usa-se o do pacote `imageio-ffmpeg`.
- Não verificado com proxy real; só com testes que substituem o yt-dlp. Rodar o worker em casa continua necessário como fallback.

## Origem da ideia

Principios:
 - util para estudos musicais.
 - ex: preciso estabilizar minha nota mais aguda em uma musica no tom de F#3.
 - Exemplo para a seguinte musica: 
    - 'Saudade Bandida', tom original em F#. 
    - Ela foi alterada para A. 
    - Desci a escala ao invés de subir. 
 - A estratégia para estabilizar uma musica de forma que a nota mais aguda seja o F#3 é o seguinte:
    - Escolher a versao da musica e verificar o Tom. 
    - Apos isso, identificar a nota mais AGUDA a partir da harmonia. 
    - Com a nota mais alta, verificar o acorde daquele ponto e onde a nota se encaixa (tonica, terca, quinta, etc). 
    - A partir disso, descer ate que a nota mais aguda da nova tonalidade seja F3 ou F#3.
 - Exemplo prático funcional:
    - Vamos usar a musica 'dois passarinhos' de alan e aladin. 
    - Identifique a nota mais alta com B3, que fica no trecho abaixo:
        D            C       D7       G
        E para nós o respeito é o segredo da nossa amizade
                     D
        Nós somos dois passarinhos ...

    - A musica esta na tonalidade de G.

Com B3 como nota mais aguda em G, o tom ideal para você é D (Ré), com o topo caindo em F#3.

Conta:
B3 → F#3 são 5 semitons abaixo.
G descendo 5 semitons dá D.
B é o 3º grau de G (G, A, B). Em D, o 3º grau é F#, e a tônica fica em D3, com o topo 4 semitons acima dela.

Função da nota no acorde

Sem a sílaba exata não consigo dizer em qual acorde o B3 cai, mas isso não muda a transposição:

Sobre G, B é a terça do acorde.
Sobre C, é a sétima maior.
Sobre D ou D7, é a sexta (13ª).

Em todos os casos B é o 3º grau da escala de G, e a transposição de tom depende só disso.

A questão é: Quero evitar de ter de usar um piano ou app piano para achar a nota mais aguda.
O claude chat sugeriu isso:
- Se você me enviar o áudio (idealmente só a voz, ou a música inteira), eu rodo o script de detecção de altura aqui e te devolvo a nota mais aguda e o trecho em que ela aparece. Meu ambiente não consegue baixar áudio de sites, então ele precisa vir de você, anexado na conversa.

entào enviie o audio em mp3 e ele fez o script.py para anlisar a bateu com a transposição teste.

```txt
Dá para fazer, e o script abaixo já funciona. Rodei no seu áudio e ele deu B4, descer 6 semitons e tom C# (Db), o mesmo resultado que eu tinha calculado à mão.

O que usei

ffmpeg para converter o mp3 em áudio mono.
librosa para o processamento de áudio: separar a parte harmônica (voz, acordeão, violão) da percussiva e calcular o espectro por notas (CQT, 3 divisões por semitom).
Soma harmônica, que é a parte central. Para cada instante, eu testo cada nota candidata da melodia somando a energia dela e dos harmônicos (2×, 3×, 4×, 5× a frequência). A nota com a maior soma é a “melodia” naquele instante. Funciona melhor que um detector simples quando há vários instrumentos.
Filtro de mediana para tirar saltos falsos, e depois uma contagem de quantos quadros cada nota aparece.

O que não funcionou
Primeiro tentei o pyin, um detector de uma nota só. Na gravação com instrumentos ele achou só 21 quadros úteis. Também tentei instalar o basic-pitch e o torchcrepe, que são mais precisos, mas a instalação falhou ou demorou demais aqui. Por isso fiz a versão acima.

Limite do método
Ele não separa a voz do resto, então acordeão e segunda voz podem aparecer como notas altas. Foi o caso do G5 e do D5. Por isso o script mostra o ranking de notas, e você decide qual é a melodia.
```

Iremos continuar e tornar isso um web-app com fastapi + fastapicloud + frontend vanilla.
 - a ideia é ter um app que recebe o link do youtube
 - extrair o audio desse link usando alguma lib ou funcao nativa
 - colocar esse audio em um temp file em memoria e analisar o som com o script para verificar a nota mais aguda.