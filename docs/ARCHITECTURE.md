# Arquitetura alvo

## Visao

O MW Engenharia e um ERP operacional, nao uma plataforma de IA.

Arquitetura inicial em monolito modular, separando dominios de negocio e evitando microservicos prematuros.

```text
Tecnico / Supervisor / Gestor
            |
            v
     PWA React/TypeScript
            |
            v
        FastAPI / API v1
            |
   +--------+---------+---------+
   |                  |         |
PostgreSQL          Redis     S3/MinIO
   |
   +------------------------------+
                  |
          API de integracao
                  |
                  v
              iAnalisys
        BI / Analytics / IA
```

## Fronteira entre os produtos

### ERP MW Engenharia

Responsavel por:

- dados mestres
- operacao de campo
- workflow
- estados transacionais
- regras de negocio
- auditoria
- evidencias
- SLA
- APIs operacionais

### iAnalisys

Responsavel por:

- BI
- indicadores analiticos avancados
- IA conversacional
- agentes
- RAG
- tendencias
- comparacoes
- previsoes
- inteligencia gerencial

O ERP nao deve conter LLMGateway, prompts, tools de agentes, embeddings, RAG ou qualquer logica de orquestracao de IA.

## Dominios do ERP

- tenants e usuarios
- clientes
- empreendimentos
- estacoes
- ativos
- planejamento de visitas
- visitas e checklists
- medicoes
- ocorrencias
- ordens de servico
- manutencao
- anexos/evidencias
- revisoes
- notificacoes operacionais
- auditoria
- integracao/exportacao

## Regras arquiteturais

- Toda tabela de negocio deve carregar `tenant_id` quando aplicavel.
- Toda query tenant-scoped deve filtrar por `tenant_id` parametrizado.
- Fotos/documentos ficam fora do banco relacional.
- O PWA deve continuar operando sem internet e sincronizar depois.
- O ERP deve expor contratos de API estaveis para consumo pelo iAnalisys.
- Integracoes de leitura devem respeitar tenant, RBAC e auditoria.
- O banco operacional nao deve ser acessado diretamente por LLMs.
- Analise/IA pertence ao iAnalisys.


## Integração com iAnalisys

A fronteira é implementada por API somente leitura e credenciais próprias por tenant.

- o iAnalisys não acessa o banco do ERP;
- não utiliza login humano;
- cada credencial pertence a um único tenant;
- o ERP armazena somente o hash da chave;
- a sincronização é incremental e paginada;
- o contrato externo é versionado em /integration/v1;
- IA, BI e agentes continuam fora deste repositório.

Detalhes: docs/INTEGRATION_IANALISYS.md.
