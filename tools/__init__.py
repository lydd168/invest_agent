"""Tool wrappers for external data services."""

from . import yfinance_client

# Backwards compatibility for older imports that referenced the MCP module name.
mcp_yfinance = yfinance_client

__all__ = [
	"yfinance_client",
	"mcp_yfinance",
]