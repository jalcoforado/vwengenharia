# Sprint UX/UI 1 - Base visual e produtividade

## Objetivo

Elevar o ERP da VW Engenharia de uma V1 funcional para uma experiencia visual mais profissional, consistente e eficiente, sem alterar regras de negocio e sem incorporar recursos de BI/IA ao ERP.

A prioridade desta sprint e reduzir friccao de uso, aumentar legibilidade e dar ao produto aparencia de sistema comercial maduro.

## Escopo

### 1. Design system

Padronizar:

- tipografia;
- escala de espacamento;
- cores semanticas;
- bordas e raios;
- sombras;
- botoes;
- inputs;
- selects;
- textareas;
- modais;
- drawers;
- cards;
- tabelas;
- badges;
- alertas;
- skeletons;
- estados vazios;
- tooltips.

Criar componentes reutilizaveis sempre que possivel.

### 2. Estrutura global da aplicacao

Melhorar o shell principal:

- sidebar mais limpa;
- agrupamento de menus por dominio;
- item ativo evidente;
- cabecalho consistente;
- breadcrumb;
- titulo e descricao curta por tela;
- area padrao para acoes primarias;
- responsividade adequada para desktop e tablet.

Agrupamento recomendado:

- Visao Geral
- Operacao
- Manutencao
- Cadastros
- Clientes
- Configuracao
- Governanca

### 3. Tabelas e listas

Criar um padrao unico para listas de dados:

- busca;
- filtros;
- ordenacao;
- paginacao;
- loading;
- empty state;
- erro;
- acao por linha;
- badges de status;
- cabecalho fixo quando fizer sentido;
- boa leitura em resolucoes menores.

Nao adicionar features inexistentes no backend apenas para preencher a interface.

### 4. Formularios

Padronizar formularios:

- secoes visuais claras;
- label e helper text;
- mensagens de validacao proximas ao campo;
- acoes primarias e secundarias consistentes;
- confirmacao para acoes destrutivas;
- melhor uso de espaco;
- navegacao por teclado;
- foco visivel.

### 5. Estados visuais

Todos os fluxos principais devem tratar:

- carregando;
- vazio;
- erro;
- sucesso;
- sem permissao;
- dado indisponivel;
- operacao offline quando aplicavel;
- sincronizacao pendente quando aplicavel.

### 6. Responsividade

Validar no minimo:

- desktop 1440 px;
- notebook 1366 px;
- tablet 768 px;
- smartphone 390 px.

Priorizar a jornada do TECNICO em telas pequenas.

### 7. Acessibilidade minima

- contraste adequado;
- foco visivel;
- labels associadas;
- botoes com nome acessivel;
- estados nao dependentes apenas de cor;
- areas de toque adequadas;
- navegacao basica por teclado.

## Telas prioritarias

Refatorar primeiro:

1. Login
2. Dashboard / Visao Geral
3. Agenda / Visitas
4. Minha Fila
5. Ocorrencias
6. Ordens de Servico
7. Estacoes
8. Ativos
9. Clientes
10. Usuarios
11. Integracao iAnalisys
12. Auditoria

## Regras de implementacao

1. Nao alterar contratos de API sem necessidade comprovada.
2. Nao mudar regras de RBAC.
3. Nao remover funcionalidades existentes.
4. Nao introduzir dependencia de IA.
5. Nao duplicar componentes equivalentes.
6. Preferir componentes compartilhados.
7. Preservar rotas existentes sempre que possivel.
8. Manter build e testes verdes.
9. Evitar reescrita total do frontend.
10. Fazer refatoracao incremental e reversivel.

## Criterios de aceite

A sprint sera aceita quando:

- navegacao global estiver visualmente consistente;
- principais telas usarem o mesmo padrao de titulo, acoes, filtros e estados;
- tabelas tiverem comportamento visual consistente;
- formularios tiverem validacao e feedback padronizados;
- telas prioritarias funcionarem em desktop e tablet;
- jornada de tecnico continuar funcional em smartphone;
- estados de loading, vazio e erro estiverem cobertos;
- nao houver regressao funcional;
- `npm run build` estiver verde;
- testes existentes continuarem verdes.

## Ordem sugerida para o Claude Code

### Etapa 1 - Auditoria do frontend

Antes de alterar:

- listar componentes existentes;
- identificar duplicacoes;
- identificar estilos globais;
- identificar biblioteca de UI atual;
- mapear telas prioritarias;
- apontar riscos de regressao.

Entregar um diagnostico curto antes da refatoracao.

### Etapa 2 - Fundacao visual

Criar ou consolidar:

- tokens;
- componentes base;
- page header;
- status badge;
- empty state;
- loading state;
- confirm dialog;
- data table base.

### Etapa 3 - Shell

Refatorar:

- sidebar;
- header;
- breadcrumbs;
- mobile navigation.

### Etapa 4 - Telas prioritarias

Aplicar o novo padrao em lotes pequenos, com build/teste entre lotes.

### Etapa 5 - QA visual

Validar:

- overflow;
- quebra de texto;
- truncamento;
- responsividade;
- contraste;
- espacamentos;
- consistencia de status;
- ausencia de regressao.

## Prompt operacional para o Claude Code

Atue como Engenheiro Front-end Senior e Product Designer especializado em SaaS corporativo.

Implemente a Sprint UX/UI 1 descrita em `docs/UX_UI_SPRINT_1.md`.

Antes de modificar qualquer arquivo:
1. audite o frontend atual;
2. identifique a stack e os componentes existentes;
3. preserve arquitetura e regras de negocio;
4. proponha uma refatoracao incremental;
5. nao altere backend ou contratos de API sem necessidade real;
6. nao introduza IA, chat, RAG ou BI no ERP.

Objetivo visual: produto corporativo moderno, limpo, confiavel e comercializavel, com excelente legibilidade e produtividade operacional.

Evite excesso de efeitos, gradientes decorativos, glassmorphism e componentes visualmente chamativos sem funcao. Priorize clareza, hierarquia, densidade adequada e consistencia.

Depois de cada lote de alteracoes:
- execute lint;
- execute testes aplicaveis;
- execute build;
- corrija regressões antes de seguir.

Nao tente redesenhar tudo de uma vez. Evolua por camadas e preserve compatibilidade.
