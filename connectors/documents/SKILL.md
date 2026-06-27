# Skill: documents — cloud document collector (Google Drive + Yandex.Disk), incremental

Ingests **primary documents** — bank statements, sales/POS reports, invoices, acts, payroll
registers — into state, **without re-scanning the archive**. Sources are cloud folders (Google
Drive, Yandex.Disk) **and a local inbox** the operator drops files into. For some clients the
cloud folder is the *only* inbound channel; the **local inbox** is also how the operator hands
the system a document it asked for (a rung-3 "needs a document" question — see below).

> **Why this is the highest-leverage collector.** `melati` (Indonesia) runs entirely
> through Google Drive: its **Mandiri statements arrive as PDFs in Drive**, its Moka sales and
> invoices too. This one collector therefore delivers the ID client's bank + revenue + invoice
> data **without** a Mandiri bank API or any Indonesian portal — it is the practical unlock for
> the whole `id` jurisdiction, and the pattern the Bali salon will reuse. RU clients who send
> primary docs to a Yandex.Disk/Drive folder are covered by the same skill.

## Pipeline — fetch into the local folder, then ingest from it

Documents flow through the client's **local folder** (its `docs_root/docs_folder` on the
operator's machine) as the single store and seam:

1. **Fetch (sync down).** Cloud sources — Google Drive / Yandex.Disk (and, later, email
   attachments) — **download new files into the client's local folder**, incremental by the
   cloud **download watermark** (each cloud file pulled once). Where to put it is the client's
   own mapping: its `quick_access` cloud folder → its `docs_root/docs_folder` local folder.
2. **Ingest (read up).** The `local` provider reads each client's local folder for files newer
   than the **ingest watermark**, classifies them, and applies to state via `mm_update`. This is
   the **single ingest path** — a downloaded statement and a **manually-dropped** file are read
   identically.

So cloud mirrors *into* local, the operator can also drop straight *into* local, and everything
is ingested *from* local. The local folder is the archive (resilient, offline-readable) and the
drop-point for the rung-3 return-path. The two watermarks are independent: **download** (cloud →
local) and **ingest** (local → state).

## Per-client config (where to look)

Driven by `state/accounts.json → quick_access[]`, never hardcoded:

- `service: "gdrive"` or `service: "yandexdisk"` → the provider.
- `url` → the **folder** to watch (e.g. melati's Accounting folder, with sub-folders
  `bank statements/<month>`, sales, invoices).
- `cred_status` → `connected` / `missing` / `after_first_billing`. **If not `connected`, skip
  this client+provider and flag it** ("Yandex.Disk доступ не выдан — запросить") — degrade
  gracefully, never fail the run. (This is the "check access first" rule.)

A client with no `gdrive`/`yandexdisk` quick-access is simply out of scope.

**Multi-account fan-out (`connectors/_sources.md`).** `gdrive` and `yandexdisk` are two
providers of the same registry: this collector runs `enumerate_sources("gdrive") ∪
enumerate_sources("yandexdisk")` — operator-owned drives from `config → sources` **plus** every
client's drive from `quick_access` — one incremental pass per account (own watermark), deduped,
`access: auto`. Adding a client's drive is a `quick_access` edit, no change here.

## Incremental watermark — the optimal-check rule (do NOT re-scan)

This governs the **fetch stage** (cloud → local download). The `local` provider keeps its own
separate **ingest watermark** (local → state) — see "Local folders" below.

Per **client + provider + folder**, keep a watermark = the max `modifiedTime` seen last run
(`journal/finkoper_state/documents/<client>_<provider>.json`, alongside the heartbeat). Each
run:

1. **List server-side by modifiedTime > watermark only.** GDrive: `search_files` with
   `modifiedTime > '<watermark>' and parentId = '<folderId>'`. Yandex.Disk: the API/WebDAV
   `last-modified` filter on the folder. This returns *just the new/changed files* — most days,
   nothing (cheap; the daily cost the bank collectors avoid does not arise here).
2. **Metadata first, content only when needed.** Decide from `title`/`mimeType`/`size`/folder
   whether a file is a document to ingest; **download/read content only for those**. Skip
   thumbnails, dupes, non-documents.
3. **Dedup by `fileId` + `modifiedTime`** against a small processed-index, so a re-run or a
   touched-but-unchanged file is never re-ingested.
4. **Folder-scoped.** Walk only the declared sub-folders (statements / sales / invoices /
   payroll), not the whole drive.
5. **Advance the watermark** to the new max `modifiedTime` at the end (only after successful
   processing), and write the heartbeat.

Backends are abstracted behind these five steps: GDrive uses the `gdrive` MCP tools; Yandex.Disk
uses its REST/WebDAV connector when present (if absent, flag "Yandex.Disk коннектор не
подключён" and skip — graceful).

## Classify & route (then feed mm_update)

For each new document, classify by folder + filename + content, and apply via the normal
`mm_update` write path (`state_ops`/`_tracks`) at the matching confidence:

| Document | Routes to | Example |
|---|---|---|
| Bank statement (incl. **Mandiri**) | `accounts.json` (issuer/branch) + turnover into `financials.json` | the melati Mandiri PDF → bank facts + monthly oborot |
| Sales / POS report (Moka, retail) | `financials.json` revenue for the period | Moka monthly sales |
| Invoice / act | `counterparties.json` (new/again) + the period's docs | a new B2B invoice |
| Payroll register | `financials.json` / payroll + BPJS basis (ID) | monthly payroll |
| Contract | `counterparties.json` / `real_estate.json` | a lease / service contract |
| **Payment receipt** (proof of a tax payment, bank / portal) | `financials.json → tax_calendar_<year>[]`: close the matching entry | a tax receipt PDF → entry `paid` |

### Payment-receipt capture — close a deadline with its proof (the deadline_monitor loop)

A **payment receipt** carries the reference proving a tax was paid — the
**`payment_ref`** (jurisdiction-neutral field; the local term is a gloss: ID = **NTPN**,
RU = **платёжное поручение № / ЕНС operation**). When one lands:

1. **Match** it to the `tax_calendar_<year>[]` entry for that **period (masa)** and tax — by the
   amount + period in the receipt against the entry's `what`/`amount`/`date`.
2. **Close it** (via `mm_update`/`state_ops`, read-modify-write): set `status: "paid"`,
   `paid_at` = the receipt date, and **`payment_ref`** = the receipt reference (a list when the
   date bundles several billings — e.g. ID PP55 + PPh 21 + unifikasi, one NTPN each; slot from
   migration `0018`).
3. The `deadline_monitor` then **drops** the now-terminal entry automatically (it skips
   `paid`/`done`) — so a deadline it surfaced closes itself once the proof arrives, no operator
   step. The recorded `payment_ref` also pre-fills the annual return (e.g. ID SPT Tahunan Badan —
   all 12 masa paid).

Recording an incoming receipt is a state *read-in* (mm_update §5a) — **no approval**; paying is
the operator/client action, never the collector. If the receipt can't be matched to an entry
confidently, surface it for confirmation — never flip an unrelated deadline.

- **High & objective** (a statement's issuer, a clear total) → apply directly.
- **Partial / needs interpretation** → apply what's certain, surface for confirmation (do not
  guess a reconciliation).
- **Unparseable / ambiguous** → create/refresh a tracked item so `question_resolver` or the
  operator picks it up; record what was found.

Resolve the client's **jurisdiction first** (INSTRUCTIONS §0) — a Mandiri statement is read in
Indonesian terms (IDR, peredaran bruto), never RF defaults.

## Output, audit, visibility

- New docs of the day → `journal/inbox/documents_<date>.json` (per-client list, for the
  dashboard source dot).
- Real changes → `journal/operator_decisions.md` (mm_update audit), and the morning brief
  ("🌙 За ночь: melati — подтянул январскую выписку Mandiri и продажи Moka").
- Heartbeat + watermark at end. A missing expected file (e.g. the monthly statement never
  arrived) is **not** this collector's job to flag — that is the `staleness_monitor` (C8).

## Local folders (provider: `local`) — the operator's per-client document folders

The operator (Mom's laptop) already keeps a **local document folder per client** — declared in
`clients_index.json` as `docs_root` + `docs_folder` (+ `group`), under a base path in
`config → sources.local`. There is **no separate inbox**; the client's own folder *is* the drop
point and the archive:

- **team** clients → `<base>/РАБОТА/ИП <Name>/`
- **direct** clients → `<base>/КЛИЕНТЫ/КЛИЕНТЫ {year}/<Name>/` (resolve `{year}`)
- `melati` → `<base>/КЛИЕНТЫ/MELATI SPA (Бали)/`

The `local` provider watches each client's resolved folder. No auth, no switching (`access:
auto`, `switch: none`); the engine reads the filesystem directly.

- **Routing is inherent** — the folder *is* the client (from the index). No filename/content
  guessing, no "unassigned" bucket: a file in `ИП Cirrus/` is Cirrus's.
- **Incremental by mtime watermark** (same as the cloud providers), **not** move-to-processed —
  these are the client's **permanent** folders, so never move or delete the operator's files;
  track processed by `journal/finkoper_state/documents/<client>_local.json` (max mtime seen).
- **Classify & apply** exactly as the cloud path (statement → accounts/turnover, invoice →
  counterparties …), via `mm_update`, jurisdiction-resolved first.

> ⚠️ **No `_Inbox` / `operator_inbox` subfolder.** Files are read straight from the client's
> document folder; the project does **not** use a per-client `_Inbox` drop subfolder. (If a
> client folder has a known sub-structure to scope or skip, declare it per the index, not a
> hardcoded inbox.)

### 🔴 Resolving a "needs a document" question (the rung-3 loop)

When `question_resolver` (or a collector) marks a question **rung-3 — "needs a document only a
person has"** (e.g. «нужна справка об остатке ипотеки», «договор от клиента»), the operator
satisfies it by **dropping that file into the client's local folder** (or its cloud folder). On
the next run the collector ingests it, applies the fact, and — because it now answers an open
question — **links and closes that question** (status `done`, `source='local:<file>'`, history
«получен документ от оператора»), per the mm_update §7.5 cross-link reconciliation. So the local
folders are the return-path that turns a rung-3 question into a closed one.

## Account switching (per provider)

Runs once per drive in `enumerate_sources("gdrive") ∪ enumerate_sources("yandexdisk")`. Make
the account active per its `switch` mode, then **verify before reading** (read back the
connected account / disk owner; confirm the target folderId is reachable — on mismatch, stop
and flag).

**Google Drive** (`provider: gdrive`, MCP/credential-backed, `switch: cred/connection`):
- An account = a distinct authorized `gdrive` connection. "Switching" = using the connection
  bound to that Google account — **no UI**.
- **Prefer shared access over per-account auth:** a single operator connection already sees any
  folder **shared with** it. `melati`'s Accounting folder is owned by
  `melatispa@example.com` yet reachable because it is shared to the connected account — so no
  switch is needed, just confirm the folderId lists. Authorize a separate connection only when a
  client's folder cannot be shared.
- **Verify:** the connected account (connector whoami) + a successful metadata list of the
  target folderId before reading any file.

**Yandex.Disk** (`provider: yandexdisk`, credential/login-backed):
- Switching = that account's token (WebDAV / REST app-password) or a dedicated browser profile —
  no in-session mid-run switching. **Verify:** the disk owner / a successful list of the watched
  folder.

> Registry, per-folder watermark, routing and dedup live in `connectors/_sources.md`.

## Safety

- **Read-only acquisition** — listing/reading files needs no approval (mm_update §5a). The
  collector **never writes to the client's drive**.
- **No secrets** in state or logs; respect `cred_status` (skip + flag if not connected).
- Credentials/2FA wall on a provider → stop for that provider, flag, continue with the rest.

## Cadence

**Daily.** Incremental listing returns nothing on most days (statements land in the first days
of the month), so the run is cheap — unlike the credentialed bank/portal collectors, this needs
no 2FA and hits a single cheap list call per folder. Declared in `config/instance.yaml →
schedule` as `documents`.

## Atomic file actions & UI playbook

For a single op (not the sweep) — `list_folder` / `read_file` / `download_file` / `upload_file`
(upload is outbound, approval-gated) — see `connectors/documents/file_actions.md`. Provider UI
mechanics (gdrive/yandexdisk/local) are in `connectors/documents/ui_playbook.md`, which
self-corrects via the loop (`policies/skill-evolution.md`); learned notes →
`journal/playbook_notes/<provider>.md`.

## Related

- `connectors/documents/file_actions.md` — atomic list/read/download/upload.
- `connectors/mm_update/SKILL.md` — the write path + rung/confidence logic.
- `docs/COVERAGE-MAP.md` — G1 (this) and the rest of the gap register.
- `connectors/question_resolver/SKILL.md` — picks up the ambiguous docs this leaves tracked.
- `policies/INSTRUCTIONS.md §0` — resolve jurisdiction before reading an ID statement.
- `tests/runtime_scenarios/` — S7 is the gate for this behaviour.
