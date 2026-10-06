$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$EnvFile = ".env.homologation"
if (-not (Test-Path $EnvFile)) {
  $EnvFile = ".env.homologation.example"
}

$Compose = @(
  "compose",
  "--env-file", $EnvFile,
  "-f", "docker-compose.app.yml",
  "-f", "docker-compose.homologation.yml"
)

& docker @Compose down
if ($LASTEXITCODE -ne 0) {
  throw "Falha ao encerrar a homologacao."
}

Write-Host "Homologacao encerrada. Os volumes foram preservados." -ForegroundColor Green
Write-Host "Para apagar tambem os dados locais: docker compose --env-file $EnvFile -f docker-compose.app.yml -f docker-compose.homologation.yml down -v"
