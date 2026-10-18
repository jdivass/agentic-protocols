"""Orquestador multiagente central de Parachute, usado por el servidor A2A."""
import os

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

from shared.parachute import agent_model, agent_model_settings, _apply_domain_guard

MODEL = agent_model()
SETTINGS = agent_model_settings()

mcp_server = MCPServerStreamableHttp(
    params={"url": os.getenv("PARACHUTE_MCP_URL", "http://localhost:8000/mcp")},
    name="Parachute MCP (Streamable HTTP)",
    cache_tools_list=True,
    client_session_timeout_seconds=float(os.getenv("PARACHUTE_MCP_TIMEOUT_SECONDS", "180")),
)

weather_worker = Agent(
    name="WeatherWorker",
    instructions="Usa consultar_clima para evaluar una fecha. Nunca inventes datos.",
    mcp_servers=[mcp_server],
    model=MODEL,
    model_settings=SETTINGS,
)
faq_worker = Agent(
    name="FAQWorker",
    instructions=("Responde exclusivamente usando consultar_faq. Si no hay coincidencia, "
                  "di que no existe información en las FAQs. No uses conocimiento general."),
    mcp_servers=[mcp_server],
    model=MODEL,
    model_settings=SETTINGS,
)
calendar_worker = Agent(
    name="CalendarWorker",
    instructions=("Usa calendarizar_cita. La herramienta vuelve a consultar el clima y "
                  "rechaza condiciones inseguras; nunca afirmes éxito si scheduled no es true."),
    mcp_servers=[mcp_server],
    model=MODEL,
    model_settings=SETTINGS,
)
supervisor = Agent(
    name="SupervisorCentral",
    instructions=(
        "Eres el supervisor de Parachute S.A. Decide qué worker usar. Para una cita, "
        "consulta primero el clima y luego delega en CalendarWorker. Nunca autorices "
        "condiciones NO SEGURO / PROHIBIDO. Solo informa que se calendarizó si la "
        "herramienta devuelve scheduled=true; la cita sigue siendo tentativa hasta "
        "confirmación del instructor."
    ),
    model=MODEL,
    model_settings=SETTINGS,
    tools=[
        weather_worker.as_tool("consultar_clima", "Consulta clima y aptitud para una fecha."),
        faq_worker.as_tool("consultar_faq", "Consulta las preguntas frecuentes."),
        calendar_worker.as_tool("calendarizar_cita", "Calendariza una cita con validación meteorológica."),
    ],
)


async def respond(user_text: str, history: list | None = None) -> tuple[str, list]:
    """Ejecuta el supervisor y devuelve la respuesta junto al historial actualizado."""
    response = await Runner.run(supervisor, (history or []) + [{"role": "user", "content": user_text}])
    output = response.final_output or ""
    output = _apply_domain_guard(user_text, output)
    return output, response.to_input_list()
