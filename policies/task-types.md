# Task types — the controlled vocabulary

> The runtime sets `tasks[].task_type` when it writes a task. That value — NOT the
> wording of the title — drives how the task is classified, bucketed and rendered.
> The title is human prose for the operator (Mom); never rely on it for meaning.
> This file is the human reference for **how to pick a type**. The machine source of
> truth is `engine/_track_attrs.py → _TASK_TYPE_LABEL` (every valid type + its
> label); `state_lint` (`i18n_task_type`) rejects any type not in that map.

## How a type becomes a wave / bucket

`engine/_plan_waves._op_canonical(task)` resolves the operation in this order:

1. **Pipeline stage** — if the type is a stage of the client's jurisdiction pack
   (`jurisdictions/<j>/cycles/*.yaml` + `pipeline.yaml`), it becomes a period-anchored
   cycle stage (`stage:<code>|<period>`). Resolved against the **client's**
   jurisdiction, so a RU «Закрытие месяца» and an ID `monthly_close_pt` are different
   operations — they do not merge, by design.
2. **Process / generic type** — re-inferred from the title by keyword
   (`_OP_KEYWORDS`). These types are statuses/processes, not operations.
3. **Otherwise** — the type itself is the operation.

Grouping is **by operation only**. Group (Команда/Прямые) and **jurisdiction** are
attributes of each member and act as filters, NOT batching axes — the same operation
spans clients of any group and any jurisdiction in one wave. Jurisdiction enters the
key **only** for pipeline stages (case 1), because there the operation is itself
defined by the jurisdiction.

## Categories

### Operations (reusable) — always form their bucket, even with one member
`primary_collection`, `kudir_posting`, `posting_1c`, `technical_1c`, `ndfl_register`,
`balance_reconciliation`, `ens_reconciliation`, `ausn_reconciliation`,
`ausn_markup_review`, `ausn_bank_marking`, `sz_checks_reconciliation`,
`service_payment`, `acquiring_reconciliation`, `bank_check`, `kkt_check`,
`declaration`, `statreport`, `regular_check`, `tax_pp`, `pp_to_form`, `notification`,
`sign_pay`, `pp_sign`, `month_close`, `period_close`, `month_audit`, `patent`,
`client_followup`.

These read as the same operation on every client, so a lone one still lands in its
bucket (e.g. a single «Запрос у клиента» or «Оплата услуг клиентом»), identically on
the Plan, a calendar day and a client card.

### Process / status types — re-inferred from the title by keyword
`awaiting_external`, `awaiting_external_then_action`, `other`, `investigation`,
`infrastructure`, `long_term_parallel`, `multi_step_preparation`, `preparation`,
`strategic_decision`, `monitoring`, `documentation`, `team_conversation_required`,
`extraction`, `finkoper_recurring`.

A `review_checkpoint` is also a process marker (a control point), not an operation —
type the underlying work, not the «Контроль …» framing.

### Mode types — describe HOW you interact, not WHAT the work is
- `client_followup` — «Запрос у клиента». The standing bucket for asking / chasing
  the client. `access_request` and `data_request` alias into it.
- `client_action` — waiting on the client to do something.

Mode is the interaction state, often better carried by `status`
(`active`/`awaiting`/`deferred`) than by the type. Do not type an operation by its
mode (see Rules).

### Inquiry / annotation — NOT operations
`open_question`, `regime_question`, `note`. A question that merely mentions an
operation in its text is still a question.

### Pipeline / cycle stages — defined in the jurisdiction packs
Not redefined here. See `jurisdictions/<j>/cycles/*.yaml` and `pipeline.yaml`
(RU: `primary_collection` → `posting_1c` → `month_close` → `month_audit` → `tax_pp`
→ `sign_pay`; plus feeders and the `tax_quarterly` / `payroll` / `ausn_monthly`
cycles). ID pack has its own (`compute_final_pph`, `payroll_pph21_bpjs`,
`spt_masa`, …).

## Rules for picking a type (see INSTRUCTIONS.md §0.4)

- **Type by the operation, not the mode or the framing.** «Контроль оплаты услуг» /
  «Проверить оплату услуг» → `service_payment` on every period, whether you are
  actively chasing or just waiting — the wait lives in `status`, not the type.
- **A control point resolved by asking the client** («уточнить у …», «спросить у …»)
  IS «Запрос у клиента» → `client_followup`, not `review_checkpoint`.
- **`service_payment` is a PRACTICE operation** — Irina's own fee, the same for a RU
  client and a Bali (ID) client. It is jurisdiction-agnostic and batches across
  jurisdictions in one wave. (Planned: a practice-level quarterly cycle so it also
  shows on the Periods page across jurisdictions.)

## Lint guards
- `i18n_task_type` — every `task_type` must exist in `_TASK_TYPE_LABEL` (no silent new
  types without a label).
- `op_type_mismatch` — a curated set of strong title phrases (`_OP_TITLE_SIGNALS`,
  seeded with «оплата услуг» → `service_payment`) flags a task whose title reliably
  names an operation while its type says otherwise. Curated on purpose: an incidental
  token (e.g. «ЛК АУСН» in an access request) must never be read as that operation.
