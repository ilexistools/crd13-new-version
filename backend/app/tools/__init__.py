from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from types import ModuleType
from typing import Protocol

from mcp.server.fastmcp import FastMCP


class ToolModule(Protocol):
    register: Callable[[FastMCP], None]


def _iter_tool_modules() -> list[ModuleType]:
    modules: list[ModuleType] = []
    package_name = __name__
    package_path = __path__

    for module_info in pkgutil.iter_modules(package_path):
        if module_info.name.startswith("_"):
            continue
        modules.append(importlib.import_module(f"{package_name}.{module_info.name}"))

    return modules


def register_tools(mcp: FastMCP) -> None:
    """Register every tool module that exposes register(mcp)."""
    for module in _iter_tool_modules():
        register = getattr(module, "register", None)
        if register is None:
            continue
        register(mcp)
