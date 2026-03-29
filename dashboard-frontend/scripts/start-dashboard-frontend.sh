#!/bin/sh
set -eu

READY_URL="${DASHBOARD_FRONTEND_WAIT_URL:-http://dashboard-backend:8000/dashboard/overview}"
WAIT_SECONDS="${DASHBOARD_FRONTEND_WAIT_SECONDS:-3}"

echo "dashboard-frontend: waiting for backend ${READY_URL}"

until node -e "fetch(process.argv[1]).then((r) => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))" "${READY_URL}" >/dev/null 2>&1; do
  echo "dashboard-frontend: backend unavailable, retrying in ${WAIT_SECONDS}s"
  sleep "${WAIT_SECONDS}"
done

echo "dashboard-frontend: backend is ready, starting preview server"
exec npm run preview -- --host 0.0.0.0 --port 5173
