# Skill: whatsapp — client-chat collector

A **single-account chat collector** — follows the full shared protocol in
`connectors/_chat_collector.md` (one operator account, clients are chats, `switch: none`,
`serves: by_chat`, per-chat watermark, read-only, mm_update inline + §D close, unconditional
render). This file is only the WhatsApp deltas.

> Primary channel for `melati` (WhatsApp `081200000000`) and the pattern the Bali salon
> will reuse. RU clients mostly use Telegram/Max/email, so the WhatsApp chat list is short.

## Deltas

- **Web app:** `web.whatsapp.com`, the operator's logged-in session (Claude-in-Chrome).
- **Session verify:** if the QR-login screen shows, the session is not linked → **flag + stop**
  (the operator scans the QR; human-gated). Reading is `auto` once linked.
- **Handle:** phone number; map a chat to a client by its `behavior.channels` `type: whatsapp`
  number (`081200000000` → `melati`).
- **Mark-as-read side effect:** opening a chat in WhatsApp Web **marks its messages read** —
  unavoidable. Minimise by opening only chats with new messages since the watermark; treat it as
  a known limitation.
- **State file:** `journal/whatsapp_state.json`; snapshot `journal/inbox/whatsapp_<date>.md`;
  heartbeat `journal/inbox/whatsapp_heartbeat.txt`; mm_update `source='whatsapp:<number>:<date>'`.
- **Jurisdiction:** `melati` is `id` — messages may be Indonesian/English, reasoned in
  `id` terms (INSTRUCTIONS §0).

## Atomic actions & UI playbook

For a single op (not the sweep) — `list_chats` / `read_chat` / `send_message` — use
`connectors/_chat_actions.md` (protocol + safety; `send_message` is outbound, approval-gated,
daemon never sends). The **UI mechanics** (how to jump to a chat, scroll, attach, send, download
on WhatsApp Web) live in **`connectors/whatsapp/ui_playbook.md`** — follow it, and grow it via the
learning loop (`policies/skill-evolution.md`).

## Related

- `connectors/_chat_collector.md` — the shared sweep algorithm and safety this skill inherits.
- `connectors/_chat_actions.md` — atomic list/read/send for ad-hoc operator requests.
- `tests/runtime_scenarios/` — S9 is the gate.
