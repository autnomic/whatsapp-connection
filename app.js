// Import Express.js
const express = require('express');

// Create an Express app
const app = express();

// Middleware to parse JSON bodies
app.use(express.json());

// Config from environment variables
const port = process.env.PORT || 3000;
const verifyToken = process.env.VERIFY_TOKEN;
const accessToken = process.env.ACCESS_TOKEN || process.env.META_API_KEY;
const graphApiVersion = process.env.GRAPH_API_VERSION || 'v25.0';

if (!verifyToken) {
  console.warn('VERIFY_TOKEN is not set; webhook verification will fail.');
}
if (!accessToken) {
  console.warn('ACCESS_TOKEN/META_API_KEY is not set; outbound messages will fail.');
}

// In-memory dedupe so Meta retries (same message id) don't echo twice.
// Bounded so the process memory stays flat over long runs.
const processedMessageIds = new Set();
const MAX_PROCESSED_IDS = 1000;
function rememberMessageId(id) {
  if (processedMessageIds.size >= MAX_PROCESSED_IDS) {
    const oldest = processedMessageIds.values().next().value;
    processedMessageIds.delete(oldest);
  }
  processedMessageIds.add(id);
}

// Convert one incoming WhatsApp message into a human-readable string.
function prettifyMessage(message, contact) {
  const name = contact?.profile?.name ?? 'Unknown';
  const waId = contact?.wa_id ?? message.from;
  const when = new Date(Number(message.timestamp) * 1000).toISOString();
  const type = message.type;

  let body;
  switch (type) {
    case 'text':
      body = `Text: "${message.text?.body ?? ''}"`;
      break;
    case 'image':
      body = `Image (id ${message.image?.id})` +
        (message.image?.caption ? ` with caption: "${message.image.caption}"` : '');
      break;
    case 'audio':
      body = `Audio (id ${message.audio?.id})`;
      break;
    case 'video':
      body = `Video (id ${message.video?.id})` +
        (message.video?.caption ? ` with caption: "${message.video.caption}"` : '');
      break;
    case 'document':
      body = `Document "${message.document?.filename ?? ''}" (id ${message.document?.id})`;
      break;
    case 'sticker':
      body = `Sticker (id ${message.sticker?.id})`;
      break;
    case 'location': {
      const { latitude, longitude, name: locName, address } = message.location ?? {};
      body = `Location: ${latitude}, ${longitude}` +
        (locName ? ` (${locName})` : '') +
        (address ? ` - ${address}` : '');
      break;
    }
    case 'contacts':
      body = `Contacts shared (${message.contacts?.length ?? 0})`;
      break;
    case 'button':
      body = `Button reply: "${message.button?.text ?? ''}"`;
      break;
    case 'interactive': {
      const inter = message.interactive;
      if (inter?.type === 'button_reply') body = `Button reply: "${inter.button_reply?.title}"`;
      else if (inter?.type === 'list_reply') body = `List reply: "${inter.list_reply?.title}"`;
      else body = `Interactive (${inter?.type ?? 'unknown'})`;
      break;
    }
    default:
      body = `Unsupported message type: ${type}`;
  }

  return [
    'Echo from the bot',
    `From: ${name} (${waId})`,
    `When: ${when}`,
    `Type: ${type}`,
    body,
  ].join('\n');
}

// POST a JSON payload to /messages on the Graph API.
async function postToGraph(phoneNumberId, payload) {
  const url = `https://graph.facebook.com/${graphApiVersion}/${encodeURIComponent(phoneNumberId)}/messages`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  if (!res.ok) {
    throw new Error(`Graph API ${res.status}: ${text}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// Send a plain text message back to the user.
function sendTextMessage(phoneNumberId, to, text) {
  return postToGraph(phoneNumberId, {
    messaging_product: 'whatsapp',
    recipient_type: 'individual',
    to,
    type: 'text',
    text: { body: text },
  });
}

// Mark a received message as read (the double blue checks). Best-effort.
async function markMessageAsRead(phoneNumberId, messageId) {
  try {
    await postToGraph(phoneNumberId, {
      messaging_product: 'whatsapp',
      status: 'read',
      message_id: messageId,
    });
  } catch (err) {
    console.warn(`Could not mark ${messageId} as read:`, err.message);
  }
}

// Walk the webhook payload and echo every fresh incoming message.
async function handleIncomingPayload(body) {
  const entries = Array.isArray(body?.entry) ? body.entry : [];
  for (const entry of entries) {
    const changes = Array.isArray(entry.changes) ? entry.changes : [];
    for (const change of changes) {
      if (change.field !== 'messages') continue;
      const value = change.value ?? {};
      const phoneNumberId = value.metadata?.phone_number_id;
      const contacts = Array.isArray(value.contacts) ? value.contacts : [];
      const messages = Array.isArray(value.messages) ? value.messages : [];
      if (!phoneNumberId || messages.length === 0) continue;

      for (const message of messages) {
        if (!message.id || processedMessageIds.has(message.id)) continue;
        rememberMessageId(message.id);

        const contact =
          contacts.find((c) => c.wa_id === message.from) ?? contacts[0];
        const reply = prettifyMessage(message, contact);

        try {
          await markMessageAsRead(phoneNumberId, message.id);
          await sendTextMessage(phoneNumberId, message.from, reply);
          console.log(`Echoed message ${message.id} to ${message.from}`);
        } catch (err) {
          console.error(`Failed to echo ${message.id}:`, err.message);
        }
      }
    }
  }
}

// Route for GET requests (webhook verification handshake from Meta)
app.get('/', (req, res) => {
  const { 'hub.mode': mode, 'hub.challenge': challenge, 'hub.verify_token': token } = req.query;

  if (mode === 'subscribe' && token === verifyToken) {
    console.log('WEBHOOK VERIFIED');
    res.status(200).send(challenge);
  } else {
    res.status(403).end();
  }
});

// Route for POST requests (incoming messages and status updates)
app.post('/', (req, res) => {
  const timestamp = new Date().toISOString().replace('T', ' ').slice(0, 19);
  console.log(`\n\nWebhook received ${timestamp}\n`);
  console.log(JSON.stringify(req.body, null, 2));

  // Acknowledge to Meta within 20s, then process asynchronously so a slow
  // Graph API call never causes Meta to retry the same delivery.
  res.status(200).end();

  handleIncomingPayload(req.body).catch((err) => {
    console.error('Unhandled error processing webhook:', err);
  });
});

// Light health check for uptime monitors / Render
app.get('/healthz', (_req, res) => {
  res.status(200).json({ ok: true });
});

// Start the server
app.listen(port, () => {
  console.log(`\nListening on port ${port}\n`);
});
