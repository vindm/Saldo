# -*- coding: utf-8 -*-
"""_onboarding.py — the "Add client" call-to-action.

Parallel to _updater.py: a dashboard affordance that copies a fixed trigger
prompt for the operator to paste into Cowork; the runtime then runs the
guarded, approval-gated onboarding (connectors/onboarding/SKILL.md). The button
itself creates nothing — Saldo's runtime is the AI, the engine only renders the
view (CLAUDE.md "the main thing"). It reuses the shared prompt-modal in _css.py:
a button[data-prompt] opens the editable modal and copies ctx+body on click.

The prompt splits the way the modal's UI already does:
  - CTX  — the static, always-included task line (the "Контекст задачи" box). It
           names the task + the workflow; it never changes, so it lives outside
           the editable field where the operator might delete it by accident.
  - BODY — the default instruction in the editable textarea: let the runtime ask.
           The operator either leaves it as-is, or replaces it with concrete
           instructions (point at a folder, hand over a document). No presets —
           the textarea is the one place to express that.
The copied prompt = CTX + "\\n\\n" + BODY. Russian — the operator-facing surface
is RU (locale boundary). The SKILL carries the steps; this stays thin.
"""
from _strings import t

ONBOARD_CTX_RU = (
    "Добавь нового клиента в Saldo по workflow connectors/onboarding/SKILL.md."
)
ONBOARD_BODY_RU = "Задавай мне вопросы по одному и собери нужные данные."

# Full prompt, for reference / keeping the SKILL in sync.
ONBOARD_PROMPT_RU = ONBOARD_CTX_RU + "\n\n" + ONBOARD_BODY_RU

# CSS for the CTA. A quiet navy primary button that matches the brand accent.
ADD_CLIENT_CSS = (
    ".btn-add-client{display:inline-flex;align-items:center;gap:6px;"
    "padding:8px 15px;border:1px solid var(--accent);background:var(--accent);"
    "color:#fff;border-radius:var(--radius-btn);cursor:pointer;font-size:14px;"
    "font-weight:500;font-family:inherit;white-space:nowrap;"
    "transition:background var(--transition),box-shadow var(--transition)}"
    ".btn-add-client:hover{background:var(--accent-text);"
    "box-shadow:0 2px 8px rgba(31,78,121,0.20)}"
    ".btn-add-client .pl{font-size:17px;line-height:1;font-weight:400}"
    # Header row that holds the page title on the left, the CTA on the right.
    ".clients-head{display:flex;align-items:flex-start;justify-content:space-between;"
    "gap:var(--space-md);flex-wrap:wrap}"
)


def _attr(s):
    """Minimal HTML-attribute escape for a double-quoted attribute value."""
    return (s.replace('&', '&amp;').replace('"', '&quot;')
             .replace('<', '&lt;').replace('>', '&gt;'))


def render_add_client_cta(group=None, group_label=None):
    """A button that opens the shared prompt modal: the static task line as the
    always-included context, the editable body defaulting to "ask me".

    The CTA lives on a specific group page, so it pre-binds that group into the
    context — the runtime defaults to adding the client to the group the operator
    was viewing (the operator can still change it in the body). `group` is the raw
    key written to clients_index (e.g. "direct"), `group_label` its display name
    (e.g. «Прямые»). Wiring is the delegated button[data-prompt] handler in _css.py.
    """
    ctx = ONBOARD_CTX_RU
    if group:
        gl = group_label or group
        ctx = ctx + ' Добавь его в группу «' + gl + '» (group=' + group + ').'
    return (
        '<button type="button" class="btn-add-client" '
        'data-prompt="' + _attr(ONBOARD_BODY_RU) + '" '
        'data-prompt-ctx="' + _attr(ctx) + '">'
        '<span class="pl">+</span>' + t('Add client') + '</button>'
    )
