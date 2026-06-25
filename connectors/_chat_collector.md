# Convention: single-account chat collector (by_chat)

Shared protocol for browser-driven messengers where **one operator account** holds a separate
chat per client — **Telegram, WhatsApp, Max**. There is no account to switch (`switch: none`,
`serves: by_chat`); the fan-out unit is the **conversation**. Each provider skill
(`connectors/{tg,whatsapp,max}/`) supplies only its deltas (web URL, session check, handle
format, quirks) and inherits everything below.

## Shared model

- **One operator account** per messenger (`config → sources.<svc>`, `switch: none`,
  `access: auto` once linked). **Access is session-level only** — the one question is *is the
  operator's account logged in?* Individual chats/channels have **no per-chat `cred_status`**:
  they're reachable by search (username / phone / peer-id) the moment the session is up. A client
  `quick_access` `service: tg|whatsapp|max` entry is a **routing pointer, not a credentialed
  access point** — ignore any `cred_status` on it (no «уточнить»). Nothing per-chat to request.
- **chat → client map**, built once from `behavior.channels` (primary/secondary) where
  `type: <svc>` → its handle (phone or `@username`). Chats mapping to no client are **ignored**.
- **Per-chat watermark** in `journal/<svc>_state.json`:
  `{ <client>: {last_message_id, last_ts, last_read_at, unread_count} }`.

## Shared algorithm

1. Open the provider's web app; **verify the session is logged in** — else **flag + stop**
   (linking is human-gated: the operator logs in / scans the QR). Reading is `auto` afterward.
2. Build the chat → client map.
3. **Detect new without opening:** from the chat list (unread badge + last-message preview +
   timestamp), select client chats with a last message **newer than that client's watermark**.
   Open **only** those — most days, few or none.
4. Read messages since the watermark. **Resolve the client's jurisdiction first**
   (INSTRUCTIONS §0) before interpreting.
5. Snapshot → `journal/inbox/<svc>_<date>.md` (one block per client; the engine source dot).
6. **mm_update inline** (`connectors/mm_update/SKILL.md`), `source='<svc>:<handle>:<date>'`:
   action/question/promise → `upsert_track(type='<svc>_action_required')`; movement →
   `add_history_event`; **closing is operator-only (§D)** — on a confirmation, `add_history_event`
   + refresh `next_action` to «Подтвердить закрытие …», never `update_status('done')`.
7. Advance each processed chat's watermark; write `journal/inbox/<svc>_heartbeat.txt`.
8. **mm_update finale** (cross-link reconciliation, `resolves_when`, read-modify-write, lint,
   self-check, audit-log) + the **unconditional dashboard render**.

## Shared safety

- **Read-only.** No send/reply/react — outbound only on an explicit "send" from the operator in
  Cowork chat.
- **Mark-as-read caveat.** Opening a chat may mark it read in some web clients (WhatsApp, Max) —
  minimise by opening only chats with new messages; note it as a known limitation. (Telegram
  `/a/` can preview without marking; provider skills state their behaviour.)
- Session linking is **human-gated**; reading is `auto` once linked. No QR/session data in state.

## Per-provider deltas (each skill specifies)

Web URL · how to verify the session is logged in · handle format (phone vs `@username`) ·
any mark-as-read side effect · provider quirks.

| Skill | Web app | Handle |
|---|---|---|
| `connectors/tg/sync.md` | `web.telegram.org/a/` | `@username` / peer id |
| `connectors/whatsapp/SKILL.md` | `web.whatsapp.com` | phone number |
| `connectors/max/SKILL.md` | `web.max.ru` | phone / `@username` |

## Atomic actions (single chat op, daemon or ad-hoc)

This file is the **sweep** (all chats, scheduled). For a **single** action — list chats, read
one chat, send a message — see `connectors/_chat_actions.md` (`list_chats` / `read_chat` /
`send_message`). The collector calls `read_chat` per conversation; the runtime calls these
directly when Mom asks ("check this chat" / "send a message"). `send_message` is outbound and
**approval-gated** — daemons never send.

## Related

- `connectors/_sources.md` — the by_chat granularity (single account, no switching).
- `connectors/_chat_actions.md` — the atomic list/read/send operations.
- `connectors/mm_update/SKILL.md` — the write path + §D close model.
