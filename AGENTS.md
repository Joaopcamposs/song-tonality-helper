# AGENTS.md

Apresentação do produto em `README.md`; decisões em `docs/superpowers/specs/`. Projeto pessoal que evolui por fases pequenas. Código simples e direto; sem abstração antes da hora.

## Regras de código

- **Simplicidade primeiro:** sem `Protocol`, interfaces abstratas ou camadas extras até a complexidade pedir. Mudança mínima e focada; não refatore o que não foi pedido.
- **Estrutura:** `app/routers/` (HTTP; traduz `DomainError` em status), `app/domain/` (regras puras: `notes`, `pitch`, `key`, `transposition`, `errors`, `schemas`), `app/services/` (`youtube`, `jobs`, `report`), `frontend/` (estático), `tests/`. Router só traduz HTTP; sem regra de negócio nele.
- **Sem banco, login ou histórico:** os jobs vivem em memória e o áudio em diretório temporário, sempre apagado.
- **Notas:** o código usa só a numeração padrão (MIDI; dó central = C4 = 60). A numeração do usuário é a padrão menos uma oitava (B4 padrão = B3 do usuário); só a UI e o relatório mostram as duas, rotuladas.
- **Tipagem:** tudo tipado, sintaxe moderna do Python 3.14 (`list[X]`, `X | None`). Sem `Any` implícito nem `dict` solto onde um modelo cabe.
- **Erros:** regras violadas são `DomainError` (domínio e serviços); `HTTPException` só nos routers.
- **Front:** HTML/JS/CSS puros em `frontend/`, sem build. Dado externo entra na página só por `textContent`, nunca `innerHTML`.
- **Nomes em inglês; comentários e docstrings em português.** Todo arquivo tem docstring de módulo; toda função/classe tem docstring que explica o propósito, sem repetir o nome (`ruff` `D1` barra ausência). Dockerfile e Makefile têm comentários equivalentes.
- Sem código morto, sem `print`; log com `logging` quando houver o que logar.
- Swagger: toda rota tem `summary` e `description`, e o router tem `tags`.

## Testes

- Todo código novo ou alterado leva teste. Nenhum teste baixa do YouTube: o `yt-dlp` é substituído por duplo e o áudio vem de sinais sintéticos gerados em código.
- Rode só o teste relacionado: `make test T=tests/test_notes.py` (`pytest -x --tb=short -q`). Nunca a suíte inteira por padrão.
- Máximo 2 tentativas no mesmo teste que falha; se continuar, pare e explique.
- Só testes que protegem comportamento real. Sem testes que espelham a implementação.

## Fluxo de trabalho

- Uma fase do plano por vez.
- Antes de dar uma tarefa como pronta: `make ruff` e `make ty` limpos, testes relacionados passando e o fluxo exercitado.
- **Conventional Commits** em commits e no título do PR (`feat:`, `fix:`, `docs:`, `ci:`, `refactor:`, `test:`, `chore:`), em português e no imperativo curto.
- Commit livre; nunca faça push sem o humano autorizar.
- Mudança notável entra no `CHANGELOG.md`; recurso novo atualiza o `README.md`.
