#!/bin/sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:18080}"
ADMIN_EMAIL="${HOMOLOGATION_ADMIN_EMAIL:-gestor.homologacao@example.com}"
PASSWORD="${HOMOLOGATION_PASSWORD:?HOMOLOGATION_PASSWORD is required}"

wait_for() {
  url="$1"
  attempts=0
  until curl -fsS "$url" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "Timed out waiting for $url" >&2
      return 1
    fi
    sleep 2
  done
}

echo "Waiting for liveness..."
wait_for "${BASE_URL}/health"

echo "Waiting for readiness..."
wait_for "${BASE_URL}/ready"

echo "Checking SPA..."
curl -fsS "${BASE_URL}/" | grep -q "VW Engenharia"

echo "Checking login..."
LOGIN_BODY=$(printf '{"email":"%s","password":"%s"}' "$ADMIN_EMAIL" "$PASSWORD")
LOGIN_RESPONSE=$(curl -fsS -H "Content-Type: application/json" -d "$LOGIN_BODY" "${BASE_URL}/api/v1/auth/login")
TOKEN=$(printf "%s" "$LOGIN_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

echo "Checking authenticated profile..."
curl -fsS -H "Authorization: Bearer $TOKEN" "${BASE_URL}/api/v1/auth/me" >/dev/null

echo "Checking dashboard..."
curl -fsS -H "Authorization: Bearer $TOKEN" "${BASE_URL}/api/v1/dashboard/overview" >/dev/null

echo "Checking seeded station..."
STATIONS=$(curl -fsS -H "Authorization: Bearer $TOKEN" "${BASE_URL}/api/v1/stations")
printf "%s" "$STATIONS" | python3 -c 'import json,sys; data=json.load(sys.stdin); assert any(x.get("code")=="ETE-HML-001" for x in data)'

echo "Checking seeded work order..."
ORDERS=$(curl -fsS -H "Authorization: Bearer $TOKEN" "${BASE_URL}/api/v1/work-orders")
printf "%s" "$ORDERS" | python3 -c 'import json,sys; data=json.load(sys.stdin); assert any("Aerador I" in x.get("description","") for x in data)'

echo "Checking field login..."
TECH_EMAIL="${HOMOLOGATION_TECH_EMAIL:-tecnico.homologacao@example.com}"
TECH_BODY=$(printf '{"email":"%s","password":"%s"}' "$TECH_EMAIL" "$PASSWORD")
TECH_RESPONSE=$(curl -fsS -H "Content-Type: application/json" -d "$TECH_BODY" "${BASE_URL}/api/v1/auth/login")
TECH_TOKEN=$(printf "%s" "$TECH_RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
BOOTSTRAP=$(curl -fsS -H "Authorization: Bearer $TECH_TOKEN" "${BASE_URL}/api/v1/field/bootstrap")
printf "%s" "$BOOTSTRAP" | python3 -c 'import json,sys; data=json.load(sys.stdin); assert len(data["visits"]) >= 1'

echo "Homologation smoke test passed."
