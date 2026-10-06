# VW Engenharia - ERP Operacional

ERP/PWA mobile-first e offline-first para a operacao da VW Engenharia.

O produto cobre o ciclo:

`Cliente -> Empreendimento -> Estacao -> Ativo -> Planejamento -> Visita -> Checklist -> Ocorrencia -> OS -> Manutencao -> Evidencia -> Revisao`

O ERP e a fonte transacional oficial. BI, analytics avancado, IA conversacional e agentes pertencem ao iAnalisys.

## Estado atual

A V1 possui:

- autenticacao, tenant e RBAC;
- clientes, empreendimentos, estacoes, tipos de ativo e ativos;
- equipe e perfis;
- planos recorrentes e geracao idempotente de agenda;
- PWA de campo com IndexedDB e outbox offline;
- checklists configuraveis e versionados;
- medicoes estruturadas;
- evidencias em object storage;
- ocorrencias;
- materiais/servicos/terceiros;
- ordens de servico com prioridade, SLA e maquina de estados;
- manutencao preventiva/corretiva;
- revisao de visitas;
- Minha Fila por perfil;
- alertas operacionais;
- Visao 360 da estacao;
- exportacoes CSV;
- auditoria consultavel;
- API read-only versionada para iAnalisys;
- migracao historica XLSX com staging, reconciliacao e carga em lotes.

Consulte:
- `docs/SPEC_V1.md`
- `docs/ARCHITECTURE.md`
- `docs/RBAC_V1.md`
- `docs/RELEASE_V1.md`
- `docs/INTEGRATION_IANALISYS.md`

## Stack

- Frontend: React + TypeScript + Vite + PWA
- Backend: Python 3.12 + FastAPI
- Banco: PostgreSQL
- Cache/apoio operacional: Redis
- Evidencias: S3 compativel / MinIO
- Migrations: Alembic
- Infra local: Docker Compose
- CI: GitHub Actions

## Subida local

### 1. Dependencias de infraestrutura

Na raiz:

```bash
docker compose up -d
```

Isso sobe PostgreSQL, Redis e MinIO conforme `docker-compose.yml`.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --reload
```

No Windows PowerShell, ative o ambiente virtual com o comando equivalente do PowerShell.

### 3. Frontend

Em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

## Variaveis de ambiente

Use `.env.example` como referencia.

Nunca versione:
- JWT secret real;
- senha de banco de producao;
- credenciais S3/MinIO de producao;
- chave de integracao iAnalisys;
- qualquer segredo operacional.

## Primeiro administrador

Com o banco migrado, configure:

- `BOOTSTRAP_TENANT_NAME`
- `BOOTSTRAP_TENANT_SLUG`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_NAME`
- `BOOTSTRAP_ADMIN_PASSWORD`

Depois execute:

```bash
cd backend
python scripts/bootstrap_admin.py
```

O script e idempotente para tenant/usuario ja existentes.

## Migracao historica da planilha

A forma recomendada e usar a area **Governanca > Migracao** no ERP:

1. enviar o XLSX;
2. validar contagens do staging;
3. executar auto-mapeamento apenas para nomes exatos;
4. mapear manualmente os rotulos restantes;
5. revisar erros;
6. materializar uma amostra;
7. reconciliar;
8. importar os lotes restantes.

Alternativamente:

```bash
cd backend
python scripts/stage_legacy_visits.py --tenant-id <UUID> --file "/caminho/Visitas MW.xlsx"
```

Por padrao, registros historicos nao sao transformados em backlog atual de revisao.

## Integracao com iAnalisys

ADMIN/SUPERADMIN cria a credencial em **Governanca > iAnalisys**.

O segredo e exibido uma unica vez.

O consumidor envia:

```text
X-Integration-Key: <segredo>
```

Recursos read-only estao sob:

```text
/api/v1/integration/v1/{resource}
```

A V1 nao permite escrita do iAnalisys no ERP.

## Testes e gate de CI

Backend:

```bash
cd backend
ruff check app tests scripts alembic
alembic upgrade head
pytest -q
```

Frontend:

```bash
cd frontend
npm install
npm run build
```

O GitHub Actions executa esses gates automaticamente.

A jornada integrada da V1 esta em `backend/tests/test_v1_acceptance.py`.

## Principios arquiteturais

1. Nao reproduzir a planilha como sistema.
2. Visita, ativo, medicao, ocorrencia, solicitacao e OS sao entidades distintas.
3. Offline-first para o tecnico.
4. Multi-tenant desde a fundacao.
5. Tenant nunca e escolhido livremente pelo frontend.
6. Historico operacional nao e apagado para simplificar cadastro.
7. Alertas e Minha Fila sao derivados da fonte transacional, evitando estado duplicado.
8. Evidencias ficam fora do PostgreSQL.
9. Integracao iAnalisys e read-only na V1.
10. Nenhuma dependencia de LLM/IA generativa existe no ERP.

## Responsabilidade do iAnalisys

- BI;
- dashboards analiticos avancados;
- analises historicas;
- IA conversacional;
- agentes;
- RAG;
- comparacoes e tendencias;
- previsoes e insights gerenciais.

O ERP VW Engenharia permanece focado em executar e registrar corretamente a operacao.
