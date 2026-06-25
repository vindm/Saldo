# Max UI playbook (web.max.ru) — the HOW (learnable)

Engine **canonical, read-only at runtime**; learned Field notes → the data-dir overlay
`<data.dir>/journal/playbook_notes/max.md`. Protocol & safety: `connectors/_chat_actions.md`.
Structure: `connectors/_ui_playbook.md`. Loop: `policies/skill-evolution.md`.

> ⚠️ **Unverified scaffold.** `web.max.ru` differs from WhatsApp/Telegram per primitive — do
> **not** reuse their selectors. The first real use seeds the overlay via the recover+capture
> loop; these are placeholders to correct, not to trust.

## Primitives (to confirm on first real use)

- **`session`** — open `web.max.ru`; recognise the login screen; verify logged-in before acting.
- **`jump_to_chat`** — find/open a conversation (search vs contact list — confirm); verify the header.
- **`scroll` / `load_history`** — load older messages (lazy/paginated — confirm).
- **`read_messages`** — read the thread; assume opening **marks read** until confirmed otherwise.
- **`attach`** / **`send`** — 🔴 gated: compose box, attach control, send trigger (button/Enter — confirm); show draft, send on approval.
- **`download_file`** — save media/file.
- **`detect_success`** — confirm the sent message is present (status indicator — confirm).

## Field notes

In the overlay `<data.dir>/journal/playbook_notes/max.md` (per `policies/skill-evolution.md`),
keyed by primitive. As the overlay accrues corroborated steps, the developer curates them upstream
into this canonical file.
