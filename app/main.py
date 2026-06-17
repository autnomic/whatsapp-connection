"""FastAPI entrypoint exposing the WhatsApp webhook."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.config import settings
from app.handlers import IncomingMessage, generate_reply
from app.whatsapp_service import mark_message_as_read, send_text_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="WhatsApp Connection API", version="0.1.0")


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Webhook bot running"}


# ---------------------------------------------------------------------------
# Webhook verification (Meta calls this with GET when you save the webhook URL)
# Docs: https://developers.facebook.com/docs/graph-api/webhooks/getting-started
# ---------------------------------------------------------------------------
@app.get("/webhook/whatsapp")
def verify_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> PlainTextResponse:
    if mode == "subscribe" and token == settings.verify_token and challenge is not None:
        logger.info("Webhook verified successfully.")
        return PlainTextResponse(content=challenge)

    logger.warning("Webhook verification failed (mode=%s).", mode)
    raise HTTPException(status_code=403, detail="Invalid verify token")


# ---------------------------------------------------------------------------
# Incoming events (messages + statuses)
# ---------------------------------------------------------------------------
@app.post("/webhook/whatsapp")
async def receive_event(request: Request) -> dict[str, Any]:
    payload = await request.json()
    logger.info("Webhook payload: %s", payload)

    replies: list[dict[str, Any]] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            for status in value.get("statuses", []):
                logger.info(
                    "Status update: id=%s status=%s",
                    status.get("id"),
                    status.get("status"),
                )

            contacts = value.get("contacts", []) or []
            contact_by_wa_id = {c.get("wa_id"): c for c in contacts}

            for raw_message in value.get("messages", []) or []:
                incoming = _parse_message(raw_message, contact_by_wa_id)
                if incoming is None:
                    continue

                reply_text = generate_reply(incoming)
                logger.info("Reply to %s: %s", incoming.wa_id, reply_text)

                try:
                    mark_message_as_read(incoming.message_id)
                    api_response = send_text_message(incoming.wa_id, reply_text)
                    replies.append({"to": incoming.wa_id, "api_response": api_response})
                except Exception:  # noqa: BLE001 - we never want to 500 to Meta
                    logger.exception("Failed to reply to %s", incoming.wa_id)

    return {"status": "received", "replies": replies}


def _parse_message(
    raw: dict[str, Any],
    contact_by_wa_id: dict[str, dict[str, Any]],
) -> IncomingMessage | None:
    wa_id = raw.get("from")
    message_id = raw.get("id")
    msg_type = raw.get("type", "unknown")
    if not wa_id or not message_id:
        return None

    text = ""
    if msg_type == "text":
        text = (raw.get("text") or {}).get("body", "")
    elif msg_type == "button":
        text = (raw.get("button") or {}).get("text", "")
    elif msg_type == "interactive":
        interactive = raw.get("interactive") or {}
        if interactive.get("type") == "button_reply":
            text = (interactive.get("button_reply") or {}).get("title", "")
        elif interactive.get("type") == "list_reply":
            text = (interactive.get("list_reply") or {}).get("title", "")

    contact = contact_by_wa_id.get(wa_id) or {}
    name = (contact.get("profile") or {}).get("name")

    return IncomingMessage(
        wa_id=wa_id,
        name=name,
        message_id=message_id,
        text=text,
        type=msg_type,
    )
