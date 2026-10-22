# song-tonality-helper

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