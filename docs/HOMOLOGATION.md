# Homologacao Local - VW Engenharia ERP

## Objetivo

Subir uma instancia completa da V1 com dados demonstrativos para navegacao e validacao funcional.

Este ambiente e exclusivamente de homologacao/desenvolvimento.

## 1. Preparar variaveis

Na raiz:

```bash
cp .env.homologation.example .env.homologation
```

O arquivo de exemplo usa credenciais ficticias e previsiveis. Nao reutilize essas senhas em producao.

## 2. Subir a pilha

```bash
docker compose \
  --env-file .env.homologation \
  -f docker-compose.app.yml \
  -f docker-compose.homologation.yml \
  up -d --build postgres redis minio minio-init migrate backend frontend
```

## 3. Carregar dados demonstrativos

```bash
docker compose \
  --env-file .env.homologation \
  -f docker-compose.app.yml \
  -f docker-compose.homologation.yml \
  run --rm seed
```

O seed e idempotente e pode ser executado novamente sem duplicar o conjunto demonstrativo.

## 4. Abrir o ERP

Por padrao:

```text
http://localhost:18080
```

MinIO:

```text
API:     http://localhost:19000
Console: http://localhost:19001
```

## 5. Usuarios de demonstracao

As contas sao definidas pelo arquivo `.env.homologation`.

Valores padrao do exemplo:

| Perfil | Email |
| --- | --- |
| ADMIN | gestor.homologacao@example.com |
| TECNICO | tecnico.homologacao@example.com |
| MANUTENCAO | manutencao.homologacao@example.com |

A senha vem de `HOMOLOGATION_PASSWORD`.

## 6. O que ja vem cadastrado

O conjunto demonstrativo inclui:

- tenant VW Engenharia - Homologacao;
- gestor;
- tecnico de campo;
- usuario de manutencao;
- cliente Condominio Demonstracao;
- empreendimento Residencial Lago Azul;
- ETE ETE-HML-001;
- Aerador I;
- Bomba de Recirculacao I;
- checklist de ETE;
- plano semanal;
- visita futura;
- visita historica revisada;
- medicao de pH;
- ocorrencia do aerador;
- OS planejada;
- solicitacao de material aprovada;
- manutencao preventiva da bomba.

O objetivo e permitir que as principais telas aparecam preenchidas assim que o usuario entrar.

## 7. Smoke test automatico

Com a pilha e o seed prontos:

```bash
HOMOLOGATION_PASSWORD="sua-senha" sh scripts/smoke_homologation.sh
```

O smoke testa:

- `/health`;
- `/ready`;
- carregamento do PWA;
- login ADMIN;
- `/auth/me`;
- dashboard;
- estacao demonstrativa;
- OS demonstrativa;
- login TECNICO;
- bootstrap de campo com visita atribuida.

O CI tambem executa essa validacao automaticamente em containers reais.

## 8. Roteiro de avaliacao visual

### Como gestor

1. entrar como ADMIN;
2. verificar Minha Fila;
3. conferir indicadores;
4. abrir Operacao;
5. verificar solicitacao de material;
6. abrir OS;
7. navegar em Cadastros;
8. abrir a Visao 360 da ETE;
9. verificar Configuracao;
10. verificar Governanca e Auditoria.

### Como tecnico

1. sair;
2. entrar como TECNICO;
3. verificar a visita programada;
4. abrir a visita;
5. simular perda de internet;
6. preencher checklist e medicao;
7. registrar ocorrencia;
8. criar solicitacao;
9. finalizar;
10. recuperar internet e conferir sincronizacao.

### Como manutencao

1. entrar como MANUTENCAO;
2. verificar Minha Fila;
3. localizar a OS planejada;
4. iniciar execucao;
5. registrar manutencao;
6. concluir a OS;
7. voltar como gestor para validar.

## 9. Reiniciar do zero

Para apagar apenas o ambiente local de homologacao:

```bash
docker compose \
  --env-file .env.homologation \
  -f docker-compose.app.yml \
  -f docker-compose.homologation.yml \
  down -v
```

Depois suba e rode o seed novamente.

## 10. Diferenca para producao

Homologacao:
- pode usar senha conhecida de teste;
- cookie pode operar sem HTTPS local;
- MinIO pode ficar exposto em portas locais;
- usa dados ficticios.

Producao:
- segredos fortes;
- HTTPS obrigatorio;
- `REFRESH_COOKIE_SECURE=true`;
- MinIO/object storage protegido;
- sem seed demonstrativo;
- dados reais importados de forma reconciliada.

Nunca execute `seed_homologation.py` no tenant de producao.
