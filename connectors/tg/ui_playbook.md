# Telegram UI playbook (web.telegram.org/a/) — the HOW (learnable)

Engine **canonical, read-only at runtime**; learned Field notes → the data-dir overlay
`<data.dir>/journal/playbook_notes/tg.md`. Protocol & safety: `connectors/_chat_actions.md`.
Structure: `connectors/_ui_playbook.md`. Loop: `policies/skill-evolution.md`. Steps are the
current best description and **self-correct** via the loop.

## Primitives

**`session`** — Open `web.telegram.org/a/`. ⚠️ Use `/a/`, **not** `/k/` — `/k/` is a separate
storage that is **not** logged in; the operator's session lives in `/a/`. Logged in → the chat
list. Verify before acting.

**`jump_to_chat`** — The search box, or the deep-link `#<peer_id>` (the hash is **numeric peer
id**, not `@username`). Verify the header matches before reading/sending.

**`scroll` / `load_history`** — Virtualised list; scroll up to load older messages until the
watermark.

**`read_messages`** — Main pane, oldest→newest. `/a/` can preview without forcing read (unlike
WhatsApp) — confirm current behavior via the loop.

**`attach`** — Clip icon → choose file. **`send`** — 🔴 gated (`_chat_actions` `send_message`):
compose box at the bottom; type; send button or Enter; show the draft, send only on approval.

**`download_file`** — Click the media message → download. **`detect_success`** — the sent message
appears with a status; confirm its presence, not just the click.

**`quirks`** — `/a/` vs `/k/` (above); numeric `peer_id` in deep-links.

## Field notes

Not here — in the overlay `<data.dir>/journal/playbook_notes/tg.md` (per
`policies/skill-evolution.md`), keyed by primitive. Corroborated, broadly-true lessons are curated
upstream into this canonical file by the developer.
