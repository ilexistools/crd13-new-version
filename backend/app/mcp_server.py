from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from app.tools import register_tools


Transport = Literal["stdio", "sse", "http"]


def build_mcp(host: str | None = None, port: int | None = None) -> FastMCP:
    """Create and populate the MCP server."""
    kwargs: dict[str, Any] = {
        "name": "crd13-tools",
        "instructions": (
            "Use these tools for CRD13 backend helper operations. "
            "Tool scripts live in app/tools and are registered at startup."
        ),
    }
    if host is not None:
        kwargs["host"] = host
    if port is not None:
        kwargs["port"] = port

    mcp = FastMCP(**kwargs)
    register_tools(mcp)
    return mcp


def run_server(
    transport: Transport = "stdio",
    host: str | None = None,
    port: int | None = None,
    mount_path: str | None = None,
) -> None:
    """Run the MCP server using one of the supported transports."""
    mcp = build_mcp(host=host, port=port)
    fastmcp_transport = "streamable-http" if transport == "http" else transport
    mcp.run(transport=fastmcp_transport, mount_path=mount_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CRD13 MCP tools server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "http"),
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport to use. 'http' maps to MCP streamable HTTP.",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host for network transports.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Port for network transports.",
    )
    parser.add_argument(
        "--mount-path",
        default=os.getenv("MCP_MOUNT_PATH"),
        help="Optional mount path for SSE or streamable HTTP transports.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    host = args.host if args.transport in {"sse", "http"} else None
    port = args.port if args.transport in {"sse", "http"} else None
    try:
        run_server(transport=args.transport, host=host, port=port, mount_path=args.mount_path)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


if __name__ == "__main__":
    main()
