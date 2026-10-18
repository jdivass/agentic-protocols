"""Cliente A2A de terminal para conversar con el supervisor Parachute."""
import argparse
import asyncio
import os
from uuid import uuid4

import httpx
from a2a.client import ClientConfig, create_client
from a2a.helpers import get_message_text
from a2a.types import Message, Part, Role, SendMessageRequest

A2A_URL = os.getenv("PARACHUTE_A2A_URL", "http://localhost:8100/")
CLIENT_TIMEOUT_SECONDS = float(os.getenv("PARACHUTE_A2A_TIMEOUT_SECONDS", "180"))


async def _send(client, text: str, context_id: str) -> str:
    message = Message(
        role=Role.ROLE_USER,
        message_id=str(uuid4()),
        context_id=context_id,
        parts=[Part(text=text)],
    )
    response_text = ""
    async for event in client.send_message(SendMessageRequest(message=message)):
        if event.HasField("message"):
            response_text = get_message_text(event.message)
        elif event.HasField("artifact_update"):
            response_text = "\n".join(
                part.text for part in event.artifact_update.artifact.parts
                if getattr(part, "text", None)
            )
    return response_text


async def _main(query: str | None) -> None:
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(CLIENT_TIMEOUT_SECONDS, connect=min(10.0, CLIENT_TIMEOUT_SECONDS))
    )
    try:
        client = await create_client(
            A2A_URL,
            client_config=ClientConfig(httpx_client=http_client),
        )
    except Exception as exc:
        await http_client.aclose()
        print(f"No se pudo conectar al servidor A2A en {A2A_URL}: {exc}")
        return
    context_id = str(uuid4())
    try:
        if query:
            print(await _send(client, query, context_id))
            return

        print(f"Conectado al agente A2A en {A2A_URL}. Escribe 'salir' para terminar.")
        while True:
            try:
                text = await asyncio.to_thread(input, "Tú: ")
            except (EOFError, KeyboardInterrupt):
                break
            if text.strip().lower() in {"salir", "exit", "quit"}:
                break
            if not text.strip():
                continue
            try:
                print(f"Agente: {await _send(client, text.strip(), context_id)}")
            except Exception as exc:
                print(f"No se pudo completar la solicitud A2A: {exc}")
    finally:
        await client.close()
        await http_client.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cliente A2A de Parachute")
    parser.add_argument("query", nargs="*", help="Consulta única; omítela para iniciar el chat")
    args = parser.parse_args()
    asyncio.run(_main(" ".join(args.query).strip() or None))
