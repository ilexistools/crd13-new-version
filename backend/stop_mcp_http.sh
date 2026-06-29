#!/usr/bin/env bash
set -euo pipefail

MCP_PORT="${MCP_PORT:-1313}"

PIDS="$(lsof -tiTCP:"$MCP_PORT" -sTCP:LISTEN 2>/dev/null || true)"

if [[ -z "$PIDS" ]] && command -v pgrep >/dev/null 2>&1; then
  PIDS="$(pgrep -f "start_mcp.py .*--transport http .*--port ${MCP_PORT}" 2>/dev/null || true)"
fi

if [[ -z "$PIDS" ]]; then
  echo "No CRD13 MCP HTTP server found on port ${MCP_PORT}."
  exit 0
fi

echo "Stopping CRD13 MCP HTTP server on port ${MCP_PORT}: ${PIDS//$'\n'/ }"
kill $PIDS

for _ in {1..20}; do
  STILL_RUNNING=""
  for PID in $PIDS; do
    if kill -0 "$PID" 2>/dev/null; then
      STILL_RUNNING="$STILL_RUNNING $PID"
    fi
  done

  if [[ -z "$STILL_RUNNING" ]]; then
    echo "Stopped."
    exit 0
  fi

  sleep 0.25
done

echo "Processes did not stop cleanly; forcing:${STILL_RUNNING}"
kill -9 $STILL_RUNNING 2>/dev/null || true
echo "Stopped."
