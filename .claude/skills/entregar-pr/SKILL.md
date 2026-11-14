---
name: entregar-pr
description: Prepara e abre um pull request do ERP da MW para o Jorge revisar — branch a partir da V1.1, validação local, revisão pelos agentes auditor-tenant-rbac e revisor-arquitetura-mw, commits limpos, descrição com riscos e o que não foi testado, envio e acompanhamento do CI. Use quando pedirem para "abrir PR", "mandar para o Jorge", "entregar" ou "enviar para o GitHub". Não faz merge nem deploy sem pedido explícito.
---

# Entregar um PR

O repositório é `jalcoforado/vwengenharia`, mantido pelo Jorge. A branch de trabalho da V1.1 é
`feat/v1.1-operational-hardening`; a `main` só recebe a V1.1 pelo PR do próprio Jorge.

## 1. Conferir a base

```bash
git fetch origin
git status --short
git log --oneline origin/feat/v1.1-operational-hardening..HEAD
git rev-list --count HEAD..origin/feat/v1.1-operational-hardening   # > 0: a V1.1 andou
```

- Trabalhe numa branch própria criada a partir da V1.1, nunca direto nela nem na `main`.
- Se a V1.1 recebeu commits novos, traga-os (`git merge origin/feat/v1.1-operational-hardening`)
  e resolva conflitos antes de seguir.
- Não reaproveite branch já mesclada.
- Arquivos alterados que não são desta tarefa: pergunte antes de incluí-los.

## 2. Validar

1. Skill `validar-ci` (backend e frontend). Tudo precisa passar.
2. Agente `auditor-tenant-rbac` sobre o diff da branch. Achado 🔴 bloqueia o PR.
3. Agente `revisor-arquitetura-mw` sobre o diff da branch. Achado 🔴 bloqueia; ❓ vai para a
   descrição do PR como pergunta ao Jorge.

## 3. Conferir o que vai sair

```bash
git diff --stat origin/feat/v1.1-operational-hardening..HEAD
git diff origin/feat/v1.1-operational-hardening..HEAD | grep -E '^\+' | grep -i -E 'password|secret|token|BEGIN .*PRIVATE'
git ls-files | grep -i '\.env' # só os .example podem aparecer
```

Nada de `.env` real, chave ou senha verdadeira. Os `.env.*.example` têm valores fictícios e
mudar segredo de exemplo exige combinar com o Jorge (o GitGuardian do repositório acusa).

## 4. Commits

Commits pequenos, por assunto, no estilo do repositório (`feat(escopo): ...`, `fix(...)`,
`chore(...)`), em português, com corpo explicando o porquê, e terminando com a linha de coautoria
que a sessão indicar.

## 5. Descrição do PR

Escreva para o Jorge, que não acompanhou o trabalho. Seções:

- **O que muda**: o comportamento, não a lista de arquivos.
- **Pontos de atenção**: mudanças em login, permissões, portal, banco offline, padrões do
  compose, contrato com o iAnalisys, migrations com carga de dados.
- **Verificação**: o que rodou (`validar-ci`, agentes) e o resultado.
- **Não testado**: seja explícito. Tela não aberta no navegador e comportamento offline num
  aparelho real costumam estar aqui.

Termine com a linha de atribuição que a sessão indicar.

## 6. Enviar e abrir

```bash
git push -u origin <branch>
gh pr create --repo jalcoforado/vwengenharia --base feat/v1.1-operational-hardening \
  --head <branch> --title "<tipo>: <resumo>" --body-file <arquivo>
gh pr checks <numero> --repo jalcoforado/vwengenharia --watch
```

PR empilhado (depende de outro ainda aberto): use o outro como `--base` e diga isso no topo da
descrição; depois do merge do primeiro, troque a base para a V1.1 (`gh pr edit --base`).

## 7. Depois de abrir

- Acompanhe o CI e relate o resultado de cada job. Falha do GitGuardian com senha fictícia de
  exemplo não se resolve aqui: avise que o Jorge precisa dispensar no painel.
- **Merge só com pedido explícito do usuário**, sempre com `--match-head-commit` para não mesclar
  um commit diferente do revisado, e confira depois que a V1.1 contém a branch.
- **Deploy não é feito por esta skill**: é manual, no servidor do Jorge.
