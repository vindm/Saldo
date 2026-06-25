# Composite skill: email/incremental_update

Incremental sweep **across all email accounts** since each one's watermark — appends to the
daily report. Multi-account, same registry as the morning sweep (`connectors/_sources.md`).

## Parameters

| Parameter | Type | Default |
|---|---|---|
| `since` | ISO datetime | per-account watermark (`journal/finkoper_state/email/<account>.json`) |
| `client_filter` | client_id | `null` (narrows the account set to that client's mailbox + the operator inbox) |
| `trigger_description` | string | `null` (for the marker in the daily report) |

## Algorithm

### Step 1. Account set + `since`

Enumerate `enumerate_sources("email")` (drop non-connected, flag) exactly as
`morning_full_scan.md` Step 1. `since` per account = its own watermark (or the `since`
parameter if given). If `client_filter` is set, restrict to that client's mailbox + the
operator inbox (`by_correspondent`).

### Step 2. Fan out — one pass per account

For each account: **switch + verify** (read back the active login == handle, else stop/flag/skip),
list `list_messages.md` (`from=null, since=<watermark>, folder="All", limit=100`), **route**
(by_correspondent vs the client's own mailbox), **dedup across accounts** by message-id, read
each match (`read_message.md`), advance that account's watermark. Identical to
`morning_full_scan.md` Step 2; if every account returns empty → there is nothing new (see "If
there are no changes").

### Step 4. R6 — preserving manual notes

Before appending to the daily report — save the operator's manual notes into `operator_decisions.md`.

### Step 5. Appending to the daily report

If `journal/inbox/email_<today>.md` exists — append to the end:

```markdown

---

## 🔄 Appended in the incremental run HH:MM (trigger: <trigger_description>)

**Emails since last_run (HH:MM):**

### 🔴 Urgent (N)
[blocks]

### 🟡 Needs a reply (N)
[blocks]

### 📩 Informational (N)
[blocks]
```

If `<today>.md` does not exist — create it as a full daily report (which means the daemon didn't run in the morning).

### Step 6. Updating the heartbeat

Overwrite `email_heartbeat.txt` with the current timestamp.

### Step 7. Applying to state + the mandatory mm_update finale

Same as `morning_full_scan.md` step 9 (applying to state) — and MANDATORILY the same mm_update finale: cross-link reconciliation across all `state/*.json` of the affected client, `resolves_when` on new questions, read-modify-write (don't overwrite `tasks_overrides`/the operator's decisions), `generate.py`/lint, self-check, audit-log. **An incremental parse updates links just as fully as the morning one — source-agnostic.**

### If there are no changes

- Do not append to the daily report.
- The heartbeat may be updated (or not — that's a matter of idempotency).
- Return to context: "For the period HH:MM..HH:MM there are no new emails from known correspondents."
- 🔴 STILL perform the unconditional dashboard render (see the "Unconditional dashboard render" section below) — even when there are no emails.

## Idempotency

On a repeat call with the same `since` (or after updating the heartbeat) — `list_messages` will return empty.

## When it's called

- Me, in-session, on a "what's new in the mail", "an email arrived" trigger.
- The updater may call it before a T4 check if the last `morning_full_scan` was a while ago.

## History

- **XXXX-05-16** — extracted as a composite during P4-email.

---

_Version 1.0 — 2026-05-16._


---

## 🔴 Unconditional dashboard render — ALWAYS, as the last action

> The dashboard render is NOT gated on whether there were changes. Whatever happened above — whether state was edited or not, whether at least one client was affected or zero — **as the last action the daemon MUST**:
>
> `python3 engine/generate.py` (runs `state_lint`); on exit 0, publish `cp _tmp_html/*.html ..` (from the `_data` directory).
>
> Reason: the dashboard carries time-dependent content (today's date in the header, overdue items, "in N days") that must be refreshed **daily**, regardless of whether there were changes in state. Skipping the render on a "quiet day" = a frozen date (incident 2026-06-11→13, the operator's decision: the render is unconditional).
