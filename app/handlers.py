"""Business logic for incoming messages.

Right now this is just a dummy auto-responder. Replace `generate_reply`
(or add new branches) when you start plugging in real logic, an LLM, a DB, etc.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingMessage:
    wa_id: str           # sender phone number (E.164, no +)
    name: str | None     # WhatsApp profile name, if available
    message_id: str      # wamid.* identifier
    text: str            # message body (empty for non-text messages)
    type: str            # "text", "image", "audio", "interactive", ...


_GREETINGS = {"hola", "hi", "hello", "buenas", "hey", "ola"}


def generate_reply(message: IncomingMessage) -> str:
    """Return the text we want to send back. Dummy version for now."""
    if message.type != "text":
        return (
            "Por ahora solo puedo responder mensajes de texto. "
            "Pronto soportare imagenes y audios."
        )

    normalized = message.text.strip().lower()

    if not normalized:
        return "Hola! Mandame un mensaje y te respondo."

    if normalized in _GREETINGS:
        nice_name = f", {message.name}" if message.name else ""
        return f"Hola{nice_name}! Soy un bot dummy. Como te puedo ayudar?"

    if normalized in {"ping", "test"}:
        return "pong"

    return f"Recibi tu mensaje: \"{message.text}\". (respuesta dummy)"
