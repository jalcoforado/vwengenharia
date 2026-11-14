---
name: subir-ambiente-local
description: Sobe, atualiza ou diagnostica o ambiente local de homologação do ERP da MW (http://localhost:18080) — Docker, banco, migrations, backend e frontend — e confere que o login funciona. Use quando pedirem para subir o app, aplicar uma mudança no ambiente local, ou quando o login der "inválido", a página não abrir ou a tela não mostrar uma alteração recente.
---

# Subir o ambiente local

O ambiente de homologação roda em Docker: Postgres, Redis, S3Mock, `migrate` (aplica as
migrations e sai), backend FastAPI e frontend (nginx com o build do React) em
**http://localhost:18080**.

Todos os comandos rodam da raiz do repositório, no PowerShell.

## Diagnóstico primeiro

Antes de subir ou reconstruir, descubra o estado:

```powershell
docker info *> $null; if ($LASTEXITCODE -ne 0) { "Docker desligado" }
docker ps --format "{{.Names}}`t{{.Status}}"
try { (Invoke-RestMethod http://localhost:18080/ready -TimeoutSec 5).status } catch { "app fora do ar" }
```

**"Email ou senha inválidos" quase nunca é senha errada quando o app está fora do ar.** A página
abre do cache do navegador mesmo sem servidor. Confira `/ready` antes de suspeitar da senha.

## Subir pela primeira vez ou depois de reiniciar o computador

Se o Docker estiver desligado, abra o Docker Desktop
(`Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"`) e espere `docker info`
responder. Depois:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-homologation.ps1
```

O script cria `.env.homologation` se faltar, sobe tudo, carrega os dados de demonstração e faz
o smoke de login.

## Aplicar uma mudança de código

Mais rápido que o script completo, reconstrói só o que mudou:

```powershell
$compose = @("compose","--env-file",".env.homologation","-f","docker-compose.app.yml","-f","docker-compose.homologation.yml")
docker @compose up -d --build migrate backend frontend   # mudança no backend ou migration
docker @compose up -d --build frontend                   # só frontend
docker @compose logs migrate | Select-String "Running upgrade"
```

Depois diga ao usuário para apertar **Ctrl+F5**: o app é um PWA e guarda a versão anterior.

## Conferir

```powershell
$b = "http://localhost:18080"
$pw = (Select-String -Path .env.homologation -Pattern '^HOMOLOGATION_PASSWORD=').Line.Split('=',2)[1]
$t = Invoke-RestMethod "$b/api/v1/auth/login" -Method Post -ContentType "application/json" -Body (@{email="gestor.homologacao@example.com"; password=$pw} | ConvertTo-Json)
"login ok: " + [bool]$t.access_token
```

Para provar que uma mudança de tela está no ar, procure um texto novo dela no JavaScript servido
(`/assets/index-*.js`).

## Cuidados

- Nunca rode `down -v` sem o usuário pedir: apaga o banco e os arquivos locais.
- Não altere `.env.homologation`: é do usuário e não é versionado.
- As credenciais de demonstração estão em `.env.homologation`; o padrão é o usuário
  `gestor.homologacao@example.com`.
