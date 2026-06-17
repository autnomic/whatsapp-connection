"""Quick manual test for outbound messages.

Run from the repo root with:

    python -m app.testDummy <phone_number_e164_without_plus>

Example:
    python -m app.testDummy 50670959499

Notes:
- To send a free-form text the recipient must have written you within the last
  24h. Otherwise Meta will only accept a template message.
- For first-time tests, prefer `send_template_message` with the pre-approved
  "hello_world" template that comes with every test number.
"""
from __future__ import annotations

import sys

from app.whatsapp_service import send_template_message, send_text_message


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m app.testDummy <phone_number>")
        sys.exit(1)

    number = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "template"

    if mode == "text":
        result = send_text_message(number, "Hola desde mi API!")
    else:
        result = send_template_message(number, "hello_world", language="en_US")

    print("Response:", result)


if __name__ == "__main__":
    main()
