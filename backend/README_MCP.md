# CRD13 MCP tools

This backend exposes a small MCP server for project-specific tools.

## Structure

- `start_mcp.py`: command-line entry point.
- `app/mcp_server.py`: server factory and transport selection.
- `app/tools/`: tool scripts. Each module can expose `register(mcp)` and add one or more `@mcp.tool()` functions.

## Install

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
```

## Run

```bash
venv/bin/python start_mcp.py --transport stdio
venv/bin/python start_mcp.py --transport sse --host 127.0.0.1 --port 8000
venv/bin/python start_mcp.py --transport http --host 127.0.0.1 --port 1313 --mount-path /mcp
```

`http` uses MCP streamable HTTP. Network transports bind to `127.0.0.1` by default.
Use `--mount-path` when a client expects a custom MCP endpoint path.

On Windows, start the HTTP MCP server with:

```powershell
.\start_mcp_http.ps1
```

or double-click/run:

```cmd
start_mcp_http.bat
```

On Linux/macOS, start the HTTP MCP server with:

```bash
./start_mcp_http.sh
```

Stop it with:

```bash
./stop_mcp_http.sh
```

The default HTTP endpoint is `http://127.0.0.1:1313/mcp`.

Environment variables are also supported:

- `MCP_TRANSPORT`: `stdio`, `sse`, or `http`.
- `MCP_HOST`: host for `sse` and `http`.
- `MCP_PORT`: port for `sse` and `http`.
- `MCP_MOUNT_PATH`: optional endpoint mount path for `sse` and `http`.

## Adding tools

Create a Python file in `app/tools`:

```python
from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def my_tool(value: str) -> dict[str, str]:
        """Describe what this tool does."""
        return {"value": value}
```

Files whose names start with `_` are ignored.

## Available tools

### `crd13_healthcheck`

Returns a simple health status for the CRD13 MCP server.

### `identify_commodities`

Identifies possible CRD13 commodities in a free-text passage and returns ranked
matches with confidence scores and evidence terms.

### `search_provisions`

Searches indexed CRD13 normative provisions for examples that are semantically
similar to a sentence. The tool first filters the SQLite RAG index by the
provided commodity list, then ranks only those candidates against the sentence
embedding.

Parameters:

- `commodities`: list of commodity names to use as the first-stage filter.
- `sentence`: text or sentence to compare with the filtered provisions.
- `top_k`: number of ranked examples to return, capped at `100`.
- `include_terms`: when `true`, the commodity filter also matches related
  commodity terms stored in the index.
- `match_all_commodities`: when `true`, candidates must match every supplied
  commodity/filter value; otherwise any supplied commodity can match.

The response includes `metadata.candidate_count`, `metadata.returned_count`, and
ranked `results` with score, score percentage, sentence, document id, section,
page range, modality, function, commodities, commodity terms, and original
metadata.

## Configure MCP in Codex

Add the CRD13 MCP server to the Codex config file:

- Windows: `C:\Users\<usuario>\.codex\config.toml`
- Linux/macOS: `~/.codex/config.toml`

For this workspace on Windows, use:

```toml
[mcp_servers.crd13_tools]
command = 'C:\Users\LOPES\Documents\workspace\crd13\crd13-new-version\backend\venv\Scripts\python.exe'
args = [
  'C:\Users\LOPES\Documents\workspace\crd13\crd13-new-version\backend\start_mcp.py',
  '--transport',
  'stdio',
]
cwd = 'C:\Users\LOPES\Documents\workspace\crd13\crd13-new-version\backend'
startup_timeout_sec = 30
tool_timeout_sec = 60
enabled = true

[mcp_servers.crd13_tools.env]
PYTHONUNBUFFERED = '1'
```

If the project is cloned in another folder, update `command`, the first item in
`args`, and `cwd` to the absolute paths for that folder.

After saving `config.toml`, restart Codex or open a new Codex session so the MCP
server is loaded. The server uses `stdio`, so Codex starts it automatically when
the configured tools are needed.

Linux/macOS example:

```toml
[mcp_servers.crd13-tools]
command = "/Users/joselopes/Workspace/2026/CRD13/crd13-new-version/backend/venv/bin/python"
args = ["/Users/joselopes/Workspace/2026/CRD13/crd13-new-version/backend/start_mcp.py", "--transport", "stdio"]
cwd = "/Users/joselopes/Workspace/2026/CRD13/crd13-new-version/backend"
startup_timeout_sec = 10
tool_timeout_sec = 60
```
