# Convention: atomic chat actions — list / read / send (tg, whatsapp, max)

The **single-action** operations on a chat, so neither a daemon nor the runtime improvises the
web UI each time. Pairs with `connectors/_chat_collector.md` (the sweep composite, which calls
`read_chat` per conversation) and shares its provider table (web URL, handle, session-verify).
Used both **by daemons** and **ad-hoc by the runtime** when Mom asks — e.g. «посмотри переписку
с melati в WhatsApp» → `read_chat`; «напиши клиенту в TG, что отчёт готов» → `send_message`.

> This file is the **protocol + safety** (the WHAT). The **mechanics** (the HOW — `jump_to_chat`,
> `scroll`, `read`, `attach`, `send`, `download` on *this* web app) are **per provider** and
> differ down to each primitive: see `connectors/<provider>/ui_playbook.md` (structure:
> `connectors/_ui_playbook.md`). Do **not** improvise the UI — follow the provider's playbook,
> and when it's wrong/missing run the recover+capture loop (`policies/skill-evolution.md`).

## Why this is shared — when the mechanics aren't

A fair question: if every provider's UI is individual, why a shared file at all? Because two
different things are split:

- **Shared here** = the **safety contract + action vocabulary** (verify recipient → show draft →
  send only on explicit approval → log; daemons never send; list/read are read-only). These are
  **identical** for tg/whatsapp/max and **must stay uniform** — if each provider re-stated its own
  gates, one would eventually drop one. Sharing the gates is a **safety guarantee**, not just DRY;
  it also gives a stable vocabulary (`send_message`) regardless of provider.
- **Per-provider** (`connectors/<x>/ui_playbook.md`) = the **mechanics** (`jump_to_chat`, `scroll`,
  selectors, the send button) — these genuinely differ and are learnable.

Interface/policy vs implementation. The rule: **share only what's invariant AND harmful-if-drifted
(safety) or a stable contract (action names); never share what differs (UI).** That is also why
`email` has its **own** `reply_message.md` (thread semantics differ from chats) rather than
force-fitting this contract — sharing is scoped to where it's genuinely common.

## `list_chats(provider, [filter])` — read-only

Open the provider web app and **verify the session** (`_chat_collector` step 1; not logged in →
flag + stop). Read the **chat list** (name, last-message preview, timestamp, unread badge);
map each row to a client by `behavior.channels` handle where known. Return the list. No approval.
Use to find a chat or see who's unread without opening anything.

## `read_chat(provider, chat, [since])` — read-only

Resolve `chat` (by a client's `behavior.channels` handle, or by name) and **verify it's the
intended one** before reading. Open it; read messages since `since` (or the watermark / a bounded
window). Return them. No approval. ⚠️ Opening marks-as-read in WhatsApp/Max (note it). If
anything is significant, apply `mm_update` inline (same as the collector) — reading is also a
chance to update state.

## `send_message(provider, chat, text)` — 🔴 OUTBOUND, APPROVAL-GATED

**Never send autonomously.** Outbound to a client is gated (`policies/safety-rules.md`
`external_sends` + `browser_actions`). Protocol:

1. **Resolve + verify the recipient** — confirm the chat maps to the intended client (read back
   the handle/name). A wrong-chat send leaks one client's data to another.
2. **Compose and SHOW the draft** to the operator in Cowork chat — do **not** send yet.
3. **Send only on the operator's explicit "send / отправь"** → type into the message box and send.
4. **Log it** — `_tracks.add_history_event(cid, tid, '<what was sent>', source='<provider>:<handle>:<date>')`
   so the outbound is on the track's record.

Never send a PIN, code, password, or other credential. The daemons **never** call this; only the
runtime, on the operator's command.

## Safety summary

| Action | Approval | Notes |
|---|---|---|
| `list_chats` / `read_chat` | none (read-only) | verify session; mark-as-read caveat (WA/Max) |
| `send_message` | **operator's explicit "send"** | verify recipient; no credentials; log via mm_update |

## Related

- `connectors/_chat_collector.md` — the sweep + provider deltas these actions reuse.
- `connectors/{tg,whatsapp,max}/` — each references this file for its atomic actions.
- `connectors/mm_update/SKILL.md` §D — close model; `policies/safety-rules.md` — the outbound gate.
