# whatsapp-connection

# ---> W.I.P <--- 

API base en FastAPI para enviar y recibir mensajes de WhatsApp usando la
[WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api).

Por ahora el bot responde mensajes dummy ("Hola", "pong", echo del texto),
pero el esqueleto ya cubre verificacion de webhook, parseo del payload real,
envio de respuestas y marca de leido.

## Estructura

```
app/
├── config.py           # carga y valida variables de entorno
├── whatsapp_service.py # cliente HTTP de la Graph API (send_text, template, read)
├── handlers.py         # logica del bot (respuesta dummy, facil de extender)
├── main.py             # FastAPI app + endpoints del webhook
└── testDummy.py        # script manual para probar envios salientes
```

## Instalacion

```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
# venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

## Variables de entorno

Copia el ejemplo y rellena con tus credenciales de Meta:

```bash
cp .env.example .env
```

| Variable | Para que sirve |
| --- | --- |
| `VERIFY_TOKEN` | String que tu eliges. Debe ser el mismo que pongas en Meta -> Webhooks. |
| `META_API_KEY` | Access token de la WhatsApp Cloud API. |
| `GRAPH_META_ID` | Phone Number ID asignado por Meta (no es el numero, es el ID). |
| `GRAPH_API_VERSION` | Version de la Graph API (default `v25.0`). |
| `DEFAULT_TEMPLATE_LANGUAGE` | Idioma por defecto para templates (default `es_US`). |

## Como correr

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Docs interactivas: http://127.0.0.1:8000/docs
- Webhook: `GET/POST http://127.0.0.1:8000/webhook/whatsapp`

## Exponer el webhook a internet (Meta lo necesita)

Meta solo acepta URLs HTTPS publicas. En local lo mas comodo es
[ngrok](https://ngrok.com/):

```bash
ngrok http 8000
```

Eso te dara una URL tipo `https://xxxx-yyy.ngrok-free.app`. La URL de tu
webhook seria `https://xxxx-yyy.ngrok-free.app/webhook/whatsapp`.

## Configurar el webhook en Meta Business

1. Entra a [developers.facebook.com](https://developers.facebook.com/) -> tu
   app -> **WhatsApp** -> **Configuration**.
2. En **Webhook** -> **Edit**:
   - **Callback URL**: `https://<tu-ngrok>/webhook/whatsapp`
   - **Verify Token**: el mismo valor de `VERIFY_TOKEN` en tu `.env`.
3. Meta hara un `GET` al endpoint y debe responder con el `hub.challenge`.
4. Suscribete a los campos `messages` (y opcionalmente `message_status`).
5. En **Phone numbers** agrega tu numero de pruebas como destinatario
   permitido mientras la app este en modo desarrollo.

## Probar envio saliente desde la terminal

```bash
# Template (funciona siempre, recomendable para el primer test)
python -m app.testDummy 50670959499

# Texto libre (solo dentro de la ventana de 24h tras un mensaje del usuario)
python -m app.testDummy 50670959499 text
```

## Flujo de respuesta

1. El usuario manda un mensaje al numero de WhatsApp Business.
2. Meta hace `POST /webhook/whatsapp` con el payload.
3. `main.py` parsea el mensaje, llama a `handlers.generate_reply(...)`.
4. `whatsapp_service.send_text_message(...)` envia la respuesta de vuelta.
5. `mark_message_as_read(...)` marca el mensaje original como leido.

Cuando quieras dejar de responder cosas dummy, edita `app/handlers.py`:
ahi es donde conectaras tu logica real, una DB, un LLM, etc.
