# Composite skill: email/morning_full_scan

Morning full sweep of **every email account** the practice can read — the operator's own
mailboxes **and** each client's mailbox — into one daily report. Multi-account by
`connectors/_sources.md`; one incremental pass per account, not per client.

## Parameters

| Parameter | Type | Default |
|---|---|---|
| `today` | date | today's date (instance.timezone) |
| `lookback_hours` | int | `24` — used only for an account with no watermark yet |

## Algorithm

### Step 1. Preparation (build the account set + the correspondents map — once)

1. **Enumerate the accounts** — `enumerate_sources("email")` (`connectors/_sources.md`):
   operator-owned from `config → sources.email` (team Yandex.Mail, personal Gmail) **∪** every
   client's `state/accounts.json → quick_access` with `service: email` (e.g. `melati`'s
   `melatispa@gmail.com`). Dedup by `(provider, handle)`.
2. **Drop what can't run now** — keep `access: auto` with `cred_status: connected`; **skip +
   flag** the rest (e.g. «Gmail melati — доступ не выдан»). Never fail the run.
3. **Build the known-correspondents map once** (shared across accounts) — clients' emails from
   `engine/_loaders.load_clients_from_index()` (`identity.contacts.email`) + government bodies +
   client banks + team + partners (see "Known correspondents" below).

### Step 2. Fan out — one pass per account

> One pass per **account**, not per client. The operator's shared inbox is read once and routed
> to many clients; a client's own mailbox routes 1:1. Independent accounts may be done in
> parallel.

For each source `S` in the set:

- **a. Switch + verify.** Make `S` active per its `switch` mode (README → "Account switching":
  Yandex profile/multi-login; Gmail connection/profile). **Read back the active login and assert
  it equals `S.handle` — on mismatch, STOP, read nothing, flag it, skip `S`.** (A wrong-account
  read crosses client data.)
- **b. Watermark.** `since = ` the account's stored watermark
  (`journal/finkoper_state/email/<account>.json`) or `now − lookback_hours` if first run.
- **c. List.** `list_messages.md` with `from=null, since=<watermark>, folder="All",
  only_unread=false, limit=200` → `recent`.
- **d. Route by source kind:**
  - `serves: by_correspondent` (operator inbox) → keep only messages matching the
    correspondents map (label `client:<id>` / `gov_authority` / `bank:<bank>` / `team` /
    `partner`); the rest are **counted, not read** (and a never-seen sender may be surfaced as a
    possible new correspondent, e.g. the `vano521@…` question).
  - `serves: [<client>]` (a client's own mailbox) → every non-spam message is **that client's**
    (label `client:<id>`); drop obvious newsletters/spam only.
- **e. Dedup across accounts** by global `message-id` — a message present in both the operator
  inbox and the client inbox is collected **once**.
- **f. Read + advance.** `read_message.md` (`read_attachments=false`) for each kept message;
  advance the account watermark to the newest message seen; write the per-account heartbeat
  `journal/finkoper_state/email/<account>.json`.

Merge all kept messages from all accounts into one `matched` set for the steps below.

### Step 3. Categorize by severity

For each in `matched` — severity from subject + first 500 chars:
- **🔴 Urgent** — "urgent", "today", "by end of day", "demand", "audit", "fine", "penalties", "block"
- **🟡 Needs a reply** — a direct question or request for action
- **📩 Informational** — notifications, newsletters, FYI

### Step 4. R6 — preserving manual notes

If `journal/inbox/mail_<today>.json` already exists with the operator's manual notes — move them
into `journal/operator_decisions.md` before overwriting.

### Step 5. Building the daily report

Write `journal/inbox/mail_<today>.json` — the contract the engine reads
(`engine/_loaders.load_daemon_mail`; the file is **`mail_`**, not `email_`). One object, an
`items` array, ordered urgent → needs-reply → informational:

```json
{
  "items": [
    {
      "severity": "high",
      "from_name": "Sender name",
      "from_email": "sender@example.com",
      "subject": "Email subject",
      "when": "DD.MM HH:MM",
      "client": "client_id or null",
      "label": "client | gov_authority | bank | team | partner",
      "source_account": "yandex:team | gmail:personal | gmail:melatispa",
      "preview": "first ~500 characters",
      "attachments": ["name.pdf (120 KB)"]
    }
  ]
}
```

`severity` ∈ `high` | `medium` | `low`. `source_account` = which mailbox it came from (for
audit/dedup transparency). Emit `{"items": []}` if nothing matched (never omit the file — the
heartbeat + empty list is the "ran, found nothing" signal). Do **not** record contents of emails
from unknown correspondents (only count them, outside `items`).

### Step 6. Global heartbeat

In addition to the per-account heartbeats (Step 2f), write `journal/inbox/email_heartbeat.txt`:
```
YYYY-MM-DD HH:MM OK  (accounts: N ok, M skipped)
```

### Step 7. Applying to client state (via mm_update)

For each client with a significant email (🔴 / 🟡) — apply via the `mm_update` cognitive protocol
(`connectors/mm_update/SKILL.md`):

- **Email requires action**: `_tracks.upsert_track(cid, {type='email_action_required', status='active', source='email:<sender>:<date>', ...})`.
- **Email confirms something on an existing track**: `_tracks.add_history_event(cid, tid, event_text, source='email:<sender>:<date>')`.
- **A new fact** (new bank / detail / counterparty): `state_ops.state_write` into the matching `state/*.json`.
- **Government bodies** — usually create a new track OR move an existing one (return accepted → refresh `next_action` to «Подтвердить закрытие …»; the operator closes).

For team email (Anastasia/Alyona) that concerns the work process — update `system_wide/mental_model.md`.

### 🔴 Mandatory mm_update finale — source-agnostic (same depth as a signal from the operator in chat)

> Writing a track/risk is NOT the end. For EACH affected client, carry it through:

1. **Cross-link reconciliation** across all their `state/*.json` (and related clients): close answered `open_question`/tracks in `tasks.json` (status=completed + history), reassess `risks.json`, fill in ❓ elsewhere, update `mental_model.md` + append `history.jsonl`.
2. **`resolves_when`** on every NEW open_question track.
3. **Read-modify-write** — never overwrite `tasks_overrides` / the operator's manual decisions (via `_tracks`/`state_ops`).
4. **lint + publish**: `python3 engine/generate.py` (runs `state_lint`); publish only on exit 0.
5. **Self-check**: grep for leftover active `open_question`/`❓` on the topic — if hanging, the finale isn't finished.
6. **Audit-log** as one block in `journal/operator_decisions.md`.

### If 0 emails from known correspondents in the period (across all accounts)

- Write `mail_<today>.json` as `{"items": []}`; still write all heartbeats (the daemon ran, the mail is just quiet).

## Security

- Do NOT mark as read. Do NOT delete, reply, or create drafts in this skill.
- **Verify-before-read** (Step 2a) is a hard gate — never read a mailbox without confirming it is the intended account.

## Relation to other skills

- Accounts/watermark/routing/dedup: `connectors/_sources.md`; switching mechanics: README → "Account switching".
- After the sweep, `mm_update` processes significant emails by the same protocol as tg/finkoper/news.

## History

- **2026-05-16** — extracted as a composite during the P4-email refactor.
- **2026-06-25** — retrofit to multi-account fan-out (`_sources.md`): per-account switch+verify, per-account watermark, cross-account dedup, `source_account` on each item. Was single Yandex.Mail — melati's Gmail (Mandiri/Coretax mail) is now read.

---

_v1.0 2026-05-16; v1.1 2026-05-25 (state/ architecture); v1.2 2026-06-25 (multi-account fan-out)._

---

## 🔴 Unconditional dashboard render — ALWAYS, as the last action

> The render is NOT gated on whether there were changes. Whatever happened above — state edited
> or not, one client affected or zero — **as the last action the daemon MUST**:
>
> `python3 engine/generate.py` (runs `state_lint`); on exit 0, publish.
>
> Reason: the dashboard carries time-dependent content (today's date, overdue items, "in N
> days") that must refresh **daily** regardless of changes. Skipping the render on a quiet day =
> a frozen date (incident 2026-06-11→13; the render is unconditional).
