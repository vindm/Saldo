# Convention: multi-account source registry & fan-out

A channel connector is **not one account** — it is a *set* of accounts of the same kind:
the operator's own mailbox **and** each client's mailbox the operator can read, often across
different providers (Yandex.Mail + Gmail; Google Drive + Yandex.Disk; the operator's WhatsApp
+ each client's number). Every channel collector (`email`, `documents`, `whatsapp`, the bank
and portal collectors) follows this one pattern so adding an account is pure config, never a
code change.

## The registry — two levels, one shape

A **source** = one account/profile to check. There are exactly two places sources come from,
and a collector's working set is their **union**:

1. **Operator-owned** (the practice's own accounts, serving many clients) →
   `config/instance.yaml → sources.<service>[]`. E.g. the team Yandex.Mail, the operator's
   personal Gmail, the operator's WhatsApp.
2. **Client-owned** (an account a client owns, the operator has access to) → that client's
   `state/accounts.json → quick_access[]` (already the per-client registry the `documents`
   collector uses). E.g. `melati`'s `melatispa@gmail.com`, a client's Drive.

`enumerate_sources(service)` = operator sources of that service **∪** every client's
`quick_access` of that service, **deduped by (provider, handle)**. One list, both levels.

### Source shape

```
service:      email | gdrive | yandexdisk | whatsapp | telegram | bank | portal
provider:     yandex | gmail | mandiri | tbank | coretax | …
handle:       the login / folder id / phone number to open
cred:         a REFERENCE into secrets/ (never the secret itself)
cred_status:  connected | missing | after_first_billing
owner:        operator | client:<id>
serves:       [<client ids>] (1:1/few) | "by_correspondent" (shared inbox) | "by_chat" (one account, per-client chats — WA/TG)
scope:        { folders | labels | filters }   (optional, narrows the fetch)
access:       auto | human_gated
              # auto = read-only API/connector, runs unattended (email, drives, EGRUL).
              # human_gated = needs a person to log in / pass 2FA — MOST BANKS, some
              #   portals. The fan-out queues these for an operator-present run, never a
              #   3am unattended one. (Ties to docs/COVERAGE-MAP.md "cadence by cost".)
switch:       how this account is made active — provider-specific (see provider skill):
              cred/connection (MCP-backed) | chrome_profile:<name> | account_switcher | relogin | none
```

## Two fan-out granularities: per-account vs per-chat

- **Per-account** (`email`, `documents`, `bank`, `portal`): clients have **separate accounts**
  (the operator's + each client's own). Fan out over *accounts*, switching between them per the
  provider's mechanism below.
- **Per-chat, single account** (`tg`, `whatsapp`, `max`): **one operator account**, each client
  is a *chat/conversation* inside it — **no account switching at all** (`switch: none`). Fan out
  over *conversations*, routing each to a client by its number/username/peer-id from
  `behavior.channels` (`serves: by_chat`). The per-account watermark becomes a per-chat
  watermark (last message id per conversation).

  🔴 **Access is session-level, not per-chat.** For `by_chat` providers there is exactly **one**
  access question — *is the operator's `tg`/`whatsapp`/`max` session logged in?* (the
  `sources.<svc>` account). Individual chats and channels carry **no per-chat `cred_status`** —
  they're **routing targets you find by search** (username / phone / peer-id) and open directly;
  nothing to "request" or confirm. A client `quick_access` entry with `service: tg|whatsapp|max`
  is a routing pointer, **not** a credentialed access point: **ignore any `cred_status` on it**,
  and the dashboard must **not** render an access chip («уточнить»/«доступ есть») for it. (Joining
  a genuinely private channel needs an invite — but that's a one-off the operator does in the app,
  not a per-chat access state the system tracks.)

## Switching accounts is provider-specific — delegated to the provider skill

The registry says *which* account and *which mechanism*; **how** to actually switch is owned by
each provider skill, because the mechanics differ in kind:

- **MCP / credential-backed** (`gdrive`, a Gmail API connector, `egrul`): an account = a
  distinct authorized connection/credential. "Switching" = selecting that credential, or
  ensuring the target folder/mailbox is **shared to** the connected account — **no UI**.
- **Browser-driven** (Yandex.Mail, WhatsApp Web, a bank portal): switching is a UI act — the
  provider's account switcher, an `authuser=`/`login=` URL, or a **dedicated Chrome profile
  per account**. **Prefer a dedicated profile/credential per account** over in-session
  switching: isolation makes the switch deterministic and stops one account's session state
  leaking into the next.

Every provider skill MUST carry an **"Account switching" section** with the concrete steps for
that provider — the daemon does not improvise switching.

🔴 **Verify before you read — every account, every time.** After switching, confirm the active
account identity equals the source's `handle` (read back the logged-in address / number /
connected email) **before reading anything**. On mismatch: **stop, read nothing, flag it.**
Reading the wrong account routes one client's data into another's file — a hard correctness and
privacy failure. Never assume the switch took.

## Fan-out rules (efficient + optimal)

- **One pass per account, not per client.** A shared operator mailbox is fetched **once** and
  its messages routed to many clients — never re-opened per client. This is the core
  efficiency win (no N× redundant scans).
- **Per-account incremental watermark** — last message-id / IMAP UID / `modifiedTime`, stored
  in `journal/finkoper_state/<service>/<account>.json`. Fetch only **since the watermark**
  (server-side filter), then advance it at the end. Most runs return little or nothing → cheap.
- **Metadata first, content on demand** — list headers/previews; read full body only for the
  messages that matched routing (known correspondent / 1:1 account).
- **Parallel across accounts, sequential within one.** Independent accounts can be checked
  concurrently; one account's pagination is serial.
- **Dedup across accounts** by global message-id — the same email can sit in both the operator
  inbox and the client inbox; ingest it once.
- **Access-gated** — skip any source whose `cred_status ≠ connected`, flag it once
  («Gmail melati — доступ не выдан»), never fail the whole run (graceful degrade, source
  dot on the overview).
- **Heartbeat per account** so a single stalled mailbox is visible, not hidden behind the rest.

## Routing (account → client)

- **1:1 / few** (`serves: [ids]`, typically a client-owned account) → straight to that client.
- **Shared** (`serves: by_correspondent`, the operator's inbox) → match each message's
  sender/recipient against the **known-correspondents map**, built once from all clients'
  `identity.contacts` + `behavior.channels` + `counterparties` + the gov/bank list
  (`connectors/email/README.md` "Known correspondents"). Unmatched → counted, not read (and
  optionally surfaced as a possible new correspondent, e.g. the `vano521@…` question).

After routing, apply via the normal `mm_update` write path at the matching confidence — the
fan-out changes only *where signals come from*, not how they become state.

## Credentials

Secrets live in `secrets/` (never in `state/`, snapshots, or git — see `policies/README.md`),
referenced by `cred` handle; the collector resolves handle → secret at run time. `cred_status`
in the registry reflects connectivity **without** holding the secret, so the registry is safe
to keep in config/state.

## Why this is the optimal approach

No redundant scans (per-account + cross-account dedup); incremental (watermark + server-side
since) so steady-state is cheap; parallelizable; **one registry reused by every channel
collector**, so onboarding a new mailbox/drive/number — or a whole new client — is a config /
`quick_access` edit with **zero collector change**. It generalizes the per-client model the
`documents` collector already uses up to the operator level.

## Who uses it

**Every channel connector, same registry:**

- `email` — operator Yandex.Mail + personal Gmail + each client's Gmail (`melati`). `access: auto`.
- `documents` — operator + client Google Drives **and** Yandex.Disks (two providers, one registry). `access: auto`.
- `whatsapp` / `telegram` — **one operator account, clients are chats within it** (`serves: by_chat`, `switch: none`): fan out over conversations, route by number/username from `behavior.channels` (e.g. WA `081200000000` → melati; TG `@vertex_tg` → vertex). No account switching.
- **Postponed but identical in shape** — `bank` (T-Bank/Alfa/Tochka/Sber/VTB/Mandiri…, each client's account a separate source, mostly `access: human_gated`, `cadence: monthly/on-demand`), `1c` (per client's 1C base, currently paused), `portal` (Coretax/BPJS/ЛК ФНС, `human_gated`). They are not new architecture — just more rows in the registry with `human_gated` access and a sparse cadence.

Each calls `enumerate_sources(<service>)` and applies the fan-out rules above.

## Related

- `config/instance.yaml → sources` — operator-level accounts.
- `state/accounts.json → quick_access[]` — client-level accounts.
- `connectors/mm_update/SKILL.md` — the write path after routing.
- `connectors/documents/SKILL.md` — the per-account incremental watermark, applied to drives.
- `docs/COVERAGE-MAP.md` — which channels each collector covers.
