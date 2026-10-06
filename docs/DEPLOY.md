# Deploy e Homologacao - VW Engenharia ERP

## Objetivo

Este documento descreve a subida da V1 do ERP em um ambiente de homologacao ou producao simples, usando Docker Compose.

A arquitetura inicial suporta bem um deployment em VPS unica, desde que CPU, memoria, disco, backups e concorrencia sejam monitorados.

## Servicos

`docker-compose.app.yml` sobe:

- PostgreSQL
- Redis
- MinIO
- migrate (execucao unica de Alembic)
- backend FastAPI
- frontend Nginx + PWA

O Nginx do frontend faz proxy de `/api/` para o backend.

## Preparacao

Copie:

```bash
cp .env.production.example .env.production
```

Preencha obrigatoriamente:

- POSTGRES_PASSWORD
- JWT_SECRET
- S3_PUBLIC_ENDPOINT
- S3_ACCESS_KEY
- S3_SECRET_KEY

Use valores fortes e exclusivos.

## Subida

```bash
docker compose --env-file .env.production -f docker-compose.app.yml up -d --build
```

O fluxo e:

1. PostgreSQL inicia e passa no healthcheck.
2. MinIO inicia.
3. O bucket e criado idempotentemente.
4. O servico `migrate` executa `alembic upgrade head`.
5. O backend inicia somente se a migration concluir.
6. O frontend inicia e publica a aplicacao.

## Primeiro admin

A criacao do primeiro admin deve ser executada em ambiente controlado.

Exemplo:

```bash
docker compose --env-file .env.production -f docker-compose.app.yml run --rm \
  -e BOOTSTRAP_TENANT_NAME="VW Engenharia" \
  -e BOOTSTRAP_TENANT_SLUG="vw-engenharia" \
  -e BOOTSTRAP_ADMIN_EMAIL="admin@example.com" \
  -e BOOTSTRAP_ADMIN_NAME="Administrador" \
  -e BOOTSTRAP_ADMIN_PASSWORD="<senha-forte>" \
  backend python scripts/bootstrap_admin.py
```

Nao registre a senha no historico do shell em producao. Prefira secret manager ou injecao segura.

## Reverse proxy e HTTPS

Para producao, coloque o compose atras de um reverse proxy HTTPS (por exemplo, Cloudflare Tunnel, Traefik, Caddy ou Nginx externo).

Requisitos:

- HTTPS obrigatorio;
- `REFRESH_COOKIE_SECURE=true`;
- dominio estavel;
- encaminhar `X-Forwarded-Proto`;
- restringir portas internas do PostgreSQL, Redis e MinIO;
- nao expor o console MinIO publicamente.

O compose de aplicacao nao publica PostgreSQL, Redis ou MinIO diretamente na interface externa.

## Evidencias e S3_PUBLIC_ENDPOINT

`S3_PUBLIC_ENDPOINT` precisa ser um endereco que o navegador do usuario consiga acessar para upload presigned.

Exemplo:

```text
https://arquivos.vw.exemplo.com
```

O endereco interno do backend permanece:

```text
http://minio:9000
```

Nunca use uma URL interna Docker como endpoint publico do navegador.

## Healthcheck

A aplicacao expoe:

```text
GET /health
```

Atraves do frontend/Nginx, o mesmo endpoint e encaminhado ao backend.

Para monitoramento externo:

```bash
curl -f https://erp.exemplo.com/health
```

## Backup minimo

### PostgreSQL

Fazer backup diario e manter rotacao.

Exemplo manual:

```bash
docker compose --env-file .env.production -f docker-compose.app.yml exec -T postgres \
  pg_dump -U vw -d vwengenharia > vwengenharia.sql
```

### MinIO

O volume/object storage de evidencias deve possuir backup independente do PostgreSQL.

O banco guarda metadados; fotos e arquivos nao estao dentro do dump SQL.

## Restauracao

Uma restauracao completa exige:

1. restaurar PostgreSQL;
2. restaurar o bucket/volume de evidencias;
3. garantir que as mesmas object keys existam;
4. subir a mesma ou uma versao compativel da aplicacao;
5. executar migrations apenas para frente quando aplicavel;
6. validar uma amostra de anexos antes de liberar usuarios.

## Atualizacao de versao

Fluxo recomendado:

```bash
git pull
docker compose --env-file .env.production -f docker-compose.app.yml build
docker compose --env-file .env.production -f docker-compose.app.yml up -d
```

O servico `migrate` aplica a migration antes do backend da nova versao iniciar.

Para mudancas destrutivas futuras, usar plano de migration expand/contract e rollback explicito.

## Observabilidade inicial

Monitorar no minimo:

- disponibilidade do `/health`;
- uso de CPU;
- memoria;
- disco;
- espaco do PostgreSQL;
- volume de evidencias;
- erros 5xx;
- tempo de resposta;
- falhas de login;
- crescimento da fila offline/sincronizacao quando houver telemetria;
- vencimento de backup.

## Recomendacao para homologacao VW

Antes de producao:

1. subir ambiente de homologacao separado;
2. cadastrar equipe real;
3. configurar checklist real;
4. configurar algumas estacoes;
5. executar jornada presencial com um tecnico usando tablet/celular;
6. testar modo aviao;
7. testar fotos/evidencias;
8. testar revisao e OS;
9. carregar amostra da planilha historica;
10. reconciliar;
11. somente depois executar a carga completa.

## Fronteira com iAnalisys

O iAnalisys nao compartilha a escrita do banco do ERP.

A integracao oficial ocorre por:

```text
/api/v1/integration/v1/*
```

com credencial read-only por tenant.

Na V1:
- iAnalisys le;
- ERP escreve;
- nenhum agente ou LLM altera a operacao.
