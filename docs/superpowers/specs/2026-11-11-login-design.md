# Login, conta e dados por usuário — design

Complementa `2026-10-22-tonalidade-design.md` (V0) e `2026-10-22-persistencia-design.md`. A absorção futura pelo repertorio está em `2026-11-11-absorcao-pelo-repertorio-plano.md`; este design foi feito para ela ser simples.

## Intenção

Hoje o app é aberto (ou protegido por uma palavra secreta única) e o tom teto vive no `localStorage` do navegador. Queremos contas: cada pessoa se cadastra, entra e vê só as **suas** músicas analisadas, com o **seu** tom teto guardado no servidor. O processo de conta é o do app `repertorio` (`~/Dev/repertorio`), copiado e adaptado.

## Objetivos

- Cadastro, login, logout, `/me`, confirmação de e-mail e redefinição de senha, como no repertorio.
- Cada usuário tem uma lista própria de músicas analisadas e um tom teto salvo no servidor.
- Mudar o teto continua atualizando o relatório na hora, sem baixar nada de novo (o relatório é montado na leitura, a partir das features guardadas).
- Banco versionado por Alembic, com schema próprio `tonalidade`.
- Compatível com a absorção pelo repertorio: `users` e `auth_tokens` com os mesmos nomes e colunas de lá.

## Não-objetivos

- Organizações, times ou convites: o "tenant" é o próprio usuário (`user_id`).
- Administrador, perfil público, amigos, login social.
- Termos de uso e política de privacidade (o app não tem essas páginas; ver "Decisões minhas").
- Migrar dados antigos: apagar e recomeçar foi autorizado.

## Anti-objetivos

- Um usuário ver, apagar ou alterar a lista ou o teto de outro.
- Uma rota `/api` (menos `register`, `login`, `logout`, `forgot-password`, `reset-password`, `verify-email`, `health`) responder sem sessão válida.
- Senha em texto, ou token de e-mail guardado em claro (só hash).

## Modelo de dados (schema `tonalidade`, via Alembic)

| Tabela | Colunas | Observação |
|---|---|---|
| `users` | `id` (UUID v7), `name`, `email` (único, minúsculas), `password_hash`, `created_at`, `email_verified_at` | mesmos nomes do repertorio |
| `auth_tokens` | `id`, `user_id` → `users`, `kind` (`reset`/`verify`), `token_hash`, `expires_at`, `used_at`, `created_at` | só o hash é guardado; uso único; reset vale 1 h, confirmação 3 dias |
| `user_settings` | `user_id` (PK → `users`), `ceiling_midi` | teto salvo; ausente = padrão (`DEFAULT_CEILING_MIDI`) |
| `user_analyses` | `user_id` → `users`, `video_id`, `created_at`; PK (`user_id`, `video_id`) | a lista de cada pessoa; criada no pedido da análise |
| `analyses` | como hoje | features puras por `video_id`, **compartilhadas** entre usuários (caras de calcular e independentes de quem pede) |
| `jobs` | como hoje | andamento por `video_id`, global; o worker segue igual |

`user_settings` fica separada de `users` para `users` continuar idêntica à do repertorio.

## Comportamento

- **Sessão:** JWT de 30 dias em cookie `session` (`httponly`, `samesite=lax`, `secure` com `COOKIE_SECURE`), assinado com `SECRET_KEY` (obrigatória; sem ela o app não sobe). Senha com bcrypt (máx. 72 bytes, validado no schema). `get_current_user` (cookie → usuário, senão 401) e `CurrentUserDep`, nomes iguais aos do repertorio. O router de análises declara `dependencies=[Depends(get_current_user)]`; `tests/test_route_auth.py` varre as rotas e falha se alguma não pública estiver aberta.
- **Cadastro:** nome, e-mail, senha (e confirmação no front); e-mail duplicado → 409; manda o e-mail de confirmação. Login: e-mail e senha; erro genérico. Esqueci a senha responde sempre 204 (não revela contas). Quem não confirmou o e-mail pode usar o app (como no repertorio); a confirmação serve para recuperar a conta.
- **E-mail:** Resend via `httpx`; sem `RESEND_API_KEY` o e-mail não é enviado e vai só para o log, o que serve ao desenvolvimento local (como no repertorio); em produção a chave é obrigatória na prática. Links `?verificar=<token>` e `?redefinir=<token>` abrem a tela certa no front.
- **Teto:** `GET /api/me/settings` e `PUT /api/me/settings` (`ceiling_midi`, 48 a 72, mesma faixa de hoje). `GET /api/analyses/{video_id}` sem `ceiling_midi` usa o teto salvo; com o parâmetro, usa o pedido sem gravar (a tela pode pré-visualizar). Ao trocar o seletor, a tela salva o teto e refaz o relatório da música aberta na hora, com as features que o servidor já tem.
- **Lista:** `POST /api/analyses` cria o vínculo em `user_analyses` (se ainda não existir), mesmo quando a análise já existe e responde 200 `already_analyzed`; se outra pessoa já pediu a mesma música, o `job` ou a análise são reaproveitados, sem baixar duas vezes. `GET /api/analyses` lista só as músicas do usuário (com as que ainda estão na fila ou com erro, para a seção "Pedidos em andamento"). `DELETE /api/analyses/{video_id}` remove só o vínculo do usuário; as features compartilhadas ficam. Quem não tem vínculo recebe 404 em `GET`/`DELETE`.
- **Limites:** o limite de novos pedidos por hora passa de por IP para por usuário; login, cadastro e e-mails têm limite por IP (módulo `ratelimit` atual, em memória). A palavra secreta (`APP_PASSPHRASE`, `X-App-Passphrase` e a tela de "gate") sai.
- **Front:** tela de entrada com abas Entrar / Criar conta, "Esqueci a senha", telas de confirmação e de nova senha (`?verificar=` / `?redefinir=`), botão Sair e o nome do usuário. 401 em qualquer chamada volta para a tela de entrada. O teto sai do `localStorage` e vem de `/api/me/settings`. Dado externo entra só por `textContent`.
- **Migrações:** o `store.create_tables()` (`create_all`) sai; entra Alembic (`alembic.ini`, `alembic/env.py` assíncrono com o schema `tonalidade` criado antes da primeira migração, como no repertorio), uma migração inicial com todas as tabelas. O app aplica `alembic upgrade head` na subida (ver "Decisões minhas"). Testes: `alembic upgrade head` uma vez por sessão e `TRUNCATE` entre testes, no banco `tonalidade_test`.
- **Dados em produção:** antes da primeira subida com Alembic, apagar o schema `tonalidade` do Supabase atual (`DROP SCHEMA tonalidade CASCADE`), com OK explícito do usuário na hora.

## Configuração nova

`SECRET_KEY` (obrigatória), `COOKIE_SECURE`, `RESEND_API_KEY`, `MAIL_FROM`, `APP_URL`. Dependências novas: `alembic`, `bcrypt`, `pyjwt`, `email-validator`, `uuid-utils`, `httpx` (que sai do grupo `dev`). O README, o `.env.example` e o compose passam a documentá-las.

## Decisões minhas (para revisar)

1. **Migrar na subida do app**, não num workflow de CI: o Tonalidade não tem pipeline de deploy próprio (o FastAPI Cloud publica no push) e o `CMD` do Dockerfile não vale lá. O repertorio migra num passo do GitHub Actions; na absorção isso passa a valer.
2. **Sem termos de uso** nem aceite no cadastro: o app não tem páginas de termos e privacidade. A coluna `terms_accepted_at` do repertorio fica de fora por ora.
3. **`ratelimit` atual** (em memória, por chave) em vez de `slowapi`, para não trazer dependência nova; ele já cobre IP e agora usuário.
4. **Sem administrador** e sem `public_token`; `users` tem só o que o login precisa.
5. **Apagar a música tira só o vínculo do usuário;** as features compartilhadas ficam (não há coleta de lixo por enquanto).
6. **Estrutura:** `app/domain/{user,auth_token,security}.py`, `app/services/{account,mailer,mail_templates}.py`, `app/routers/{auth,settings}.py` e `deps.py`, nomes iguais aos do repertorio. A regra de auth fica na dependência, não espalhada pelas rotas.

## Testes (comportamento real)

Cadastro/login/logout/`/me`; e-mail duplicado (409); senha errada; token de e-mail inválido, vencido e reutilizado; redefinição de senha; isolamento entre usuários (lista, relatório, delete, teto); teto salvo e usado como padrão; relatório muda com o teto sem novo download; varredura de rotas sem login; migração inicial sobe do zero.

## Fases

1. Alembic e tabelas (`users`, `auth_tokens`, `user_settings`, `user_analyses`), `SECRET_KEY`, testes de infraestrutura.
2. Backend de conta: cadastro, login, logout, `/me`, e-mails, redefinição, limites.
3. Dados por usuário: vínculo na lista, teto salvo, rotas protegidas e filtradas, remoção da palavra secreta.
4. Front: telas de entrada, sair, teto do servidor, 401.
5. Docs (README, CHANGELOG, `.env.example`, AGENTS), limpeza da produção e deploy.
