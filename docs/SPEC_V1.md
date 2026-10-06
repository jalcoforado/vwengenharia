# SPEC V1 - VW Engenharia

## 1. Objetivo

Criar uma PWA para controlar o ciclo operacional da VW Engenharia:

`Cliente -> Empreendimento -> Estacao -> Ativo -> Planejamento -> Visita -> Checklist -> Ocorrencia -> OS -> Manutencao -> Evidencia -> Revisao`

A planilha historica serve como fonte de requisitos e migracao, nao como modelo de dados definitivo.

## 2. Contexto observado

A base operacional atual possui aproximadamente 13,8 mil registros de visitas, 129 estacoes/empreendimentos e 5 tecnicos principais. Ela registra medicoes, limpeza, cloracao, equipamentos, observacoes e revisao, mas usa muitos estados em texto livre e concentra pendencias dentro das observacoes.

Principais problemas a resolver:

1. pendencias nao sao entidades rastreaveis;
2. ausencia de OS/SLA estruturados;
3. estados de equipamento em texto livre;
4. medicoes ambiguas (ex.: zero podendo significar nao medido);
5. pouca ou nenhuma evidencia fotografica estruturada;
6. dependencia de filtros e linhas ocultas no Excel;
7. dificuldade de transformar historico em gestao executiva.

## 3. Perfis

- SUPERADMIN
- ADMIN
- GESTOR
- SUPERVISOR
- TECNICO
- MANUTENCAO
- CLIENTE

## 4. MVP funcional

### 4.1 Cadastros

- tenant
- usuario e perfil
- cliente
- empreendimento
- estacao
- ativo/equipamento
- tipos de ativo

### 4.2 Planejamento e visitas

- programar visita
- atribuir tecnico
- iniciar/finalizar visita
- checklist por template
- registrar medicoes com unidade e status
- registrar estado de equipamentos
- observacoes
- anexar fotos
- operar offline
- sincronizar quando houver internet

### 4.3 Ocorrencias

Durante uma visita, o tecnico pode criar uma ocorrencia vinculada a estacao e opcionalmente a um ativo.

Campos minimos:

- tipo
- descricao
- criticidade
- ativo
- fotos
- autor
- data/hora
- status

### 4.4 Ordem de Servico

Uma ocorrencia pode gerar OS.

Estados iniciais:

- ABERTA
- TRIAGEM
- PLANEJADA
- EM_EXECUCAO
- AGUARDANDO_MATERIAL
- AGUARDANDO_TERCEIRO
- CONCLUIDA
- VALIDADA
- CANCELADA

Campos:

- prioridade
- responsavel
- prazo
- SLA
- descricao
- ocorrencia origem
- ativo
- evidencias
- historico de status

### 4.5 Revisao

Visitas finalizadas podem entrar em fila de revisao.

Estados:

- PROGRAMADA
- EM_EXECUCAO
- FINALIZADA
- AGUARDANDO_REVISAO
- REVISADA
- DEVOLVIDA

### 4.6 Dashboard inicial

Indicadores minimos:

- estacoes ativas
- visitas previstas hoje
- visitas realizadas hoje
- visitas atrasadas
- ocorrencias abertas
- OS abertas
- OS fora do SLA
- equipamentos indisponiveis
- estacoes sem visita no periodo configurado

## 5. Offline-first

O frontend usa IndexedDB para:

- visitas do tecnico;
- templates de checklist;
- cadastros necessarios para execucao;
- rascunhos;
- fila local de comandos (outbox);
- metadados de anexos.

Cada comando local recebe um `client_operation_id` UUID para idempotencia.

O backend deve aceitar reenvio seguro e responder com identificador do registro persistido.

Estados visuais:

- SINCRONIZADO
- PENDENTE
- ERRO

Conflitos devem ser registrados e nunca resolvidos silenciosamente quando houver risco de perda de dado.

## 6. Modelo de dados inicial

Entidades principais:

- tenants
- users
- memberships
- clients
- developments
- stations
- asset_types
- assets
- checklist_templates
- checklist_template_items
- visit_plans
- visits
- visit_answers
- measurements
- occurrences
- work_orders
- work_order_status_history
- attachments
- reviews
- audit_events

Todas as entidades operacionais devem possuir identificador UUID.

## 7. Medicoes

Nao usar zero para representar ausencia.

Exemplo valido:

```json
{
  "measurement_type": "PH",
  "status": "MEASURED",
  "value": 7.2,
  "unit": "pH"
}
```

Exemplo de nao medido:

```json
{
  "measurement_type": "PH",
  "status": "NOT_MEASURED",
  "reason": "sem condicao de coleta"
}
```

## 8. Estados de ativos

Estados controlados iniciais:

- OPERANDO
- DESLIGADO
- EM_MANUTENCAO
- AGUARDANDO_MANUTENCAO
- FORA_DA_ESTACAO
- AGUARDANDO_INSTALACAO
- NAO_POSSUI
- NAO_APLICAVEL

Texto complementar continua permitido, mas nao substitui o estado estruturado.

## 9. API v1 proposta

Base: `/api/v1`

### Auth

- POST `/auth/login`
- POST `/auth/refresh`
- GET `/auth/me`

### Estacoes e ativos

- GET `/stations`
- POST `/stations`
- GET `/stations/{id}`
- GET `/stations/{id}/assets`
- POST `/stations/{id}/assets`

### Visitas

- GET `/visits`
- POST `/visits`
- GET `/visits/{id}`
- POST `/visits/{id}/start`
- POST `/visits/{id}/finish`
- POST `/visits/{id}/answers`
- POST `/visits/{id}/measurements`
- POST `/visits/{id}/attachments`

### Ocorrencias

- GET `/occurrences`
- POST `/occurrences`
- GET `/occurrences/{id}`

### OS

- GET `/work-orders`
- POST `/work-orders`
- GET `/work-orders/{id}`
- POST `/work-orders/{id}/assign`
- POST `/work-orders/{id}/transition`
- POST `/work-orders/{id}/attachments`

### Dashboard

- GET `/dashboard/overview`
- GET `/dashboard/stations-health`
- GET `/dashboard/sla`

### Integracao com iAnalisys

O ERP devera disponibilizar contratos de leitura estaveis para o iAnalisys, mantendo o isolamento por tenant.

Escopo inicial:

- estacoes
- ativos
- visitas
- medicoes
- ocorrencias
- ordens de servico
- SLA
- historico de status
- revisoes

A integracao pode evoluir para API dedicada, views de leitura ou eventos, mas o ERP continua sendo a fonte transacional de verdade.

O ERP nao implementara:

- chat
- agentes
- LLMGateway
- RAG
- embeddings
- prompts
- ferramentas de IA
- previsoes por modelo generativo

## 10. Auditoria

Registrar no minimo:

- tenant
- usuario
- acao
- entidade
- id da entidade
- valor anterior quando aplicavel
- valor novo quando aplicavel
- timestamp
- origem/dispositivo

## 11. Migracao da planilha

Criar camada de staging antes da normalizacao.

Fluxo:

1. importar arquivo bruto;
2. preservar linha e conteudo original;
3. normalizar nomes de estacao/tecnico;
4. mapear estados textuais;
5. sinalizar ambiguidades;
6. reconciliar amostra com a VW;
7. carregar tabelas canonicas;
8. emitir relatorio de reconciliacao.

Nunca transformar automaticamente valores ambiguos sem regra aprovada.

## 12. Seguranca

- tenant isolation fail-closed;
- RBAC por membership;
- senhas com hash forte;
- refresh token com rotacao/revogacao;
- anexos com URLs temporarias;
- rate limiting em autenticacao e APIs sensiveis;
- logs sem segredos;
- segredo apenas em ambiente/secret manager;
- trilha de auditoria para mudancas relevantes.

## 13. Estrategia de entrega

### Fase 0 - Fundacao

- repo
- CI
- Docker local
- auth
- tenant
- usuarios
- migrations

### Fase 1 - Cadastros

- clientes
- empreendimentos
- estacoes
- ativos

### Fase 2 - Campo

- planejamento de visita
- PWA
- checklist
- medicoes
- anexos
- offline/outbox

### Fase 3 - Operacao

- ocorrencias
- OS
- SLA
- revisao

### Fase 4 - Gestao

- dashboards
- filtros
- exportacoes

### Fase 5 - Integracao com iAnalisys

- contratos de leitura
- endpoints/exportacoes tenant-scoped
- documentacao de integracao
- dados consistentes para BI e IA externos

### Fase 6 - Migracao e homologacao

- staging
- mapeamentos
- carga historica
- paralelo Excel + novo sistema
- reconciliacao

## 14. Criterios de aceite do MVP

1. Tecnico consegue executar visita inteira sem internet apos sincronizar sua agenda.
2. Ao recuperar conexao, dados sincronizam sem duplicar registros.
3. Toda visita finalizada possui autor, horarios e trilha de sincronizacao.
4. Medicao ausente nao e representada por zero.
5. Ocorrencia pode gerar OS com responsavel, prioridade e prazo.
6. Dashboard identifica OS fora do SLA.
7. Toda leitura/escrita de negocio respeita tenant_id.
8. Usuario de um tenant nao acessa dados de outro tenant.
9. Fotos ficam fora do PostgreSQL e vinculadas por metadados.
10. APIs de integracao respeitam tenant e RBAC.
11. O ERP nao possui dependencia de LLM/IA generativa.
12. Migracao historica fornece contagem de entrada, sucesso, erro e reconciliacao.

## 15. Fora do MVP

- financeiro completo
- compras completas
- estoque completo
- roteirizacao otimizada
- manutencao preditiva
- visao computacional
- chat/IA generativa
- RAG
- fine-tuning
- agentes
- BI analitico avancado


## 16. Fronteira definitiva com o iAnalisys

O VW Engenharia e o ERP operacional e fonte transacional.

O iAnalisys e a camada de inteligencia.

Nenhuma funcionalidade de IA deve ser adicionada a este repositorio sem uma decisao arquitetural explicita que revise esta fronteira.
