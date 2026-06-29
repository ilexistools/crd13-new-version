$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $scriptDir "venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

$hostName = if ($env:MCP_HOST) { $env:MCP_HOST } else { "127.0.0.1" }
$port = if ($env:MCP_PORT) { $env:MCP_PORT } else { "1313" }
$mountPath = if ($env:MCP_MOUNT_PATH) { $env:MCP_MOUNT_PATH } else { "/mcp" }

Write-Host "Starting CRD13 MCP HTTP server at http://$hostName`:$port$mountPath"

& $python (Join-Path $scriptDir "start_mcp.py") `
    --transport http `
    --host $hostName `
    --port $port `
    --mount-path $mountPath
