#!/bin/sh
# Valida o backend como o job "backend" do CI: ruff, alembic (sobe/desce/sobe) e pytest,
# num Postgres 16 descartavel. Roda da raiz do repositorio ou de qualquer subpasta.
set -u

ROOT=$(git rev-parse --show-toplevel)
NET="mwci-$$"
DB="mwci-pg-$$"

cleanup() {
  docker stop "$DB" >/dev/null 2>&1
  docker network rm "$NET" >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

docker info >/dev/null 2>&1 || { echo "Docker nao esta acessivel. Abra o Docker Desktop e tente de novo."; exit 2; }

docker network create "$NET" >/dev/null
docker run -d --rm --name "$DB" --network "$NET" \
  -e POSTGRES_DB=mwengenharia -e POSTGRES_USER=mw -e POSTGRES_PASSWORD=mw postgres:16 >/dev/null

# Espera o Postgres aceitar conexoes (ate ~30s).
for _ in $(seq 1 30); do
  docker exec "$DB" pg_isready -U mw -d mwengenharia >/dev/null 2>&1 && break
  sleep 1
done

# MSYS_NO_PATHCONV evita que o Git Bash do Windows reescreva os caminhos do container.
MSYS_NO_PATHCONV=1 docker run --rm --network "$NET" -v "$ROOT/backend:/src:ro" \
  -e APP_ENV=test \
  -e DATABASE_URL="postgresql+asyncpg://mw:mw@$DB:5432/mwengenharia" \
  -e JWT_SECRET=test-secret-must-have-at-least-32-bytes-long \
  python:3.12 sh -c '
set -e
cp -r /src /w && cd /w
# Arquivos montados do Windows chegam como executaveis e disparam o EXE002 do ruff.
find . -name "*.py" -exec chmod -x {} +
pip install -q -e ".[dev]" 2>&1 | grep -v -E "notice|WARNING" || true
echo "== ruff";    ruff check app tests scripts alembic
echo "== alembic"; alembic upgrade head 2>&1 | tail -1
                   alembic downgrade -1 2>&1 | tail -1
                   alembic upgrade head 2>&1 | tail -1
echo "== pytest";  pytest -q 2>&1 | grep -E "passed|failed|error|FAILED|^E  " | tail -40
'
