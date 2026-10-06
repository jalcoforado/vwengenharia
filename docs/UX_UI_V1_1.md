# UX/UI V1.1 - Direcao de Produto

## Objetivo

Elevar o ERP da VW Engenharia de uma interface funcional para uma experiencia de produto SaaS premium, mantendo velocidade, legibilidade e operacao mobile-first.

A prioridade nao e decoracao. A UX deve reduzir tempo de decisao, erros de operacao e carga cognitiva.

## Principios

1. **Acao antes de informacao**: cada tela deve deixar claro o que precisa de atencao e qual a proxima acao.
2. **Hierarquia visual forte**: titulo, contexto, KPI, alerta e acao primaria nao podem competir entre si.
3. **Densidade controlada**: desktop usa melhor o espaco sem virar planilha; mobile mantem alvos de toque confortaveis.
4. **Estados legiveis**: status, prioridade, SLA, offline e sincronizacao devem ser reconhecidos antes de serem lidos.
5. **Consistencia**: botoes, inputs, cards, bordas, espacamento e feedback seguem um unico sistema.
6. **Progressive disclosure**: detalhes operacionais aparecem quando necessarios; a tela inicial prioriza excecoes.
7. **Campo primeiro**: tecnico deve concluir uma visita com poucos toques, mesmo offline.
8. **Acessibilidade**: foco visivel, contraste, alvos de toque, labels e estados nao dependem apenas de cor.

## Linguagem visual

- Base clara e neutra, com verde institucional usado como acento e nao como preenchimento dominante.
- Superficies brancas com bordas suaves e sombras discretas.
- Tipografia de sistema, alta legibilidade, pesos fortes apenas em hierarquia e numeros.
- Radius consistente: 10/14/18/24 px conforme nivel de superficie.
- Espacamento baseado em escala de 4 px.
- Cores semanticas separadas da identidade visual: sucesso, alerta, risco e informacao.

## Navegacao

### Gestao
- Topbar reduzida e utilitaria.
- Navegacao principal sticky com icone + label.
- Secoes: Visao geral, Operacao, Cadastros, Configuracao, Governanca.
- Desktop com leitura horizontal limpa; mobile com scroll sem quebrar contexto.

### Campo
- Agenda como tela principal.
- Card de visita com hora, estacao, contexto e status.
- Dentro da visita: acao primaria fixa/obvia, blocos na ordem natural do trabalho.
- Offline/sync sempre visiveis no shell.

## Dashboard

A Visao Geral deve responder rapidamente:
1. O que esta atrasado?
2. O que e critico?
3. O que precisa de validacao?
4. O que acontece hoje?
5. Onde devo clicar agora?

KPIs devem ser escaneaveis, com numero dominante e rotulo curto.

## Formularios

- Labels sempre acima do campo.
- Foco visivel.
- Altura minima de 44 px em mobile.
- Agrupar campos relacionados.
- Acoes destrutivas ou de transicao irreversivel com diferenciacao clara.
- Feedback de sucesso/erro proximo da area alterada.

## Estados vazios

Nunca apenas "nenhum item".
Quando aplicavel, explicar:
- por que esta vazio;
- se isso e bom ou requer acao;
- qual proxima acao possivel.

## Primeira entrega visual

Sem mudar contratos de API ou banco:
- tokens de design;
- topbar refinada;
- navegacao de gestao com icones;
- cards/KPIs com melhor hierarquia;
- botoes e inputs consistentes;
- foco e hover;
- superficies e listas menos pesadas;
- melhor responsividade;
- melhor visual da tela de login.

## Proximas entregas

1. Agenda operacional em visual diario/semanal.
2. Command center de pendencias.
3. Skeleton/loading states.
4. Toasts em vez de mensagens persistentes.
5. Empty states orientados a acao.
6. Bottom navigation para perfis de campo em mobile.
7. QR Code como entrada contextual para estacao/ativo.
8. Portal CLIENTE com linguagem simplificada.
