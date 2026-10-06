#!/bin/sh
set -eu

BASE_URL="${BASE_URL:-http://127.0.0.1:18080}"
ADMIN_EMAIL="${HOMOLOGATION_ADMIN_EMAIL:-gestor.homologacao@example.com}"
PASSWORD="${HOMOLOGATION_PASSWORD:?HOMOLOGATION_PASSWORD is required}"

echo "Checking liveness..."
curl -fsS "${BASE_URL}/health" >/dev/null

echo "Checking readiness..."
curl -fsS "${BASE_URL}/ready" >/dev/null

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

echo "Checking seeded stations..."
STATIONS=$(curl -fsS -H "Authorization: Bearer $TOKEN" "${BASE_URL}/api/v1/stations")
printf "%s" "$STATIONS" | python3 -c 'import json,sys; data=json.load(sys.stdin); assert any(x.get("code")=="ETE-HML-001" for x in data)'

echo "Homologation smoke test passed."
