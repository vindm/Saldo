# Atomic file actions — documents (gdrive / yandexdisk / local)

The **single-file** operations on a client's document store, so neither a daemon nor the runtime
improvises. Provider mechanics (auth, switching, the two-stage download→ingest pipeline) are in
`connectors/documents/SKILL.md`; this file is the **actions**. Used by the collector (the sweep
calls `list_folder` + `read_file`) and **ad-hoc by the runtime** — «возьми майскую выписку
клиента», «загрузи этот PDF в его папку».

**Resolve the folder first.** Local → `clients_index.json` `docs_root/docs_folder` (+ `{year}`);
cloud → the client's `quick_access`. **Verify the connected account / folder** (whoami; a
successful list of the target folderId) before reading — the cross-client guard.

## `list_folder(client, [provider], [subpath])` — read-only

List files in the client's folder (name, mtime, size, type). No approval. Use to find a file or
see what's new. Prefer the **local** folder (it mirrors cloud + holds manual drops).

## `read_file(client, file)` — read-only

Read/parse a file's content (PDF text, spreadsheet, image) for analysis. No approval. Prefer the
local copy if synced; else read the cloud file. If it answers an open item, apply via `mm_update`.

## `download_file(client, file, [dest])` — read-only acquisition

Download a **cloud** file into the client's **local** folder (the pipeline's fetch stage). No
approval (read-only acquisition). Dedup by `fileId`; advance the download watermark; never
re-pull an already-synced file.

## `upload_file(client, file, dest)` — 🔴 OUTBOUND, APPROVAL-GATED

Writing **into** the client's drive (or placing a prepared report in a folder the client sees) is
outbound. **Show the operator what + where; upload only on an explicit "upload / загрузи".**
Never overwrite an existing file without confirmation. Log via `mm_update`. Daemons never upload.

## Safety

| Action | Approval |
|---|---|
| `list_folder` / `read_file` / `download_file` | none (read-only) |
| `upload_file` | **operator's explicit go** |

## Related

- `connectors/documents/SKILL.md` — pipeline, per-provider switching, watermarks.
- `connectors/_sources.md` — registry; `connectors/mm_update/SKILL.md` — write path + outbound gate.
