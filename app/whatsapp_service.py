"""Thin client around the WhatsApp Cloud API (Graph API)."""
from __future__ import annotations

import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    if not settings.meta_api_key:
        raise RuntimeError("META_API_KEY is not set; cannot call the Graph API.")
    if not settings.graph_meta_id:
        raise RuntimeError("GRAPH_META_ID is not set; cannot call the Graph API.")

    return {
        "Authorization": f"Bearer {settings.meta_api_key}",
        "Content-Type": "application/json",
    }


def _post(payload: dict) -> dict:
    url = f"{settings.graph_base_url}/messages"
    response = requests.post(url, json=payload, headers=_headers(), timeout=15)
    if not response.ok:
        logger.error("WhatsApp API error %s: %s", response.status_code, response.text)
    response.raise_for_status()
    return response.json()


def send_text_message(to: str, body: str, *, preview_url: bool = False) -> dict:
    """Send a free-form text message.

    Note: outside the 24h customer-service window you must use a template.
    """
    return _post(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": body},
        }
    )


def send_template_message(
    to: str,
    template_name: str,
    language: str | None = None,
) -> dict:
    """Send a pre-approved template message (works outside the 24h window)."""
    return _post(
        {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language or settings.default_language},
            },
        }
    )


def mark_message_as_read(message_id: str) -> dict:
    """Mark an incoming message as read so the user sees the blue checks."""
    url = f"{settings.graph_base_url}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }
    response = requests.post(url, json=payload, headers=_headers(), timeout=15)
    if not response.ok:
        logger.warning(
            "Could not mark message %s as read: %s", message_id, response.text
        )
    return response.json() if response.content else {}
