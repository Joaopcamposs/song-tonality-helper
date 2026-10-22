# Song Tonality Helper — design da tessitura, acordes e letra

## Intenção
Hoje o relatório diz o tom e onde fica a nota mais aguda, mas quem canta e toca precisa saber **o que está acontecendo naquele ponto**: a letra, o acorde e a nota, no tom original e no tom em que vai cantar. Também precisa saber **onde a melodia mais fica**, não só o pico: no caso de "Saudade Bandida" o usuário canta em A (−9) e o pico (C#4) cai bem abaixo do teto (F#4), porque o conforto vem de onde a melodia passa a maior parte do tempo.

## Objetivos
- **Tessitura:** nota mais frequente da melodia e a faixa que cobre 80% dos quadros (do 10º ao 90º percentil), no tom original e no novo.
- **Momentos agudos:** para cada ocorrência da nota mais aguda (os `top_times` que já existem), mostrar o **acorde** (original e no novo tom, com as notas do acorde) e a **letra**.
- Acorde sai junto da análise (custo desprezível). Letra é uma **etapa opcional**, pedida por botão, porque exige modelo de fala.
- Tudo guardado por `video_id` e independente do teto, como o resto: o novo tom e os acordes transpostos são montados na leitura.

## Não objetivos
- Cifra completa da música, acordes com sétima/tensões, inversões, baixo.
- Letra da música inteira ou alinhada palavra a palavra.
- GPU, modelos grandes (large), busca de letra na internet (Genius etc.).
- Garantir letra correta: é estimativa.

## Anti-objetivos
- Mostrar letra transcrita como se fosse a oficial. Ela aparece marcada como **estimada**.
- Baixar o modelo de fala sem o usuário pedir a letra.
- Frases inventadas pelo Whisper (ex.: "Legendas pela comunidade de Amara.org") aparecendo como letra.

## Decisões do usuário
- Os acordes aparecem **nos dois tons** (original e novo).
- Fazer a tessitura e a análise de letra/acordes; o teste de viabilidade foi feito antes (abaixo).

## Evidência (teste de viabilidade, sem mexer no projeto)
- `faster-whisper` instala no Python 3.14 sem PyTorch. Modelo `small` (~470 MB): ~1,3 s por trecho de 14 s, 11 s para carregar.
- Letra: "Saudade Bandida" saiu bem; "Caso Indefinido" saiu irregular. Houve uma alucinação ("Amara.org").
- Acordes (maiores e menores por correspondência com o chroma): em "Saudade Bandida" F# nos 5 picos, coerente com o tom; em "Caso Indefinido" C#m dominante com oscilações, que a escolha do acorde mais frequente por janela suaviza.

## Decisões minhas (a confirmar)
1. **Tessitura** vem do mesmo histograma de notas já calculado (`rounded[strong]`): nota mais frequente (moda) e percentis 10 e 90. Guarda-se `mode_midi`, `low_midi`, `high_midi` junto das features. A faixa só considera quadros "fortes" da faixa E3–G5 (limite do detector).
2. **Acorde por momento:** em janelas de 0,5 s de `t − 0,5 s` até `t + 3,0 s`, cada janela recebe o melhor acorde (24 tríades, correlação com o chroma médio); o momento fica com o mais frequente. Guarda-se o acorde no tom original (nome, ex. `F#`, `C#m`); a versão no novo tom e as notas do acorde são calculadas na leitura somando o deslocamento.
3. **Nomes com sustenidos** (`C#`, `F#m`), como nas notas.
4. **Letra:** `faster-whisper`, modelo `small` por padrão, trocável por `WHISPER_MODEL`. Transcreve só o trecho `[t − 6 s, t + 8 s]` de cada momento. Frases conhecidas de alucinação são descartadas (lista pequena em código). O áudio é apagado depois da análise, então a letra **rebaixa o áudio** quando pedida.
5. **Fluxo da letra:** `POST /api/analyses/{video_id}/lyrics` devolve 202 e roda em segundo plano (200 se já há letra); o andamento aparece no `GET` da análise (`lyrics_status`). A letra fica guardada no banco, junto do momento.
6. **Persistência:** novas colunas em `analyses` (tessitura, acordes por momento, letra por momento). `ALGO_VERSION` sobe para 2, porque os registros antigos não têm tessitura nem acordes e serão refeitos no próximo POST (mesma regra de hoje). O projeto não usa Alembic; no desenvolvimento um banco antigo é recriado (o arquivo em `data/` é descartável).
7. **Docker:** o modelo fica em volume (`HF_HOME` dentro de `/srv/data/models`) para baixar uma vez só.

## Restrições
- Python 3.14; só sintaxe moderna e tipagem completa; `DomainError` no domínio e serviços, `HTTPException` só nos routers; front sem `innerHTML`.
- Nenhum teste baixa do YouTube nem usa o Whisper real: `yt-dlp` e o transcritor são substituídos por duplos; acordes saem de sinais sintéticos (tríades geradas em código).
- Numeração das notas: só a padrão (dó central = C4).

## Para o construtor decidir
- Nomes de campos da API e dos modelos Pydantic, layout dos cartões novos, textos de estado ("Baixando o modelo…", "Transcrevendo…").
- Como representar acorde (string ou modelo com `name` e `notes`) e a lista de alucinações.

## Limites conhecidos (aparecem na tela)
- Letra estimada: instrumentos e vozes sobrepostas geram erros.
- Acordes só maiores e menores; pode confundir relativos e acordes com sétima.
- A tessitura e os acordes vêm do mesmo áudio misturado, então herdam o limite de não separar voz de instrumentos.
