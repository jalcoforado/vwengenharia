# VW Engenharia - ERP Operacional

ERP/PWA para gestao operacional da VW Engenharia: cadastros, visitas tecnicas, ativos, ocorrencias, ordens de servico, manutencao, SLA, evidencias e revisoes.

## Objetivo

Substituir gradualmente o controle operacional hoje realizado em planilha por um ERP mobile-first e offline-first.

Este repositorio e exclusivamente transacional/operacional.

A camada de BI, analytics, IA conversacional, agentes e inteligencia gerencial pertence ao iAnalisys e nao deve ser implementada aqui.

## Responsabilidade do ERP VW

- usuarios e perfis
- clientes
- empreendimentos
- estacoes
- ativos/equipamentos
- programacao de visitas
- visitas e checklists
- medicoes
- ocorrencias
- ordens de servico
- manutencao
- SLA
- evidencias
- revisoes
- auditoria
- APIs de integracao
- exportacao/consulta operacional

## Responsabilidade do iAnalisys

- BI
- dashboards analiticos avancados
- analises historicas
- IA conversacional
- agentes
- RAG
- comparacoes e tendencias
- previsoes
- alertas inteligentes
- insights gerenciais

## Stack

- Frontend: React + TypeScript + Vite + PWA
- Backend: Python + FastAPI
- Banco: PostgreSQL
- Cache/filas: Redis
- Evidencias: S3 compativel / MinIO
- Infra: Docker Compose no inicio

## Principios

1. Nao reproduzir a planilha em formato web.
2. Visita, ativo, medicao, ocorrencia e OS sao entidades separadas.
3. Offline-first para operacao de campo.
4. Multi-tenant desde a fundacao.
5. O ERP e a fonte transacional oficial.
6. O iAnalisys consome o ERP por APIs/views/eventos autorizados.
7. Nenhuma dependencia direta de LLM no ERP.
8. Toda operacao relevante deve ser auditavel.

Consulte docs/SPEC_V1.md e docs/ARCHITECTURE.md.
