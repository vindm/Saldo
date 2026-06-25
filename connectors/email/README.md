# Skills for the `email` domain

> ⚠️ **Multi-account.** `email` is **not** one mailbox. It fans out over the operator's own
> accounts (`config → sources.email`: team Yandex.Mail + personal Gmail) **and** each client's
> mailbox in `quick_access` (e.g. `melati`'s Gmail, where its Mandiri/Coretax mail
> arrives). Enumerate via `connectors/_sources.md` (`enumerate_sources("email")`), one
> incremental pass per account with its own watermark, dedup across accounts, route shared
> inboxes by correspondent. The procedures below are the **per-account** operations; the
> composites run them once per source in the working set.
>
> All procedures for working with a mailbox as reusable infrastructure. Atomic operations — read_message, read_thread, list_messages. Composites — morning_full_scan, incremental_update.
>
> **Who calls these skills:**
> - The `Scheduled/email/SKILL.md` daemon — in the morning (`morning_full_scan`)
> - Me, in-session — on a trigger from the operator (atomic or composite)
> - The updater on a T4 event (a notification from the FTS/social fund/bank) — `read_message` for a specific email

## Atomic skills

| File | What it does | Parameters |
|---|---|---|
| [`read_message.md`](read_message.md) | Read **one** email in full: headers + body + attachments | `message_id_or_url`, `read_attachments` |
| [`read_thread.md`](read_thread.md) | Read a **thread** (the whole chain of related emails) | `thread_id_or_subject`, `message_count` |
| [`list_messages.md`](list_messages.md) | List emails by filter (sender, date, folder, label) | `from`, `since`, `folder`, `label` |
| [`reply_message.md`](reply_message.md) | 🔴 **Outbound** — reply to / send an email; approval-gated, multi-account-aware | `thread/recipient`, `from_account`, `text` |

## Composite skills

| File | What it does | When |
|---|---|---|
| [`morning_full_scan.md`](morning_full_scan.md) | Morning sweep: list_messages(since=24h, filter by known correspondents) → read_message for each match → daily report | Daemon 06:15 MSK; explicit "rebuild the mail" |
| [`incremental_update.md`](incremental_update.md) | Since last_run → list_messages → targeted read_message → append to the daily report | On a "what's new in the mail" trigger during the day |

## Which one to call when

| Trigger from the operator | Skill | Parameters |
|---|---|---|
| "open the email from X with subject Y" | `read_message.md` | `message_id_or_url` or search |
| "read the thread with the FTS about the demand" | `read_thread.md` | `thread_id_or_subject=...` |
| "which emails from Sber in May" | `list_messages.md` | `from=*@sberbank.ru, since=2026-05-01` |
| "what's new in the mail" | `incremental_update.md` | `since=last_run` |
| "rebuild the mail" | `morning_full_scan.md` | — |

## Account switching (per provider)

The morning sweep runs once **per source** in `enumerate_sources("email")` (operator Yandex.Mail
+ personal Gmail + each client's Gmail). Make the account active per its `switch` mode, then
**verify before reading** (read back the active login; on mismatch — stop and flag).

**Yandex.Mail** (`provider: yandex`, browser-driven via Claude-in-Chrome):
- Preferred — a **dedicated Chrome profile per Yandex account** (`switch: chrome_profile:<name>`);
  open the mailbox in that profile, no in-session switching.
- Otherwise — Yandex multi-login: top-right avatar → choose the account, or open
  `https://mail.yandex.ru/?login=<login>`.
- **Verify:** the active login shown in the avatar/menu == the source `handle`.

**Gmail** (`provider: gmail`):
- If a **Gmail API connector** is authorized per Google account (`switch: cred/connection`):
  select the connection bound to that account — **no UI**. Verify via the connector's
  profile/whoami (the connected address).
- If **browser-driven**: a dedicated Chrome profile per Google account, or the account switcher
  (avatar → choose), or the `authuser` index (`https://mail.google.com/mail/u/<n>/`). **Verify:**
  the account email in the avatar == the source `handle`.
- Client Gmails (e.g. `melati`'s) are reached either by the client sharing delegated
  access to the operator's account, or by a separate authorized connection/profile — respect
  `cred_status` and skip+flag if not connected.

> Provider mechanics only — the registry, watermark, routing and dedup rules are in
> `connectors/_sources.md`. WhatsApp/Telegram are single-account/`switch: none` and have no such
> section (clients are chats, not accounts).

## Known correspondents (filter for full_scan)

- **Clients** — email from `state/<client>/identity.json.contacts.email` (via `_loaders.load_clients_from_index()`). After the Phase 2 migration on 2026-05-25, clients_data.json was archived.
- **Government bodies** — domains `@nalog.gov.ru`, `@sfr.gov.ru`, `@rosstat.gov.ru`, `@gks.ru`
- **Client banks** — `@sberbank.ru`, `@tinkoff.ru`, `@tochka.com`, `@vtb.ru`
- **Team** — Anastasia, Alyona (if email addresses exist)
- **Partners** — Yandex.Taxi (for the client), agents (for the client)

## Format for calling one skill from another

Analogous to `finkoper/`:

```
1. Read `connectors/email/list_messages.md`. Execute:
   from = null
   since = <24h ago>
   folder = "Inbox"
   Get the array message_metadata[].

2. For each email from a known correspondent:
   Read `connectors/email/read_message.md`. Execute:
     message_id_or_url = <id from step 1>
     read_attachments = false
   Collect the result.
```

## Security

The **read** atomic skills (`read_message`, `read_thread`, `list_messages`) are **read-only** — per `security_rules.md §3`: opening an email, downloading attachments into `Downloads/` — no approval; marking as read / deleting — never. **Sending** is the one outbound action and lives in its own skill, `reply_message.md` — compose → show the draft → send **only on the operator's explicit "send"** (`safety-rules.md` `external_sends`). Daemons never send; the read skills never send.

## History

- **XXXX-05-16** — refactored from the monolithic `Scheduled/email/SKILL.md` (70 lines) into a decomposed structure. P4-email.

---

_Folder created 2026-05-16 as part of P4._
