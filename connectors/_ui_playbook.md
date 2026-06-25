# Convention: per-provider UI playbook (the HOW; learnable)

Each web-app provider has a `connectors/<x>/ui_playbook.md` — the **concrete steps to operate that
web app**, so the runtime follows them instead of improvising the clicks. The shared files
(`_chat_actions.md`, `_chat_collector.md`, `_sources.md`) hold **protocol + safety** (the WHAT);
this is **mechanics** (the HOW). Generic instructions cause UI mistakes — playbooks are specific,
and they differ per provider **down to each primitive**.

## Organised by granular UI primitive

A playbook documents each **primitive** the atomic actions need. The steps **and the lessons**
differ per provider:

| Primitive | What it does | Why it differs per provider |
|---|---|---|
| `session` | verify logged-in; recognise the login/QR screen | QR scan (WhatsApp) vs token (Yandex.Disk) vs `/a/` session (Telegram) |
| `jump_to_chat` | open a **specific** conversation | search box vs `#peer_id` URL vs contact list |
| `scroll` / `load_history` | load older messages/items | virtualised list, lazy-load, pagination all differ |
| `read_messages` | extract the visible messages | DOM layout; mark-as-read side effect (WA/Max) |
| `attach` | add a file to a message | clip-icon location & flow |
| `send` | submit the message | button vs Enter; new-contact confirm dialog |
| `download_file` | save a file / media | right-click vs icon vs API/export |
| `upload_file` | put a file into the store | drag-drop vs picker vs API |
| `detect_success` | confirm the action happened | sent-tick / message id / page state |
| `quirks` | provider gotchas | — |

Drives/portals get their own primitives (`list_folder`, `open_file`, `download`, `upload`, …);
banks add `login_2fa`, `select_account`, `export_statement`.

## Canonical here (engine), learned notes in the data dir

This file holds the **canonical** steps and is **engine code — read-only at runtime**. Learned
**Field notes** are written to the per-instance overlay `<data.dir>/journal/playbook_notes/<provider>.md`
(per `policies/skill-evolution.md`) — **the running instance never edits this file**. The runtime
**composes** canonical steps + the overlay (overlay wins for a primitive it has corrected). Notes
are keyed to their primitive, e.g. —
> `jump_to_chat`: the search result isn't clickable until the header updates (~300 ms); wait,
> then click. *(learned 2026-…, corroborated)*

So lessons accrue exactly where they apply (per primitive), in the operator's data — not in the
public engine.

## Every web-driven provider gets one — not just chats

Any provider the runtime operates through a web UI has a `ui_playbook.md`, each with its **own**
primitives and lessons:

- **chats** (`tg`/`whatsapp`/`max`) — `jump_to_chat`, `scroll`, `read`, `attach`, `send`, `download`.
- **cloud drives** (`gdrive`/`yandexdisk`) — `list_folder`, `open_file`, `download`, `upload`, `switch_account`.
- **email web** (`yandex`/`gmail`) — the read atomics + the reply/compose box, `switch_account`.
- **banks** (`tbank`/`alfa`/`sber`/`vtb`) — `login_2fa`, `select_account`, `set_date_range`, `export_statement`.
- **portals** (`egrul`, `websbor`, `coretax`, `bpjs`, ЛК ФНС) — `search_by_key`, `open_card`, `export`/`submit`.
- **OFD** — `open_kassa`, `export_z_report`.

**Some already exist under other names — recognise and migrate them, don't duplicate:**
`connectors/egrul/egrul_vypiska_workflow.md` is the egrul.nalog.ru playbook;
`connectors/{tbank,alfabank}/get_statement.md` are bank-export playbooks;
`workflows/templates/chrome-instruction-template.md` is the generic browser-driving scaffold.

**Coverage — every active provider has a canonical playbook + a data-dir overlay; none is
special:** `whatsapp` ✓, `tg` ✓, `max` ✓ (unverified scaffold), `documents` (gdrive/yandexdisk/
local) ✓; `egrul`/`bank` ✓ (de-facto: `egrul_vypiska_workflow.md`, `get_statement.md`). Still to
add as those providers come online: email-web (yandex/gmail), the non-direct bank portals,
Coretax/BPJS. **All of them evolve by the same loop** — a stub starts approximate and self-corrects
via its overlay; nothing stays hand-maintained-only.

## When the playbook is wrong or missing

Run the **recover + capture** loop (`policies/skill-evolution.md`): observe the live page,
accomplish the goal, append a Field note **to that primitive** in the data-dir overlay
(`<data.dir>/journal/playbook_notes/<provider>.md`), not this engine file. Never silently repeat a
failing step. Promotion of a note into a canonical engine step is two-tier (instance-local
corroboration → developer curates upstream + version + scenario).

## Provenance

Each Field note: `date · trigger · the working step · evidence · status (tentative | corroborated | promoted)`.

## Related

- `policies/skill-evolution.md` — the learning loop + safeguards (mechanics evolve, safety doesn't).
- `connectors/_chat_actions.md` — the immutable protocol layer these mechanics serve.
