"""Tool type only (keeps ``integrations`` / ``automations`` imports cycle-free)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


@dataclass
class ToolConfig:
    """Configuration for an agent tool."""
    name: str
    description: str
    input_schema: dict[str, Any]
    categories: list[str] = field(default_factory=lambda: ["general"])


class Tool:
    """Represents an agent tool."""

    def __init__(
        self,
        config: ToolConfig,
        handler: Callable[..., Coroutine[Any, Any, str]],
    ):
        self.name = config.name
        self.description = config.description
        self.input_schema = config.input_schema
        self.handler = handler
        self.categories = config.categories

    def to_anthropic_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def to_compact_prompt(self) -> str:
        """Ultra-compact prompt format for small models."""
        lines = [f"{self.name}: {self.description}"]
        props = self.input_schema.get("properties", {})
        req = self.input_schema.get("required", [])
        params = []
        for pname, pinfo in props.items():
            pdesc = pinfo.get("description", "")
            ptype = pinfo.get("type", "any")
            r = "*" if pname in req else ""
            params.append(f"  {pname}{r} ({ptype}): {pdesc}")
        if params:
            lines.extend(params)
        return "\n".join(lines)

    async def run(self, **kwargs) -> str:
        try:
            result = await self.handler(**kwargs)
            return result
        except Exception as e:
            return f"Error: {e}"
