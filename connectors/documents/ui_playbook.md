# Documents UI playbook — gdrive / yandexdisk / local (the HOW; learnable)

Engine **canonical, read-only at runtime**; learned Field notes → the data-dir overlay
`<data.dir>/journal/playbook_notes/<provider>.md` (`gdrive.md` / `yandexdisk.md` / `local.md`).
Actions: `connectors/documents/file_actions.md` (protocol). Structure: `connectors/_ui_playbook.md`.
Loop: `policies/skill-evolution.md`. Pipeline & switching: `connectors/documents/SKILL.md`.

## `gdrive` (MCP/credential-backed — mostly no UI)

- **`switch_account`** — select the authorized connection, or rely on **shared access** to the
  operator's account (no UI). `whoami` to verify before reading.
- **`list_folder`** — `search_files` by `parentId` + `modifiedTime > watermark`; metadata first.
- **`open_file` / `read`** — `read_file_content` (or download → parse).
- **`download`** — into the client's local folder (fetch stage). **`upload`** — 🔴 gated.

## `yandexdisk` (token / WebDAV / web)

- **`session`** — the account token (REST/WebDAV) or a dedicated browser profile; verify the disk owner.
- **`list_folder`** / **`download`** / **`upload`** (🔴 gated) — confirm the API/UI flow on first use.

## `local` (filesystem — no UI)

No web UI; still keeps a playbook of **file-handling lessons** (PDF/spreadsheet quirks, encodings,
folder layout edge cases) in `journal/playbook_notes/local.md`.

## Field notes

In the per-provider overlay (not here), keyed by primitive; corroborated lessons curated upstream
by the developer.
