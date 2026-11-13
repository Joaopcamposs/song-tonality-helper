# Tonalidade — acorde no ponto mais agudo (design curto)

Recorte do spec `2026-10-22-letra-acordes-design.md`: só os acordes dos momentos agudos. Tessitura e letra ficam para fases seguintes.

## Intenção
O relatório diz o tom e onde a nota mais aguda toca (`top_times`), mas não o que a harmonia faz ali. Quem canta e toca precisa do acorde daquele ponto, no tom original e no novo. Ex.: tom Em, pico B4, acorde provável Em.

## Objetivos
- Para cada `top_time`, um acorde provável (36 candidatos: tríades maiores e menores e dominantes com sétima, `X7`), no tom original e no novo.
- Acorde calculado na análise e guardado só como nome; a versão no novo tom sai na leitura (acorde original + `shift`).

## Não objetivos
- Outras sétimas (maior, menor), tensões, inversões, baixo, cifra completa.
- Tessitura e letra (fases seguintes).
- Guardar chroma fino da música inteira.

## Anti-objetivos
- Mostrar o acorde como certeza. Na tela ele aparece como **provável**.
- O campo harmônico virar filtro rígido: ele só desempata.

## Abordagens consideradas
- **A. Calcular na análise e guardar o nome (escolhida):** segue o spec antigo; barato; o chroma fino não vai ao banco. Custo: mudar o critério exige refazer a análise (`ALGO_VERSION`).
- B. Guardar chroma fino e calcular na leitura: ajusta o critério sem rebaixar áudio, mas põe mais dado no banco que o projeto não guarda hoje. Descartada (sem necessidade ainda).
- C. Só teoria (campo harmônico + nota): dá candidatos, não o acorde. Descartada como solução única.

## Design
- **Lógica pura** em `app/domain/chords.py` (só numpy, sem libs de áudio): modelos das 24 tríades, correlação com o chroma, escolha do acorde por janela e voto do mais frequente.
- **Por momento:** janelas de 0,5 s de `t − 0,5 s` até `t + 3,0 s`; cada janela recebe o melhor acorde por correlação com o chroma médio; o momento fica com o mais frequente.
- **Desempate:** quando os dois melhores de uma janela ficam quase empatados (margem pequena), vence o diatônico ao tom da seção em que o momento cai (`key_sections`). Sem empate, o campo harmônico não interfere.
- **`analyze_audio`** (`pitch.py`) calcula os acordes com o chroma que já existe e preenche `AudioFeatures.top_chords: list[str]`, paralelo a `top_times`. Nomes com sustenido (`C#`, `F#m`).
- **Persistência:** coluna nova `top_chords` (JSON) em `analyses`, via migração Alembic nova (schema `tonalidade`), com valor padrão vazio. `ALGO_VERSION` sobe para 3: registros antigos são refeitos no próximo POST.
- **Relatório:** `build_report` devolve, por momento, o acorde original e o do novo tom (`shift` somado à tônica). Campos e schema Pydantic novos em `schemas.py`.
- **Front:** uma linha por pico mostrando o acorde nos dois tons, marcado como provável, via `textContent`.

## Restrições
- Regras do `AGENTS.md`: tipagem completa, docstrings em português, `DomainError` no domínio, sem `innerHTML`, `make ruff` e `make ty` limpos.
- Testes sem YouTube: chroma sintético com tríades geradas em código; teste do desempate, do voto por momento, da transposição na leitura e da migração.
- `CHANGELOG.md` e `README.md` atualizados.

## Para o construtor decidir
- Valor da margem de empate e formato exato dos campos da API.
- Se `chords.py` guarda os modelos como constantes numpy ou os gera de intervalos.
- Layout da linha do acorde no front.

## Limites conhecidos (aparecem na tela)
- Estimativa: áudio misturado, voz e instrumentos juntos.
- Só maiores, menores e dominantes com sétima; a sétima dominante só vence quando soa com clareza (penalidade fora do V do tom).
