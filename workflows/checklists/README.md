# Checklists moved into jurisdiction packs

Tax procedures are jurisdiction-specific, so checklists now live inside the
jurisdiction pack that owns them, not here:

    jurisdictions/<code>/checklists/<task_type>.md

The RU checklists (formerly in this folder) are now in
`jurisdictions/ru/checklists/`. The runtime never opens a checklist by a fixed
path: per `policies/INSTRUCTIONS.md` §0 it resolves the client's jurisdiction,
loads `jurisdictions/<code>/manifest.yaml`, and takes the checklist for the task
type from the pack's `checklists:` map. A task type with no checklist in the
client's pack does **not** apply in that jurisdiction — surface it, never fall
back to RF procedures.

Genuinely jurisdiction-neutral material (brand/tone, generic message structure)
stays under `workflows/templates/` and `policies/brand-and-tone.md`.
