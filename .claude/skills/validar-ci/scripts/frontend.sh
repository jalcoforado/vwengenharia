#!/bin/sh
# Valida o frontend como o job "frontend" do CI: npm install + npm run build (tsc -b e vite)
# em Node 22, numa copia limpa, sem tocar no node_modules local.
set -u

ROOT=$(git rev-parse --show-toplevel)
docker info >/dev/null 2>&1 || { echo "Docker nao esta acessivel. Abra o Docker Desktop e tente de novo."; exit 2; }

MSYS_NO_PATHCONV=1 docker run --rm -v "$ROOT/frontend:/src:ro" node:22 sh -c '
cp -r /src /w && cd /w && rm -rf node_modules dist
npm install --no-audit --no-fund --loglevel=error >/dev/null 2>&1 || { echo "npm install falhou"; exit 1; }
npm run build 2>&1 | grep -E "error|built in|TS[0-9]+" | head -40
'
