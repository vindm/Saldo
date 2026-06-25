# WhatsApp UI playbook (web.whatsapp.com) — the HOW (learnable)

Mechanics for operating WhatsApp Web, by primitive. Protocol & safety: `connectors/_chat_actions.md`.
Structure: `connectors/_ui_playbook.md`. Learning loop: `policies/skill-evolution.md`.

> This file is **engine canonical — read-only at runtime.** The runtime confirms/corrects steps
> via the loop, writing **Field notes to the data-dir overlay** `<data.dir>/journal/playbook_notes/whatsapp.md`
> (never to this file). At run time the runtime composes these steps + that overlay.
>
> **Curated 2026-06-25** — `session`, `jump_to_chat`, `chat_list`, `read`, `compose`, `send`,
> `detect_success`, and the official-account quirk were **confirmed against live WhatsApp Web** and
> promoted from an instance overlay (the upstream tier of `policies/skill-evolution.md`).

## Primitives

**`session`** — Open `web.whatsapp.com` (Claude-in-Chrome). Logged in → the left-pane chat list
renders + your own avatar shows; the browser **tab title reads `(N) WhatsApp`** where N = total
unread (a cheap logged-in + has-unread signal without a screenshot). Not logged in → a **QR
screen** → STOP + flag (operator scans; human-gated). Verify the chat list before doing anything.

**`jump_to_chat`** — Click the **search box** at the top of the left pane; type the client's name
or number (from `behavior.channels`). Click the matching row. **Verify** the conversation header
shows the matching name/number before reading or sending.

**`scroll` / `load_history`** — Older messages load by scrolling **up** in the main pane (lazy).
Scroll until you reach the watermark timestamp; don't assume the first screen is all of it.

**`read_messages`** — Messages render oldest→newest in the main pane. ⚠️ Opening a chat **marks
its messages read** (unavoidable) — open only chats with new messages since the watermark.

**`attach`** — The **clip/paperclip** icon near the compose box → Document/Photo → pick the file.

**`send`** — 🔴 outbound, gated (`_chat_actions` `send_message`): the compose box ("Type a message")
is at the bottom-center; click it, type, show the operator the draft, send only on the explicit
"send". **Send via Enter (Return) — it's reliable.** The green paper-plane button (bottom-right)
also sends, **but its pixel coordinates shift when the window/viewport resizes** — a click at a
stale position misses and leaves the text unsent, so prefer Enter or re-locate the button fresh
each time. `Shift+Enter` = newline. A first message to a new number may show a confirm step.
*(corroborated live 2026-06-25 — a stale-coordinate button click missed; Enter sent.)*

**`download_file`** — Click a media message → the **download** arrow; or the message menu →
Download. Saves to the browser's download dir.

**`detect_success`** — The sent message appears at the bottom-**right** of the thread with a
timestamp and a status tick: clock → single ✓ → **double ✓✓ (delivered)**; the left-list row's
preview updates to "✓✓ <text>". Confirm the message bubble is present (not just that you clicked).

**`quirks`** — The **official "WhatsApp" account** chat has **no compose box** ("Only WhatsApp can
send messages") — not a sendable conversation. Multi-device session can drop; if the chat list
won't load, re-run `session`. Search can lag; see Field notes.

## Field notes (learned)

Learned notes are **not** kept here — they live in the per-instance overlay
`<data.dir>/journal/playbook_notes/whatsapp.md` (per `policies/skill-evolution.md`), keyed by
primitive, format `- <primitive>: <working step>. (date · trigger · evidence · status)`. The
running instance writes there; corroborated, broadly-true lessons are curated upstream into this
canonical file by the developer.
