# VW Engenharia - Plataforma de Operacoes

PWA para gestao de visitas tecnicas, ativos, ocorrencias, ordens de servico, manutencao, SLA, evidencias e inteligencia operacional da VW Engenharia.

## Objetivo

Substituir gradualmente o controle operacional hoje realizado em planilha por uma plataforma mobile-first, offline-first e preparada para SaaS.

## Stack alvo

- Frontend: React + TypeScript + Vite + PWA
- Backend: Python + FastAPI
- Banco: PostgreSQL
- Cache/filas: Redis
- Arquivos: S3 compativel / MinIO
- IA: gateway multi-provider (Kimi, OpenAI, Anthropic etc.)
- Infra: Docker Compose no inicio

## Estrutura

backend/ API FastAPI e regras de negocio
frontend/ PWA React/TypeScript
docs/ arquitetura, SPEC e decisoes
.github/ CI

## Principios

1. Nao reproduzir a planilha em formato web.
2. Visita, ativo, medicao, ocorrencia e OS sao entidades separadas.
3. Offline-first para operacao de campo.
4. Multi-tenant desde a fundacao, mesmo com apenas a VW no primeiro momento.
5. IA usa ferramentas seguras da aplicacao; nao SQL livre.
6. Acoes sensiveis de IA exigem aprovacao humana.
7. Toda operacao relevante deve ser auditavel.

Consulte docs/SPEC_V1.md e docs/ARCHITECTURE.md.
