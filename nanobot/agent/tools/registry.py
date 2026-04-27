"""Tool registry for dynamic tool management."""

from typing import Any

from nanobot.agent.tools.base import Tool


class ToolRegistry:
    """
    Registry for agent tools.
    
    Allows dynamic registration and execution of tools.
    """
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_schema() for tool in self._tools.values()]

    def get_definitions_filtered(self, names: list[str]) -> list[dict[str, Any]]:
        """Get tool definitions for a subset of tools by name.

        Args:
            names: List of tool names to include.

        Returns:
            Tool definitions in OpenAI format, filtered to only the given names.
        """
        name_set = set(names)
        return [tool.to_schema() for name, tool in self._tools.items() if name in name_set]
    
    async def execute(self, name: str, params: dict[str, Any]) -> "str | list[dict[str, Any]]":
        """
        Execute a tool by name with given parameters.
        
        Args:
            name: Tool name.
            params: Tool parameters.
        
        Returns:
            Tool execution result as string, or multimodal content list (with images).
        
        Raises:
            KeyError: If tool not found.
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        try:
            errors = tool.validate_params(params)
            if errors:
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
