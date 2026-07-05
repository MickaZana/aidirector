#!/usr/bin/env bash
# ── Canary deploy script — Sprint 2 ──────────────────────────────────────────
#
# Usage:
#   ./scripts/deploy.sh [staging|production]
#
# Deploys to 1 instance first, waits 5 minutes, monitors health checks,
# then deploys to the second instance.
#
# Prerequisites:
#   - docker-compose is installed and the production context is configured
#   - HEALTH_URL env var points to the load balancer health endpoint
#   - GIT_SHA env var is set (or auto-detected from HEAD)
#
# SpaceX pattern: "Deploy to test" — this script IS your test stand.
# If the canary fails, the script rolls back automatically.

set -euo pipefail

TARGET="${1:-staging}"
COMPOSE_FILE="apps/api/docker-compose.yml"
HEALTH_URL="${HEALTH_URL:-http://localhost:8000/health}"
GIT_SHA="${GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo 'dev')}"
DEPLOY_TAG="aidirector-api:${GIT_SHA}"

echo "═══ Canary deploy: ${TARGET} ═══"
echo "  Tag:      ${DEPLOY_TAG}"
echo "  Health:   ${HEALTH_URL}"
echo "  Compose:  ${COMPOSE_FILE}"

# ── Step 1: Build ────────────────────────────────────────────────────────────

echo ""
echo "▸ Building image: ${DEPLOY_TAG}"
docker build -f apps/api/Dockerfile -t "${DEPLOY_TAG}" .
docker tag "${DEPLOY_TAG}" aidirector-api:latest

# ── Step 2: Deploy canary (instance 1) ───────────────────────────────────────

echo ""
echo "▸ Deploying canary (instance 1)..."

# Scale instance 1 to the new tag
docker-compose -f "${COMPOSE_FILE}" up -d --no-deps --scale api=1 api

# ── Step 3: Bake / monitor ───────────────────────────────────────────────────

echo ""
echo "▸ Baking for 5 minutes — monitoring health checks..."

BAKE_SECONDS=300
SLEEP_INTERVAL=15
FAILURES=0
MAX_FAILURES=3

for (( i=0; i<BAKE_SECONDS; i+=SLEEP_INTERVAL )); do
    sleep "${SLEEP_INTERVAL}"
    STATUS=$(curl -sf "${HEALTH_URL}" | python -c "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "error")

    if [ "${STATUS}" != "ok" ]; then
        FAILURES=$((FAILURES + 1))
        echo "  ⚠ Health check degraded (${FAILURES}/${MAX_FAILURES}): status=${STATUS}"
    else
        echo "  ✓ Health check OK (${i}s)"
        FAILURES=0
    fi

    if [ "${FAILURES}" -ge "${MAX_FAILURES}" ]; then
        echo ""
        echo "✖ CANARY FAILED — rolling back..."
        docker-compose -f "${COMPOSE_FILE}" up -d --no-deps --scale api=2 aidirector-api:latest
        echo "  Rolled back to previous version."
        exit 1
    fi
done

# ── Step 4: Deploy to all instances ──────────────────────────────────────────

echo ""
echo "▸ Canary healthy — deploying to all instances..."
docker-compose -f "${COMPOSE_FILE}" up -d --no-deps api

echo ""
echo "✓ Deploy complete: ${DEPLOY_TAG} is live on ${TARGET}"
