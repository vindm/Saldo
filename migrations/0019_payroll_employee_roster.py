"""Create `state/payroll.json` — the per-employee roster slot — for clients that run payroll.

Today payroll is modelled at the COMPANY AGGREGATE: the `id` monthly close sums PPh 21
across employees and pays one BPJS billing, but there is no per-employee entity in state.
That blind spot is exactly the failure mode a foreign-worker risk review surfaces: a worker
**missing from a BPJS billing** (a UU 24/2011 violation) cannot be detected by the engine,
because there is no roster of "who should be covered" to reconcile the billing against. Nor
can the engine reason about per-person facts that drive the tax — tax residency (the 183-day
test, which flips withholding from PPh 21 to PPh 26), the PPh 21 method (annualisasi vs flat
TER), or a foreign worker's permit expiry (RPTKA/KITAS).

This migration opens the slot. For every client that runs payroll
(`regime.json → has_employees == true`) and has no `payroll.json` yet, it creates:

    state/payroll.json = {
        "schema_version": "1.0",
        "client_id":      "<id>",
        "employees":      []          # filled by the operator/runtime, not here
    }

Per-employee record shape (documented here; the migration seeds NONE of it — employee data
is real per-operator data and is written later via state_ops, following
`jurisdictions/id/checklists/payroll-pph21-bpjs.md`):

    employees[] = {
      "id":               str,    # stable local id, e.g. "emp_<slug>"
      "name":             str,    # operator-facing display name (real data — never here)
      "foreign_national": bool|null,            # drives the TKA + residency rules
      "tax_residency":    "id"|"non_id"|null,   # outcome of the 183-day test
      "pph_method":       "ter"|"annualisasi"|"pph26"|null,
      "bpjs": { "kesehatan": "active"|"missing"|"exempt"|null,
                "ketenagakerjaan": "active"|"missing"|"exempt"|null },
      "permit": { "kitas_expires": ISO|null, "rptka_expires": ISO|null,
                  "dpkk_paid": bool|null }      # foreign worker only
    }

Additive + behaviour-preserving: NO engine render path reads `payroll.json` yet (only the new
`state_lint` section H3 does, and it is pack-declared + opt-in), so dashboards stay
byte-identical after applying this — verified by a clean generate. The roster is created
EMPTY; a client whose `has_employees` flag is true but whose roster is still empty is then
nudged by the lint (`payroll_roster_empty`) to populate it.

Idempotent: a client that already has `payroll.json` is skipped, so a partial or repeated run
is a no-op. Schema-level — keyed purely on the `has_employees` flag and file/field names, no
client names, no employee data, no amounts — so the file carries ZERO real data and is safe in
the public repo. Mirrors the new-file pattern of 0013 (`brief.json`) and the additive-slot
pattern of 0011 / 0017.
"""

ID = "0019"
DESCRIPTION = ("create payroll.json {employees: []} for clients with regime.has_employees=true "
               "and no roster yet (per-employee BPJS/permit/residency slot). Additive, "
               "behaviour-preserving.")


def up(api):
    for cid in api.clients():
        reg = api._ops.state_read(cid, "regime.json")
        if not isinstance(reg, dict) or reg.get("has_employees") is not True:
            continue  # not a payroll client — nothing to open

        existing = api._ops.state_read(cid, "payroll.json")
        if isinstance(existing, dict) and "employees" in existing:
            continue  # roster slot already present — idempotent no-op

        data = {"schema_version": "1.0", "client_id": cid, "employees": []}
        api._commit(cid, "payroll.json", data,
                    "create payroll.json employee-roster slot (empty)")
