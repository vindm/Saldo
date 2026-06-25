# Skill: max — client-chat collector (Max messenger)

A **single-account chat collector** — follows the full shared protocol in
`connectors/_chat_collector.md` (one operator account, clients are chats, `switch: none`,
`serves: by_chat`, per-chat watermark, read-only, mm_update inline + §D close, unconditional
render). This file is only the Max deltas.

> Max (`web.max.ru`) is a Russian messenger; expect RU clients to adopt it alongside or instead
> of Telegram. A client is mapped by a `behavior.channels` entry with `type: max`.

## Deltas

- **Web app:** `web.max.ru`, the operator's logged-in session (Claude-in-Chrome).
- **Session verify:** if the login/QR screen shows, the session is not linked → **flag + stop**
  (human-gated login). Reading is `auto` once linked.
- **Handle:** phone number or `@username` — map a chat to a client by its `behavior.channels`
  `type: max` handle.
- **Mark-as-read side effect:** assume opening a chat marks it read (like WhatsApp) until
  confirmed otherwise on the live client — minimise by opening only chats with new messages.
- **State file:** `journal/max_state.json`; snapshot `journal/inbox/max_<date>.md`; heartbeat
  `journal/inbox/max_heartbeat.txt`; mm_update `source='max:<handle>:<date>'`.
- **Jurisdiction:** resolve per client (INSTRUCTIONS §0) before interpreting.

## Atomic actions & UI playbook

For a single op — `list_chats` / `read_chat` / `send_message` — use `connectors/_chat_actions.md`
(protocol + safety; `send_message` outbound, gated). **Max UI mechanics:**
`connectors/max/ui_playbook.md` (an unverified scaffold — `web.max.ru` differs per primitive;
do not reuse WhatsApp/Telegram selectors). It self-corrects on first real use via the
recover+capture loop (`policies/skill-evolution.md`); learned notes → `journal/playbook_notes/max.md`.

## Related

- `connectors/_chat_collector.md` — the shared algorithm and safety this skill inherits.
- `connectors/_chat_actions.md` — atomic list/read/send for ad-hoc operator requests.
- `connectors/whatsapp/SKILL.md`, `connectors/tg/sync.md` — sibling chat collectors.
- `tests/runtime_scenarios/` — S9/S10 gate the by_chat behaviour.
