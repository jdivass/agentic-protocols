"""Supervisor centralizado conectado al servidor MCP de Parachute."""
import asyncio
import os

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp

from shared.parachute import agent_model, agent_model_settings, _apply_domain_guard

MODEL = agent_model()
SETTINGS = agent_model_settings()
MCP_URL = os.getenv("PARACHUTE_MCP_URL", "http://localhost:8000/mcp")

mcp_server = MCPServerStreamableHttp(
    params={"url": MCP_URL},
    name="Parachute MCP (Streamable HTTP)",
    cache_tools_list=True,
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


async def _respond(user_text: str, history: list | None = None) -> tuple[str, list]:
    response = await Runner.run(supervisor, (history or []) + [{"role": "user", "content": user_text}])
    output = response.final_output or ""
    # El servidor valida toda operación de cita. Esta guarda mantiene las
    # respuestas fuera del dominio respaldadas exclusivamente por las FAQs.
    output = _apply_domain_guard(user_text, output)
    return output, response.to_input_list()


async def _main() -> None:
    history = []
    async with mcp_server:
        while True:
            try:
                user_text = input("Tú: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("Sesión finalizada.")
                return
            if user_text.lower() in {"salir", "exit", "quit"}:
                print("Sesión finalizada.")
                return
            if not user_text:
                continue
            try:
                output, history = await _respond(user_text, history)
                print(f"Agente: {output}")
            except Exception as exc:
                print(f"Agente: No se pudo completar la solicitud: {exc}")


if __name__ == "__main__":
    asyncio.run(_main())
