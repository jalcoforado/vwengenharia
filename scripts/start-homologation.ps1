param(
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Assert-Command {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Comando '$Name' nao encontrado. Instale/inicie o Docker Desktop e tente novamente."
  }
}

Assert-Command "docker"

try {
  docker info *> $null
} catch {
  throw "Docker Desktop nao esta acessivel. Inicie o Docker Desktop e tente novamente."
}

$EnvFile = Join-Path $Root ".env.homologation"
$ExampleEnv = Join-Path $Root ".env.homologation.example"

if (-not (Test-Path $EnvFile)) {
  Copy-Item $ExampleEnv $EnvFile
  Write-Host "Criado .env.homologation a partir do exemplo." -ForegroundColor Yellow
}

$Compose = @(
  "compose",
  "--env-file", ".env.homologation",
  "-f", "docker-compose.app.yml",
  "-f", "docker-compose.homologation.yml"
)

Write-Host "Subindo VW Engenharia ERP - Homologacao..." -ForegroundColor Cyan
& docker @Compose up -d --build postgres redis s3mock migrate backend frontend
if ($LASTEXITCODE -ne 0) {
  throw "Falha ao subir a pilha de homologacao."
}

Write-Host "Carregando dados demonstrativos e sincronizando credenciais..." -ForegroundColor Cyan
& docker @Compose run --rm seed
if ($LASTEXITCODE -ne 0) {
  throw "Falha ao carregar dados demonstrativos."
}

$BaseUrl = "http://localhost:18080"
$Timeout = (Get-Date).AddMinutes(3)

Write-Host "Aguardando aplicacao ficar pronta..." -ForegroundColor Cyan
do {
  try {
    $ready = Invoke-RestMethod -Uri "$BaseUrl/ready" -Method Get -TimeoutSec 5
    if ($ready.status -eq "ready") {
      break
    }
  } catch {
    Start-Sleep -Seconds 2
  }
} while ((Get-Date) -lt $Timeout)

if ((Get-Date) -ge $Timeout) {
  & docker @Compose logs --tail 150
  throw "A aplicacao nao ficou pronta dentro do limite de seguranca."
}

Write-Host "Executando smoke test..." -ForegroundColor Cyan
$envLines = Get-Content $EnvFile
$envMap = @{}
foreach ($line in $envLines) {
  if ($line -match '^[A-Za-z_][A-Za-z0-9_]*=') {
    $parts = $line -split '=', 2
    $envMap[$parts[0]] = $parts[1]
  }
}

$AdminEmail = if ($envMap.ContainsKey("HOMOLOGATION_ADMIN_EMAIL")) {
  $envMap["HOMOLOGATION_ADMIN_EMAIL"]
} else {
  "gestor.homologacao@example.com"
}
$TechEmail = if ($envMap.ContainsKey("HOMOLOGATION_TECH_EMAIL")) {
  $envMap["HOMOLOGATION_TECH_EMAIL"]
} else {
  "tecnico.homologacao@example.com"
}
$MaintEmail = if ($envMap.ContainsKey("HOMOLOGATION_MAINTENANCE_EMAIL")) {
  $envMap["HOMOLOGATION_MAINTENANCE_EMAIL"]
} else {
  "manutencao.homologacao@example.com"
}
$Password = if ($envMap.ContainsKey("HOMOLOGATION_PASSWORD")) {
  $envMap["HOMOLOGATION_PASSWORD"]
} else {
  "Homologacao-VW-2026!"
}

$loginBody = @{
  email = $AdminEmail
  password = $Password
} | ConvertTo-Json

$login = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $loginBody
$headers = @{ Authorization = "Bearer $($login.access_token)" }

$me = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/me" -Headers $headers
$dashboard = Invoke-RestMethod -Uri "$BaseUrl/api/v1/dashboard/overview" -Headers $headers
$stations = Invoke-RestMethod -Uri "$BaseUrl/api/v1/stations" -Headers $headers

if (-not ($stations | Where-Object { $_.code -eq "ETE-HML-001" })) {
  throw "Smoke test falhou: estacao demonstrativa nao encontrada."
}

Write-Host ""
Write-Host "VW Engenharia ERP esta pronto para homologacao." -ForegroundColor Green
Write-Host "Endereco: $BaseUrl" -ForegroundColor Green
Write-Host ""
Write-Host "Usuarios demonstrativos:"
Write-Host "  Gestor:      $AdminEmail"
Write-Host "  Tecnico:     $TechEmail"
Write-Host "  Manutencao:  $MaintEmail"
Write-Host "  Senha:       $Password"
Write-Host ""
Write-Host "Tenant: $($me.tenant_name)"
Write-Host "Estacoes no ambiente: $($stations.Count)"
Write-Host "Dashboard carregado com sucesso."

if (-not $NoBrowser) {
  Start-Process $BaseUrl
}
