# Atomic action: email/reply_message — 🔴 OUTBOUND, APPROVAL-GATED

Replying to, or sending, an email. The `email` collector is **read-only**; this is the one
outbound email action. Used **ad-hoc by the runtime** when Mom asks — «ответь на письмо ФНС»,
«напиши клиенту, что отчёт сдан». Daemons never send.

**Multi-account aware.** Send **from the right mailbox** — the account the thread is in, or the
correspondent account that owns the relationship (`connectors/_sources.md`,
`connectors/email/README.md` → "Account switching"). **Switch to it and verify the active login**
before composing — sending from the wrong account leaks/mislabels.

## Protocol

1. **Resolve** the thread/recipient **and the sending account**; verify both (read back the
   active login == the intended mailbox; confirm the recipient).
2. **Compose** the reply (quote/thread as needed) and **SHOW the draft** to the operator in
   Cowork chat — do **not** send.
3. **Send only on the operator's explicit "send / отправь"** (`policies/safety-rules.md`
   `external_sends`).
4. **Log** — `_tracks.add_history_event(cid, tid, '<what was sent>', source='email:<recipient>:<date>')`
   on the relevant track.

Never send a PIN, code, password, or attachment containing credentials. For a reply to the tax
authority, follow the jurisdiction checklist (`jurisdictions/<code>/checklists/reply-to-tax-authority.md`).

## Safety

Outbound, **operator-gated**. Read of the thread to reply to is via `read_message.md` /
`read_thread.md` (no approval); only the send is gated. Daemons never call this.

## Related

- `connectors/email/README.md` — domain + account switching; `read_message.md` / `read_thread.md` — read the thread first.
- `connectors/_sources.md` — which account to send from; `connectors/mm_update/SKILL.md` — log the outbound.
