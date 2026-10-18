"""Servidor A2A que publica el supervisor centralizado de Parachute."""
from contextlib import asynccontextmanager
import logging
import time
from uuid import uuid4

import uvicorn
from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill, Role
from starlette.applications import Starlette

from parachute_agents import respond, mcp_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("parachute.a2a")

HOST = "0.0.0.0"
PORT = 8100
PUBLIC_URL = f"http://localhost:{PORT}/"


class ParachuteExecutor(AgentExecutor):
    """Adapta los mensajes A2A al supervisor multiagente de la HDT."""

    def __init__(self) -> None:
        self._histories: dict[str, list] = {}

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        user_text = "\n".join(
            part.text for part in message.parts if getattr(part, "text", None)
        ).strip()
        if not user_text:
            await event_queue.enqueue_event(
                new_text_message("Envía una solicitud como texto.", role=Role.ROLE_AGENT)
            )
            return

        context_id = context.context_id or str(uuid4())
        started = time.perf_counter()
        logger.info("A2A request started: context=%s chars=%d", context_id, len(user_text))
        try:
            output, history = await respond(user_text, self._histories.get(context_id, []))
        except Exception:
            logger.exception("A2A request failed: context=%s", context_id)
            raise
        self._histories[context_id] = history
        logger.info(
            "A2A request completed: context=%s chars=%d (%.0f ms)",
            context_id,
            len(output),
            (time.perf_counter() - started) * 1000,
        )
        await event_queue.enqueue_event(
            new_text_message(output, role=Role.ROLE_AGENT)
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """No hay una operación cancelable después de iniciado Runner.run."""
        return None


agent_card = AgentCard(
    name="Parachute Central Supervisor",
    description="Supervisor multiagente de Parachute S.A. para FAQs, clima y citas seguras.",
    version="1.0.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(streaming=False),
    supported_interfaces=[
        AgentInterface(protocol_binding="JSONRPC", url=PUBLIC_URL),
    ],
    skills=[
        AgentSkill(
            id="preguntas-frecuentes",
            name="Preguntas frecuentes",
            description="Responde preguntas de servicios, políticas, equipo y seguridad usando las FAQs oficiales.",
            tags=["parachute", "faq", "informacion"],
            examples=["¿Qué equipo necesito para saltar?"],
            input_modes=["text/plain"],
            output_modes=["text/plain"],
        ),
        AgentSkill(
            id="evaluacion-meteorologica",
            name="Evaluación meteorológica",
            description="Consulta el pronóstico y evalúa las condiciones de seguridad para una fecha.",
            tags=["clima", "weather", "seguridad"],
            examples=["Consulta el clima para 2026-10-20"],
            input_modes=["text/plain"],
            output_modes=["text/plain"],
        ),
        AgentSkill(
            id="calendarizacion-segura",
            name="Calendarización segura",
            description="Intenta calendarizar una cita, sujeto a la validación meteorológica determinista.",
            tags=["citas", "reservas", "appointments"],
            examples=["Quiero calendarizar una cita el 2026-10-20"],
            input_modes=["text/plain"],
            output_modes=["text/plain"],
        ),
    ],
)

request_handler = DefaultRequestHandler(
    agent_executor=ParachuteExecutor(),
    task_store=InMemoryTaskStore(),
    agent_card=agent_card,
)


@asynccontextmanager
async def lifespan(app: Starlette):
    """Mantiene conectado el cliente MCP mientras atiende solicitudes A2A."""
    async with mcp_server:
        yield


app = Starlette(
    routes=[
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(request_handler, rpc_url="/"),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
