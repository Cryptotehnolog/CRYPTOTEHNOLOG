#!/bin/sh
set -eu

READY_URL="${DASHBOARD_BACKEND_START_WAIT_URL:-http://host.docker.internal:8080/api/status}"
WAIT_SECONDS="${DASHBOARD_BACKEND_START_WAIT_SECONDS:-3}"

echo "dashboard-backend: waiting for dependency ${READY_URL}"

until curl --fail --silent --show-error "${READY_URL}" >/dev/null 2>&1; do
  echo "dashboard-backend: dependency unavailable, retrying in ${WAIT_SECONDS}s"
  sleep "${WAIT_SECONDS}"
done

echo "dashboard-backend: dependency is ready, starting API"
exec python -m cryptotechnolog.dashboard
