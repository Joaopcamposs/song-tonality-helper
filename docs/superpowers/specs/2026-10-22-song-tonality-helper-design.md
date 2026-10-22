# Song Tonality Helper — design da V0

## Intenção
Ferramenta pessoal de estudo musical. O usuário cola o link de uma música do YouTube e escolhe o seu **tom teto** (a nota mais aguda que consegue cantar com estabilidade). O app descobre sozinho a nota mais aguda da melodia e o tom original, e devolve um relatório com o tom ao qual a música deve ser transposta para que o topo caia no teto. Hoje isso é feito à mão, com piano ou app de piano.

## Objetivos
- Entrada mínima: link do YouTube + teto (lista suspensa). Nada de digitar o tom da música.
- Relatório no front: nota mais aguda, tom original detectado, deslocamento em semitons, novo tom, grau da nota no tom original e trechos (tempos) em que a nota mais aguda aparece.
- Teto lembrado entre usos (localStorage).
- Rodar localmente, pelo `uvicorn` ou Docker.

## Não objetivos
- Multiusuário, login, banco de dados, histórico de análises.
- Identificar o acorde exato do ponto mais agudo (o README só pede o grau na escala).
- Separar voz de instrumentos (limite conhecido do método atual).
- Publicar para outras pessoas. Deploy no FastAPI Cloud é fase final opcional.

## Anti-objetivos
- Resultado único e confiante quando o algoritmo está em dúvida. O relatório mostra o ranking de notas e os tons candidatos, para o usuário julgar.
- Complexidade antes da hora (sem fila, sem abstrações, sem build no front).

## Decisões do usuário
- Uso pessoal, por enquanto.
- O teto vem de uma lista suspensa e é guardado em cache.
- O tom original **não** é informado: o algoritmo o detecta.
- Stack: FastAPI + front vanilla.

## Decisões minhas (a confirmar)
1. **Detecção do tom:** chroma do áudio harmônico correlacionado com os perfis de Krumhansl (maior/menor), no mesmo carregamento do áudio. O relatório mostra o melhor tom e os 2 candidatos seguintes (relativo maior/menor é a confusão típica).
2. **O deslocamento não depende do tom detectado:** vem só de (nota mais aguda → teto). O tom detectado serve para dar nome ao novo tom e ao grau. Um tom errado nomeia mal, mas não muda o número de semitons.
3. **Numeração das notas:** existem duas convenções. A do usuário (estilo Yamaha: dó central = C3) vale a padrão científica (dó central = C4, a do librosa) menos 1 oitava. Confirmado no caso "Dois Passarinhos": usuário B3 = algoritmo B4. O código usa só o padrão (MIDI). A lista suspensa e o relatório mostram as duas, rotuladas (ex.: `F#3 (padrão: F#4)`), e o front indica a convenção em uso. O cache guarda o número MIDI. Faixa da lista: C2 a C4 na numeração do usuário, padrão F#3. Alternar convenção fica fora da V0.
4. **Deslocamento mínimo** entre -6 e +5 semitons (como no `script.py`), mostrando também a alternativa de 12 semitons quando existir.
5. **Fluxo em job:** `POST /analyses` devolve o id; `GET /analyses/{id}` informa o status (baixando, analisando, pronto, erro). Estado num dicionário em memória; áudio em arquivo temporário apagado ao fim.
6. **Download:** `yt-dlp` com `ffmpeg`, só áudio. Duração máxima aceita: 10 min (evita análise longa por engano).
7. **Algoritmo de pitch:** o de `script.py`, movido para `app/domain/pitch.py` sem alterar o critério (nota mais alta com >= 100 quadros). Acrescenta os tempos de ocorrência.
8. **Estrutura:** `app/main.py`, `app/routers/analyses.py`, `app/domain/{pitch,key,notes}.py`, `app/services/{youtube,jobs}.py`, `frontend/`.

## Restrições
- Python 3.14; confirmar que librosa/numba/scipy instalam nele (primeira tarefa do plano; se falhar, fixar 3.13).
- `ffmpeg` precisa estar no PATH (brew local, apt no Docker).
- YouTube bloqueia IPs de datacenter: no deploy será preciso cookies, o que é frágil. Por isso o deploy é opcional.

## Para o construtor decidir
- Nomes de campos da API, layout visual do relatório, mensagens de erro (link inválido, vídeo longo, falha de download).
- Testes: núcleo com sinais sintéticos (senoide/acordes gerados em código), API com o download mockado. Nenhum teste baixa do YouTube.

## Limites conhecidos (aparecem no relatório)
- Acordeão, segundas vozes e instrumentos agudos podem ser tomados por melodia.
- Detecção de tom é estatística; músicas com modulação ou tom ambíguo podem errar.

## Plano por fases (visão geral)
0. Reescrever `AGENTS.md` (remover Postgres/auth/Spotify/Alembic), corrigir `Dockerfile` (`vicorn`) e `Makefile`, criar `pyproject` com dependências, validar o ambiente (Python 3.14 + librosa + ffmpeg).
1. Domínio: notas, pitch (migrado do script), tom, cálculo do novo tom — com testes sintéticos.
2. Download + job + endpoints.
3. Front: formulário, lista suspensa com cache, relatório.
4. Docs (`README`, `CHANGELOG`) e Docker.
5. (Opcional) Deploy no FastAPI Cloud.
