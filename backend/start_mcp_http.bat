@echo off
setlocal

set "SCRIPT_DIR=%~dp0"

if "%MCP_HOST%"=="" set "MCP_HOST=127.0.0.1"
if "%MCP_PORT%"=="" set "MCP_PORT=1313"
if "%MCP_MOUNT_PATH%"=="" set "MCP_MOUNT_PATH=/mcp"

echo Starting CRD13 MCP HTTP server at http://%MCP_HOST%:%MCP_PORT%%MCP_MOUNT_PATH%

if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
  "%SCRIPT_DIR%venv\Scripts\python.exe" "%SCRIPT_DIR%start_mcp.py" --transport http --host "%MCP_HOST%" --port "%MCP_PORT%" --mount-path "%MCP_MOUNT_PATH%"
) else (
  python "%SCRIPT_DIR%start_mcp.py" --transport http --host "%MCP_HOST%" --port "%MCP_PORT%" --mount-path "%MCP_MOUNT_PATH%"
)

endlocal
