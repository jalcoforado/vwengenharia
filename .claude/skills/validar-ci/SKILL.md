---
name: validar-ci
description: Roda localmente os mesmos portões do CI do ERP da MW (ruff, alembic subindo e descendo, pytest e build do frontend) em containers descartáveis, sem depender de Python ou Node instalados. Use antes de commitar, antes de abrir PR, depois de criar migration ou sempre que perguntarem se "está passando".
---

# Validar como o CI

O CI (`.github/workflows/ci.yml`) roda backend, frontend, containers e o smoke de homologação.
Esta skill reproduz os dois primeiros, que são os que quebram com mudança de código.

## Pré-requisito

Docker Desktop ligado. Se `docker info` falhar, diga para abrir o Docker Desktop; não tente
contornar.

## Passos

Da raiz do repositório:

```bash
sh .claude/skills/validar-ci/scripts/backend.sh
sh .claude/skills/validar-ci/scripts/frontend.sh
```

Rode só o backend se a mudança não tocou `frontend/`, e só o frontend se não tocou `backend/`.

- **backend.sh**: Postgres 16 descartável, `pip install -e .[dev]`, `ruff check`, `alembic upgrade
  head`, `downgrade -1`, `upgrade head` de novo e `pytest -q`. O banco de homologação do app local
  não é tocado.
- **frontend.sh**: Node 22, `npm install` e `npm run build` (inclui a checagem de tipos `tsc -b`),
  numa cópia, sem mexer no `node_modules` local.

Os dois limpam os containers e a rede temporários ao terminar, inclusive se falharem.

## Como relatar

- Diga o número de testes que passaram e se o build passou, em uma linha.
- Se algo falhou, mostre a saída do erro (arquivo, linha, mensagem) e diga se a falha é da
  mudança atual ou já existia na base (`git stash` e rode de novo só se houver dúvida real).
- Nunca diga que "passou" sem ter rodado nesta sessão.
- Diga o que esta skill **não** cobre: o job `containers` (build das imagens Docker) e o
  `homologation-smoke`. Esses só rodam no GitHub ou subindo o ambiente com `subir-ambiente-local`.
