---
name: ux-telas-mw
description: Decisões de UX e padrão visual das telas do ERP da MW Engenharia (React + CSS próprio com tokens --mw-*). Use ao criar ou alterar qualquer tela, formulário, lista, consulta ou mensagem do app — cadastros, gestão, campo do técnico e portal do cliente — e quando pedirem "mais claro", "mais bonito", "padronizar", "igual às outras telas" ou uma revisão de UX. Não cobre painéis analíticos e gráficos, que são do iAnalisys.
---

# UX das telas da MW

Você decide **como a tela funciona e se apresenta**, e garante que ela sai no mesmo padrão das
telas que já existem. Ordem de precedência, quando houver conflito:

1. O que o usuário pediu nesta conversa.
2. `docs/UX_UI_V1_1.md` (direção de produto do Jorge).
3. Os padrões já implementados no código (esta skill e `references/padrao-cadastro.md`).
4. Os princípios gerais abaixo.

Antes de criar um componente, procure um equivalente em `frontend/src/components/` e reuse.

## Princípios

1. **Ação antes de informação.** Cada tela deixa claro o que precisa de atenção e qual a próxima
   ação. Antes de desenhar, responda: *que decisão ou tarefa esta tela resolve?*
2. **Dado primeiro, sem decoração.** Nada de ornamento, gradiente sem função ou ícone no lugar de
   texto.
3. **Cor só com significado.** Marrom da marca (`--mw-primary`) para ação principal e seleção;
   verde, âmbar, vermelho e azul só para estado (sucesso, atenção, erro, informação). O vermelho
   de erro (`--mw-danger-text`) é distinto do marrom de propósito: não aproxime os dois.
4. **Estados reconhecíveis antes de lidos.** Status, prioridade, SLA, offline e sincronização usam
   etiqueta com forma e cor, nunca só cor (acessibilidade).
5. **Texto de interface importa mais que ícone.** Botão diz o que faz ("Cadastrar contratante",
   "Liberar portal"); mensagem de sucesso confirma o resultado; erro diz o que houve e como
   resolver. Português com acento, sem jargão técnico (`client_id`, `422`) na tela.
6. **Campo primeiro.** No app do técnico: poucos toques, ordem natural do trabalho, alvos de toque
   de 44 px, funciona offline (ver o agente `especialista-campo-offline`).
7. **Animação só com função**, de 150 a 200 ms, e respeitando `prefers-reduced-motion`.

## Tokens e componentes

- Cores, raios e sombras: só pelas variáveis `--mw-*` de `frontend/src/styles.css`. Não escreva
  cor solta (`#...`) em regra nova; se faltar um token, crie-o no `:root`.
- Raios: 10 / 14 / 18 / 24 px (`--mw-radius-sm/md/lg/xl`), conforme o nível da superfície.
- Espaçamento em múltiplos de 4 px, com `gap` em grid ou flex.
- Ícones: `lucide-react` (confira se o ícone existe na versão instalada antes de usar).
- Números alinhados em coluna: `font-variant-numeric: tabular-nums`.
- Atenção à especificidade do CSS: regras antigas como `.client-contact-row span:not(.status)`
  vencem classes simples. Se uma etiqueta sair com a cor errada, aumente o seletor da regra nova
  em vez de usar `!important`.

## Padrões de tela

**Cadastro (lista + formulário).** Todos os cadastros seguem o mesmo esqueleto — veja
`references/padrao-cadastro.md`, com o exemplo de `ContractingPartyAdmin.tsx`:

- Barra no topo: busca (`.search-field`), filtros (`.admin-toolbar-select`) e o botão
  "Novo <coisa>" (`.primary-button`).
- Formulário **recolhível acima da lista** (`useFormPanel`): abre em "Novo" e no lápis da linha,
  rola até ele e foca o primeiro campo. Ao cadastrar, fica aberto e limpo para o próximo; ao
  concluir uma edição, fecha.
- Lista em tabela (`TableHead`, `.collab-table`, `.collab-row`): avatar com iniciais, nome em
  negrito, uma linha de resumo, etiqueta de tipo (`.collab-chip`), coluna de contato, status
  (`.collab-status`) e ações por ícone (`.icon-action`) mais o menu ⋮ (`RowMenu`).
- Ações por linha, nesta ordem: consultar (olho), ações específicas, editar (lápis), menu ⋮.
  Ação destrutiva (inativar, bloquear) fica no menu, marcada como `danger`.
- Nada é excluído: "Inativar" e "Reativar".

**Consulta (somente leitura).** Abre logo abaixo da linha, pelo ícone de olho (`Eye`) ou clicando
no nome (`RowName`, que usa o mesmo estado do olho), num
`.client-contacts` com seções `<section>` e `.eyebrow`, campos em `<dl className="detail-grid">`
com o componente `Field` (`DevelopmentDetails.tsx`). Deixe claro que é consulta: sem campos
editáveis, e um caminho para editar (o lápis da linha). Só uma consulta ou painel aberto por linha.

**Formulário.**
- Rótulo acima do campo. Obrigatório marcado com `<b className="required-mark">*</b>` e legenda
  `.required-hint` no fim. "Ao menos um entre A e B" usa `**` e diz isso na legenda.
- A obrigatoriedade é validada **na tela** antes de enviar, com mensagem que diz o campo que falta.
  O servidor continua aceitando o mínimo, para não quebrar carga de dados e testes.
- CPF/CNPJ: `isValidCpfCnpj` e `normalizeDocument` (grava só dígitos) e `formatDocument` para
  exibir (`lib/document.ts`). Aceita CNPJ alfanumérico.
- Telefone e WhatsApp: `formatPhone` enquanto digita e `isCompletePhone` ao salvar
  (`lib/phone.ts`); `inputMode="numeric"`.
- Erros do servidor viram mensagem humana: 409 de documento repetido → "Já existe um ... com esse
  CPF/CNPJ"; 422 → "Confira os dados informados"; 403 → quem pode fazer a ação.
- Retorno perto da área alterada: `.inline-feedback` no formulário ou acima da lista.

**Estado vazio.** Nunca só "nenhum item". Diga por que está vazio e qual o próximo passo
(`.empty-state`), e diferencie "nada cadastrado" de "nada encontrado com essa busca".

**Portal do cliente.** Telas próprias, linguagem simples, nada de dado interno da equipe; nunca
reaproveite tela de gestão para o cliente.

## Checklist antes de entregar

- [ ] A tela segue o esqueleto da tela vizinha mais parecida (mesmas classes e componentes).
- [ ] Cores e raios só por `--mw-*`; funciona no tema claro (o app hoje não tem tema escuro).
- [ ] Busca acha por nome e por números (CPF/CNPJ, telefone) digitados sem pontuação.
- [ ] Campos obrigatórios marcados, validados na tela, com legenda.
- [ ] Estado vazio e "nada encontrado" com orientação.
- [ ] Mensagens de sucesso e erro claras, em português, perto da ação.
- [ ] Celular: a tabela não estoura a largura, a toolbar quebra linha, alvos de toque de 44 px.
- [ ] Foco visível no teclado; botões só com ícone têm `title` e `aria-label`.
- [ ] `npm run build` passando (skill `validar-ci`).
- [ ] Diga ao usuário o que precisa ser conferido no navegador: esta checagem não substitui olhar
      a tela (peça um print quando houver dúvida visual).
