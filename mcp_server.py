"""Servidor MCP de Parachute usando el transporte Streamable HTTP."""
from mcp.server.fastmcp import FastMCP

from shared.parachute import faq_tool, schedule_tool, weather_tool

mcp = FastMCP(
    "Parachute S. A.",
    instructions=(
        "Herramientas de Parachute S.A. Consulta el clima antes de calendarizar. "
        "schedule_tool vuelve a consultar el clima y rechaza condiciones inseguras."
    ),
    host="0.0.0.0",
    port=8000,
)


@mcp.tool()
def consultar_clima(date: str) -> str:
    """Consulta el pronóstico y evalúa seguridad. Fecha en formato YYYY-MM-DD."""
    return weather_tool(date)


@mcp.tool()
def consultar_faq(question: str) -> str:
    """Busca una respuesta en la base de FAQs de Parachute."""
    return faq_tool(question)


@mcp.tool()
def calendarizar_cita(date: str) -> str:
    """Intenta calendarizar. Vuelve a validar el clima antes de guardar."""
    return schedule_tool(date)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
