# Arquitetura alvo

## Visao

Arquitetura inicial em monolito modular, separando dominios de negocio e evitando microservicos prematuros.

```text
PWA React/TypeScript
        |
        v
FastAPI / API v1
        |
+-------+----------+----------+
|                  |          |
PostgreSQL       Redis       S3/MinIO
        |
        +--------------------+
                 |
             IA Gateway
                 |
      Kimi / OpenAI / Anthropic
```

## Dominios

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
- notificacoes
- indicadores
- IA e agentes
- auditoria

## Regras arquiteturais

- Toda tabela de negocio deve carregar `tenant_id` quando aplicavel.
- Toda query tenant-scoped deve filtrar por `tenant_id` parametrizado.
- Fotos/documentos fora do banco relacional.
- IA nao executa SQL arbitrario.
- Ferramentas de IA respeitam RBAC e tenant.
- Acoes mutaveis disparadas pela IA exigem confirmacao/aprovacao quando houver risco operacional.
- O app de campo deve continuar operando sem internet e sincronizar depois.
