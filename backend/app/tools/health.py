from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def crd13_healthcheck() -> dict[str, Any]:
        """Return a simple health status for the CRD13 MCP server."""
        return {
            "status": "ok",
            "service": "crd13-tools",
        }
