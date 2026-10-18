"""Servidor MCP de Parachute usando el transporte Streamable HTTP."""
import logging
import time

from mcp.server.fastmcp import FastMCP

from shared.parachute import faq_tool, schedule_tool, weather_tool

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("parachute.mcp")


def _run_tool(name: str, operation) -> str:
    started = time.perf_counter()
    logger.info("MCP tool started: %s", name)
    try:
        result = operation()
    except Exception:
        logger.exception("MCP tool failed: %s", name)
        raise
    logger.info(
        "MCP tool completed: %s (%.0f ms)",
        name,
        (time.perf_counter() - started) * 1000,
    )
    return result

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
    return _run_tool("consultar_clima", lambda: weather_tool(date))


@mcp.tool()
def consultar_faq(question: str) -> str:
    """Busca una respuesta en la base de FAQs de Parachute."""
    return _run_tool("consultar_faq", lambda: faq_tool(question))


@mcp.tool()
def calendarizar_cita(date: str) -> str:
    """Intenta calendarizar. Vuelve a validar el clima antes de guardar."""
    return _run_tool("calendarizar_cita", lambda: schedule_tool(date))


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
