#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON="python3"
  else
    PYTHON="python"
  fi
fi

MCP_HOST="${MCP_HOST:-127.0.0.1}"
MCP_PORT="${MCP_PORT:-1313}"
MCP_MOUNT_PATH="${MCP_MOUNT_PATH:-/mcp}"

echo "Starting CRD13 MCP HTTP server at http://${MCP_HOST}:${MCP_PORT}${MCP_MOUNT_PATH}"

exec "$PYTHON" "$SCRIPT_DIR/start_mcp.py" \
  --transport http \
  --host "$MCP_HOST" \
  --port "$MCP_PORT" \
  --mount-path "$MCP_MOUNT_PATH"
