"""Servidor MCP de Parachute usando el transporte Streamable HTTP."""
import logging
import time

from mcp.server.fastmcp import FastMCP

from shared.parachute import (
    CLOUD_COVER_MARGINAL_PCT,
    CLOUD_COVER_UNSAFE_PCT,
    FAQ_PATH,
    MAX_FORECAST_DAYS,
    PRECIPITATION_UNSAFE_MM,
    WIND_GUST_UNSAFE_KMH,
    WIND_SPEED_MARGINAL_KMH,
    WIND_SPEED_UNSAFE_KMH,
    faq_tool,
    schedule_tool,
    weather_tool,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("parachute.mcp")

mcp = FastMCP(
    "Parachute S. A.",
    instructions=(
        "Herramientas y contexto de Parachute S.A. Consulta el clima antes de "
        "calendarizar; la herramienta de citas vuelve a comprobar las condiciones."
    ),
    host="0.0.0.0",
    port=8000,
)


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


@mcp.resource(
    "parachute://company/profile",
    name="Perfil de Parachute S.A.",
    description="Descripción de la empresa y del servicio que cubre este asistente.",
    mime_type="text/markdown",
)
def company_profile() -> str:
    """Expone contexto estable de la empresa como recurso MCP de solo lectura."""
    return (
        "# Parachute S.A.\n\n"
        "Empresa de paracaidismo en Guatemala. Este asistente apoya consultas sobre "
        "servicios, seguridad, clima y calendarización de citas. La información "
        "operativa específica se consulta en las FAQs oficiales y con las herramientas "
        "de clima y calendarización. Una cita queda tentativa hasta confirmación del instructor."
    )


@mcp.resource(
    "parachute://safety/flight-rules",
    name="Reglas de seguridad meteorológica",
    description="Umbrales deterministas que se aplican antes de calendarizar un salto.",
    mime_type="text/markdown",
)
def flight_safety_rules() -> str:
    """Publica las mismas constantes que aplica la evaluación meteorológica."""
    return (
        "# Reglas meteorológicas de Parachute S.A.\n\n"
        f"- Pronóstico disponible: {MAX_FORECAST_DAYS} días contando hoy.\n"
        f"- Viento superficial: marginal desde {WIND_SPEED_MARGINAL_KMH} km/h; "
        f"inseguro por encima de {WIND_SPEED_UNSAFE_KMH} km/h.\n"
        f"- Ráfagas: inseguro por encima de {WIND_GUST_UNSAFE_KMH} km/h.\n"
        f"- Precipitación: inseguro por encima de {PRECIPITATION_UNSAFE_MM} mm.\n"
        f"- Nubes: marginal desde {CLOUD_COVER_MARGINAL_PCT}%; "
        f"inseguro por encima de {CLOUD_COVER_UNSAFE_PCT}%.\n"
        "Solo se calendariza con decisión IDEAL o MARGINAL. La herramienta de "
        "calendarización vuelve a consultar el clima antes de guardar."
    )


@mcp.resource(
    "parachute://faqs/corpus",
    name="Corpus oficial de FAQs",
    description="Corpus de preguntas frecuentes de Parachute S.A. usado por la integración HDT4.",
    mime_type="text/plain",
)
def faq_corpus() -> str:
    """Publica el corpus como recurso MCP de solo lectura."""
    return FAQ_PATH.read_text(encoding="utf-8")


@mcp.prompt(
    name="responder_faq",
    title="Responder una pregunta frecuente",
    description="Prepara una consulta acotada a la base oficial de FAQs de Parachute.",
)
def faq_prompt(question: str) -> str:
    """Plantilla para resolver consultas de la empresa usando sus FAQs."""
    return (
        "Responde en español y utiliza consultar_faq para fundamentar la respuesta. "
        "No inventes políticas ni respondas con conocimiento general. "
        f"\n\nPregunta del usuario: {question}"
    )


@mcp.prompt(
    name="evaluar_clima",
    title="Evaluar clima para una fecha",
    description="Consulta y explica la aptitud meteorológica de una fecha concreta.",
)
def weather_prompt(date: str) -> str:
    """Plantilla que orienta una evaluación meteorológica mediante la herramienta."""
    return (
        "Usa consultar_clima para la fecha indicada. Explica la decisión y sus razones. "
        "No inventes ni reutilices datos de otro reporte.\n\n"
        f"Fecha solicitada: {date}"
    )


@mcp.prompt(
    name="solicitar_cita_segura",
    title="Solicitar una cita segura",
    description="Guía la comprobación climática y la calendarización de una cita.",
)
def booking_prompt(date: str) -> str:
    """Plantilla para consultar el clima antes de intentar calendarizar."""
    return (
        "Consulta primero el clima y luego usa calendarizar_cita, que realiza su "
        "propia validación. Solo informa éxito si scheduled=true; aclara que la cita "
        "queda tentativa hasta confirmación del instructor.\n\n"
        f"Fecha solicitada: {date}"
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
