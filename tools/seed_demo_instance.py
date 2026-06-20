#!/usr/bin/env python3
"""Seed a DEEP, fully synthetic demo instance for screenshots / onboarding.

Not wide, but deep: ~7 fabricated clients, 5 batchable operations (waves) + 5
standalone tasks, full-fidelity tasks (multi-event history, an AI hypothesis with
recommended actions), open questions with hypotheses, a "Waiting" lane, risks,
two red clients (one via a monthly-close blocker, one via a high anomaly), and the
morning collectors (news / mail / updates / anomalies + a practice-management
snapshot) so the dashboard digest is populated.

All data is INVENTED — no real personal, financial, or tax data. English.
Dates are relative to today, so re-running refreshes the demo to "today".

Run from the repo root:  python3 tools/seed_demo_instance.py
"""
import json, os, glob
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "instances", "example", "data")
TODAY = date.today()


def d(off):
    return (TODAY + timedelta(days=off)).isoformat()


# ---- clients: (id, short, full, group, regime_type, object, rate) -----------
CLIENTS = [
    ("aurora",   "SP Aurora Bakery",    "Aurora Maxwell",   "direct", "USN",  "income",         6),
    ("meridian", "SP Meridian Crafts",  "Celeste Okonkwo",  "direct", "USN",  "income",         6),
    ("harbor",   "SP Harbor Press",     "Diego Navarro",    "direct", "USN",  "income_expense", 15),
    ("lumen",    "SP Lumen Studio",     "Farid Haddad",     "direct", "AUSN", "income",         8),
    ("northwind","SP Northwind Studio", "Bruno Castellano", "team",   "USN",  "income",         6),
    ("cobalt",   "SP Cobalt Metalwork", "Ivana Petrova",    "team",   "USN",  "income_expense", 15),
    ("vertex",   "SP Vertex Media",     "Jamal Idris",      "team",   "AUSN", "income",         8),
]

# ---- tasks: (client, suffix, title, task_type, status, priority, due, period, amount)
# Optional richness (history / assist) is attached in RICH below, keyed by id.
T = [
    # Wave 1 — Month close · April (overdue, red) — spans direct + team (one bar)
    ("aurora",   "mc04", "Close April 2026 in the ledger (6 regulated ops)", "month_close", "active", "high",   d(-4), "2026-04", None),
    ("meridian", "mc04", "Close April 2026 in the ledger (6 regulated ops)", "month_close", "active", "normal", d(-4), "2026-04", None),
    ("harbor",   "mc04", "Close April 2026 in the ledger (6 regulated ops)", "month_close", "active", "normal", d(-4), "2026-04", None),
    ("cobalt",   "mc04", "Close April 2026 in the ledger (6 regulated ops)", "month_close", "blocked","high",   d(-4), "2026-04", None),
    # Wave 2 — Calc + notice + payment order · June (amber)
    ("aurora",   "pp06", "June advance: notification + payment order", "pp_to_form", "active", "high",   d(5), "2026-06", 19000),
    ("meridian", "pp06", "June advance: notification + payment order", "pp_to_form", "active", "normal", d(5), "2026-06", 16500),
    ("harbor",   "pp06", "June advance: notification + payment order", "pp_to_form", "active", "normal", d(5), "2026-06", 14300),
    # Wave 3 — Sign / pay · June (amber)
    ("meridian", "ps06", "Sign the payment order in the bank", "pp_sign", "awaiting", "normal", d(6), "2026-06", None),
    ("harbor",   "ps06", "Sign the payment order in the bank", "pp_sign", "awaiting", "normal", d(6), "2026-06", None),
    ("lumen",    "ps06", "Sign the payment order in the bank", "pp_sign", "awaiting", "normal", d(6), "2026-06", None),
    # Wave 4 — Acquiring · recurring (team, single client, 2 tasks)
    ("vertex",   "acq1", "Acquiring confirmation to the bank — June", "acquiring_reconciliation", "active", "normal", d(4),  None, None),
    ("vertex",   "acq2", "Acquiring confirmation to the bank — July", "acquiring_reconciliation", "active", "normal", d(25), None, None),
    # Wave 5 — Client service payment (blue)
    ("aurora",   "sp", "Fee control — Q2 2026 (postpaid)", "service_payment", "awaiting", "normal", d(15), None, 5000),
    ("meridian", "sp", "Fee control — Q2 2026 (postpaid)", "service_payment", "awaiting", "normal", d(15), None, 5000),
    ("harbor",   "sp", "Fee control — Q2 2026 (postpaid)", "service_payment", "awaiting", "normal", d(15), None, 5000),
    ("lumen",    "sp", "Fee control — Q2 2026 (postpaid)", "service_payment", "awaiting", "normal", d(15), None, 5000),
    # 5 standalone tasks (one-offs, distinct operations)
    ("harbor",   "pc05", "May source documents (expense invoices)", "primary_collection", "awaiting", "normal", d(-3), "2026-05", None),
    ("cobalt",   "ndfl", "Payroll-tax register for the period", "ndfl_register", "blocked", "normal", d(4), None, None),
    ("northwind","bk",   "Get the bank statement (Q2 package)", "bank_check", "active", "normal", d(2), None, None),
    ("vertex",   "amr",  "AUSN — review the marking of May operations", "ausn_markup_review", "active", "normal", d(8), "2026-05", None),
    ("lumen",    "ens",  "Reconcile the single tax account for Q2", "ens_reconciliation", "active", "normal", d(25), None, None),
    # Waiting lane (passive: monitoring + dateless awaiting)
    ("lumen",    "mon",  "Monitor the bank's reaction to new payees (after the recent hold)", "monitoring", "awaiting", "normal", None, None, None),
    ("northwind","aw1",  "Awaiting the client's decision on acquiring with fiscalization", "awaiting_external", "awaiting", "normal", None, None, None),
]

# Open questions (Dashboard block) — (client, suffix, title, priority)
Q = [
    ("aurora",   "q1", "Confirm the webshop revenue OKVED is registered", "high"),
    ("harbor",   "q1", "Status of the bank loan (schedule + balance)?", "normal"),
    ("cobalt",   "q1", "Reason for the -40% revenue dip vs last year?", "high"),
    ("vertex",   "q1", "Which 1C base (Fresh or local) and when set up?", "normal"),
    ("lumen",    "q1", "Bank-acquirer and tariff?", "normal"),
    ("meridian", "q1", "Which email is the working one — A or B?", "normal"),
]

# Rich detail (history + assist) keyed by "<client>_<suffix>"
RICH = {
    "aurora_mc04": {
        "context": "April close is the last open monthly period; 6 regulated operations remain after the bank statement was posted on 14.06.",
        "next_action": "Run the 6 closing operations in 1C, then re-check the balance.",
        "history": [
            {"date": d(-19), "event": "Period opened for April close.", "kind": "status_change", "auto": True},
            {"date": d(-6),  "event": "Client sent the missing April invoices via Telegram.", "kind": "reply", "auto": False},
            {"date": d(-2),  "event": "Bank statement for April posted; 2 of 6 closing ops done.", "kind": "posting", "auto": False},
        ],
        "assist": {
            "hypothesis": "Ready to finish — the inputs are in. The remaining 4 ops are mechanical; no client action needed.",
            "confidence": "high", "updated_at": d(-1),
            "actions": [
                {"label": "Run the close", "prompt": "Close April for SP Aurora Bakery: run the remaining 4 regulated operations in 1C and re-check the balance.", "recommended": True},
                {"label": "Show the checklist", "prompt": "Show the month-close checklist for SP Aurora Bakery and where we are."},
                {"label": "Defer 2 days", "prompt": "Defer the April close for SP Aurora Bakery by 2 days with a reminder."},
            ],
        },
    },
    "aurora_pp06": {
        "context": "June advance for USN 6%. The client asked for the exact figure today (see the morning mail).",
        "next_action": "Confirm the advance amount, draft the notification + payment order.",
        "history": [
            {"date": d(-3), "event": "Quarterly pace recalculated; advance estimate ~19,000.", "kind": "calc", "auto": False},
            {"date": d(0),  "event": "Client emailed asking for the exact figure before noon.", "kind": "reply", "auto": False},
        ],
        "assist": {
            "hypothesis": "The estimate (19,000) is solid; reconcile it against the latest bank inflow before confirming to the client.",
            "confidence": "medium", "updated_at": d(0),
            "actions": [
                {"label": "Draft the figure + PO", "prompt": "For SP Aurora Bakery, reconcile the June USN advance against the latest statement and draft the notification + payment order.", "recommended": True},
                {"label": "Reply to the client", "prompt": "Draft a short reply to SP Aurora Bakery confirming the June advance amount."},
            ],
        },
    },
}

# Assist for the open questions (hypothesis + recommended action)
Q_ASSIST = {
    "aurora_q1": {
        "hypothesis": "The webshop activity is very likely covered by the existing additional OKVED 47.91; worth a 1-minute EGRIP check before the next close.",
        "confidence": "medium", "updated_at": d(-2),
        "actions": [
            {"label": "Check & close", "prompt": "Check the EGRIP extract for SP Aurora Bakery; if 47.91 is present, close this question.", "recommended": True},
            {"label": "Ask the client", "prompt": "Ask SP Aurora Bakery to confirm which OKVED codes are registered."},
            {"label": "Defer a quarter", "prompt": "Defer the OKVED question for SP Aurora Bakery with a wake-up next quarter."},
        ],
    },
    "cobalt_q1": {
        "hypothesis": "The drop tracks a lost wholesale buyer in Q1; not a data error. Re-estimate the annual pace and the advance.",
        "confidence": "medium", "updated_at": d(-3),
        "actions": [
            {"label": "Re-estimate pace", "prompt": "Re-estimate SP Cobalt Metalwork's 2026 annual pace and June advance given the revenue drop.", "recommended": True},
            {"label": "Ask the client", "prompt": "Ask SP Cobalt Metalwork whether the revenue drop is expected to continue."},
        ],
    },
}

RISKS = {
    "lumen": [("R-lumen-bank-block", "Bank may block transfers to unusual payees", "yellow", "operational",
               "On AUSN the partner bank is the only one, so a hold on a tax payment is critical. A transfer to an unusual payee was recently held and released via the operator.",
               "Warn the client before any unusual payee; keep an alternative channel ready.")],
    "cobalt": [("R-cobalt-revenue-drop", "Sharp revenue drop in 2026", "yellow", "financial",
                "Revenue pace down ~40% year over year after losing a wholesale buyer; watch cashflow and re-estimate advances.",
                "Re-estimate the annual pace; revisit advance amounts.")],
    "harbor": [("R-harbor-margin", "Thin margin on the income-expense regime", "yellow", "financial",
                "Expenses run close to income; verify deductible expense documents each month.",
                "Tighten primary-document collection for expenses.")],
}
BLOCKER = {"cobalt": "Awaiting access to the bank portal — April close is blocked."}


def valid_inn12(first10):
    d10 = [int(x) for x in first10]
    c11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    n11 = sum(a * b for a, b in zip(c11, d10)) % 11 % 10
    d11 = d10 + [n11]
    c12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    n12 = sum(a * b for a, b in zip(c12, d11)) % 11 % 10
    return first10 + str(n11) + str(n12)


def w(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


NEXT = {
    "month_close": "Run the remaining closing operations in 1C, then re-check the balance.",
    "month_audit": "Audit the period's documents in 1C against the bank statement.",
    "pp_to_form": "Calculate the amount and draft the notification + payment order.",
    "pp_sign": "Remind the client to sign the payment order in the bank.",
    "acquiring_reconciliation": "Confirm the acquiring turnover to the bank.",
    "service_payment": "Check whether the quarterly fee has been received.",
    "primary_collection": "Remind the client to send the source documents.",
    "ndfl_register": "Compile the payroll-tax register for the period.",
    "bank_check": "Download and review the bank statement.",
    "ausn_markup_review": "Review the operation marking in the bank portal.",
    "ens_reconciliation": "Reconcile the single tax account balance for the quarter.",
    "monitoring": "Keep watching; act only if the bank flags a transfer.",
    "awaiting_external": "Waiting on the client — follow up if it stalls.",
}
CTX = {
    "month_close": "Last open monthly period; a few regulated operations remain.",
    "pp_to_form": "Quarterly advance for the regime; figure pending confirmation.",
    "pp_sign": "Payment order prepared; waiting for the client's signature.",
    "acquiring_reconciliation": "Recurring acquiring confirmation to the partner bank.",
    "service_payment": "Postpaid quarterly fee; verify receipt on the statement.",
    "primary_collection": "Waiting on the client's source documents for the period.",
    "ndfl_register": "Payroll-tax register due for the reporting period.",
    "bank_check": "Quarterly bank statement needed to post the period.",
    "ausn_markup_review": "Operation marking in the bank portal needs a review.",
    "ens_reconciliation": "Quarterly single-tax-account reconciliation.",
    "monitoring": "Passive watch after a recent bank hold on an unusual payee.",
    "awaiting_external": "The ball is in the client's court; nothing to do but wait.",
}


def task_obj(cid, suf, title, tt, status, prio, due, period, amount):
    key = f"{cid}_{suf}"
    rich = RICH.get(key, {})
    ts = {}
    if period:
        ts["period"] = period
    if amount:
        ts["amount"] = float(amount)
    hist = rich.get("history") or [
        {"date": d(-7), "event": "Task created (synthetic seed).", "auto": True, "kind": "status_change"}]
    o = {
        "id": key, "title": title, "task_type": tt, "status": status, "priority": prio,
        "created_at": d(-21), "due_date": due, "completed_at": None, "assignee": "Operator",
        "blocked_by": [], "labels": [], "context": rich.get("context", CTX.get(tt, "Example task for the demo instance.")),
        "next_action": rich.get("next_action", NEXT.get(tt, "Take the next step on this task.")), "comments": [],
        "history": hist, "source": "manual",
        "linked": {"finkoper_task_id": None, "anomaly_id": None, "documents": []},
        "type_specific": ts,
    }
    if rich.get("assist"):
        o["assist"] = rich["assist"]
    return o


def main():
    by_client = {c[0]: [] for c in CLIENTS}
    for row in T:
        by_client[row[0]].append(task_obj(*row))
    for cid, suf, title, prio in Q:
        q = {
            "id": f"{cid}_{suf}", "title": title, "task_type": "open_question", "status": "active",
            "priority": prio, "created_at": d(-30), "due_date": None, "completed_at": None,
            "assignee": "Operator", "blocked_by": [], "labels": [], "context": "Synthetic clarification.",
            "next_action": "Ask the client / check the source.", "comments": [],
            "history": [{"date": d(-30), "event": "Question opened (synthetic seed).", "auto": True, "kind": "status_change"}],
            "source": "manual", "linked": {"finkoper_task_id": None, "anomaly_id": None, "documents": []},
            "type_specific": {"no_auto_resolve": True},
        }
        if Q_ASSIST.get(f"{cid}_{suf}"):
            q["assist"] = Q_ASSIST[f"{cid}_{suf}"]
        by_client[cid].append(q)

    roster = []
    for i, (cid, short, full, group, rtype, robj, rate) in enumerate(CLIENTS, 1):
        cdir = os.path.join(DATA, "clients", cid)
        roster.append({"id": cid, "name_short": short, "name_full": full, "folder": f"clients/{cid}", "group": group})
        inn = valid_inn12(f"00000000{i:02d}")
        w(os.path.join(cdir, "state", "identity.json"), {
            "schema_version": "1.0", "client_id": cid, "last_updated": d(-30) + "T00:00:00+03:00",
            "name": {"short": short, "full": full, "in_1c": short, "uncertainty": None},
            "inn": inn, "ogrnip": f"3000000000000{i:02d}", "reg_date": "2021-03-15", "reg_started_year": 2021,
            "addr": {"city": "Lakeside", "full": "Lakeside (synthetic)", "region_pill": "Lakeside"},
            "ifns": {"registration": "Tax Office No.1", "accounting": "0001", "oktmo": "00000001"},
            "okved": {"main": {"code": "10.71", "name": "Synthetic activity", "confirmed_at": "2026-01-10",
                               "confirmed_by": "sample_data", "history": []},
                      "additional": [{"code": "47.91", "name": "Retail via mail order or internet"}]},
            "contacts": {"phone": f"+10000000{i:03d}", "email": f"hello@{cid}.example", "telegram": f"@{cid}", "whatsapp": None},
        })
        w(os.path.join(cdir, "state", "regime.json"), {
            "schema_version": "1.1", "client_id": cid, "last_updated": d(-30) + "T00:00:00+00:00",
            "primary": {"type": rtype, "object": robj, "rate": rate, "since": "2021-03-15"},
            "scenario": "F" if rtype == "AUSN" else "A", "scenario_name": f"{rtype} {robj}",
            "patents": [], "auto_simplified": None, "signature": {"holder": "client", "type": None},
            "filing": {"submission_method": "client_lk_fns", "declarations": "Accountant (prepared)",
                       "declarations_note": "Synthetic.", "contracts_edo": None},
            "accounting_system": "1C" if rtype != "AUSN" else "bank_native",
            "business_description": f"Fabricated example client on {rtype}. No real data.",
        })
        w(os.path.join(cdir, "state", "accounts.json"), {
            "schema_version": "1.1", "client_id": cid, "last_updated": d(-30) + "T00:00:00+08:00",
            "bank_accounts": [{"id": "main", "bank_name": "Example Bank", "bik": "000000001",
                               "account": f"408000000000000000{i:02d}", "purpose": "primary", "is_primary": True,
                               "since": "2021-03-20", "closed_at": None, "notes": "Synthetic."}],
            "foreign_accounts": [], "kassas": [], "acquiring_channels": [], "ofd": None,
            "bank_access": {"primary_bank": "Example Bank", "access_level": "full", "lk_url": "bank.example",
                            "is_ausn_partner": rtype == "AUSN", "statements_source": "accountant_access", "note": "Synthetic."},
            "quick_access": [
                {"service": "bank", "label": "Example Bank", "icon": "building-bank", "url": "https://bank.example/login",
                 "login": None, "password": None, "cred_status": "na", "status": "active", "note": "Sample."},
                {"service": "fns", "label": "Tax office portal", "icon": "building-estate", "url": "https://tax.example/lk",
                 "login": None, "password": None, "cred_status": "na", "status": "active", "note": "Sample."},
            ],
        })
        w(os.path.join(cdir, "state", "financials.json"), {
            "schema_version": "1.1", "client_id": cid, "last_updated": d(-20) + "T01:00:00+00:00",
            "periods": [{"period": "2025", "period_type": "year", "income_usn": 4000000 + i * 120000,
                         "income_usn_estimated": False, "income_usn_basis": "bank_statement", "expenses": None,
                         "patent_income": None, "taxes": {"usn_final": 240000, "one_pct_overage": 36000},
                         "declaration_status": "submitted_accepted", "status": "archive", "notes": "Synthetic year close."}],
            "yearly_pace_2026": {"estimated_annual_income_usn": 3800000, "growth_vs_prev_year_x": 0.95,
                                 "nds_threshold_2026": 20000000, "ausn_threshold_2026": 60000000,
                                 "nds_warning": False, "nds_warning_reason": "Synthetic — safe.", "notes": "Synthetic pace."},
            "tax_calendar_2026": [], "monthly_close": {"month": "April 2026", "deadline": d(-4),
                                                       "today": TODAY.isoformat(), "blocker": BLOCKER.get(cid)},
        })
        w(os.path.join(cdir, "state", "counterparties.json"), {
            "schema_version": "1.1", "client_id": cid, "last_updated": d(-30) + "T00:00:00+03:00",
            "counterparties": [{"id": "main_buyer", "name": "Sample Buyer Ltd", "inn": None, "kpp": None, "ogrn": None,
                                "relation_type": "b2b_customer_main", "category": "wholesale", "contract_type": "supply",
                                "since": "2024-06-01", "volume_share_2026": "main B2B", "volume_amount_2026": None,
                                "requisites": {}, "tags": ["B2B"], "linked_open_questions": [], "linked_tasks": [],
                                "documents": [], "notes": "Synthetic."}],
            "open_questions_summary": "Synthetic example.",
        })
        w(os.path.join(cdir, "state", "behavior.json"), {
            "schema_version": "1.0", "client_id": cid, "last_updated": d(-30) + "T00:00:00",
            "communication": {"response_speed": {"level": "normal", "description": "Synthetic.", "active_examples": [], "silence_examples": []},
                              "style": {"tone": "neutral", "emoji_usage": "rare", "formality": "neutral", "notes": "Synthetic."},
                              "preferences": {"likes": [], "dislikes": [], "asks_for_pattern": None}},
            "channels": {"primary": {"type": "telegram", "id": f"@{cid}"}, "secondary": [], "best_time": None, "timezone": "UTC+3"},
            "notes": "Synthetic behavior profile.", "special_notes": [f"{group.title()} client. {rtype} {robj}."],
        })
        rks = [{"id": rid, "title": rt, "severity": sev, "category": cat, "description": desc, "next_action": na,
                "linked_tasks": [], "linked_law": None, "since": d(-25), "history": [], "kind": "risk"}
               for rid, rt, sev, cat, desc, na in RISKS.get(cid, [])]
        w(os.path.join(cdir, "state", "risks.json"), {
            "schema_version": "1.0", "client_id": cid, "last_updated": d(-20) + "T00:00:00+00:00",
            "risks": rks, "resolved_risks": []})
        w(os.path.join(cdir, "state", "tasks.json"), {
            "schema_version": "2.0", "client_id": cid, "last_updated": TODAY.isoformat() + "T00:00:00",
            "tasks": by_client[cid]})
        with open(os.path.join(cdir, "mental_model.md"), "w", encoding="utf-8") as f:
            f.write(f"# {short}\n\nSynthetic demo client ({group}, {rtype} {robj}). No real data.\n")
        with open(os.path.join(cdir, "history.jsonl"), "w", encoding="utf-8") as f:
            f.write(json.dumps({"date": d(-30), "event": "Synthetic seed.", "kind": "status_change"}, ensure_ascii=False) + "\n")
        with open(os.path.join(cdir, "profile.md"), "w", encoding="utf-8") as f:
            f.write(f"# {short} — profile\n\nFabricated example. Communication: keep it short and clear.\n")

    w(os.path.join(DATA, "clients_index.json"), roster)

    # ---- morning collectors (dated today so the digest is populated) ----------
    inbox = os.path.join(DATA, "journal", "inbox")
    for old in glob.glob(os.path.join(inbox, "*.json")):
        os.remove(old)
    td = TODAY.isoformat()
    w(os.path.join(inbox, f"news_{td}.json"), {"items": [
        {"severity": "high", "title": "Simplified-regime advance deadline confirmed for July 28", "source": "Tax Daily",
         "body": "The quarterly advance date is fixed; no extensions announced.", "url": "https://example.com/news/usn-advance"},
        {"severity": "medium", "title": "New e-invoicing format mandatory in Q4", "source": "Accounting Weekly",
         "body": "Update billing software before October.", "url": "https://example.com/news/einvoice"},
        {"severity": "low", "title": "Bank API maintenance window next weekend", "source": "Bank Status",
         "body": "Statement export may be delayed.", "url": "https://example.com/news/bank-maintenance"},
    ]})
    w(os.path.join(inbox, f"mail_{td}.json"), {"items": [
        {"severity": "high", "from_name": "Aurora Maxwell", "from_email": "aurora@aurora.example",
         "subject": "Need the June advance figure today", "received_at": TODAY.strftime("%d.%m") + " 09:14",
         "client": "SP Aurora Bakery", "preview": "Bank is asking for the exact amount before noon. Can you confirm?", "attachments": []},
        {"severity": "medium", "from_name": "Bruno Castellano", "from_email": "bruno@northwind.example",
         "subject": "Contract for the new buyer", "received_at": TODAY.strftime("%d.%m") + " 08:02",
         "client": "SP Northwind Studio", "preview": "Attaching the signed agreement you asked about.", "attachments": ["contract.pdf"]},
        {"severity": "low", "from_name": "FNS Notifications", "from_email": "noreply@fns.example",
         "subject": "Reporting calendar for July", "received_at": (TODAY - timedelta(1)).strftime("%d.%m") + " 19:40",
         "client": None, "preview": "Informational digest of upcoming July deadlines.", "attachments": []},
    ]})
    w(os.path.join(inbox, f"updates_{td}.json"), {"items": [
        {"category": "applied", "label": "tax_rates", "title": "USN regional rate table",
         "body": "Refreshed the 2026 regional reduced-rate table; applied automatically."},
        {"category": "needs_manual", "label": "okved", "title": "Secondary activity code",
         "body": "A workshop activity code is suggested for SP Meridian Crafts — needs a human decision."},
    ]})
    w(os.path.join(inbox, f"anomalies_{td}.json"), {"items": [
        {"client": "SP Aurora Bakery", "severity": "high", "title": "June advance looks underpaid",
         "description": "Calculated advance is 19,000 but only 12,000 was transferred on the statement.",
         "context": "Compared bank outflow against the period tax calendar.", "source": "bank_statement",
         "suggested_action": "Confirm the shortfall and top up before the deadline.", "anomaly_id": "anom-aurora-001", "lifecycle": "open"},
        {"client": "SP Northwind Studio", "severity": "medium", "title": "New counterparty without a contract on file",
         "description": "Two incoming payments from a new buyer but no contract attached.",
         "context": "Detected during reconciliation of the latest statement.", "source": "reconciliation",
         "suggested_action": "Request the contract and primary documents.", "anomaly_id": "anom-northwind-002", "lifecycle": "open"},
        {"client": None, "severity": "medium", "title": "FNS portal maintenance this weekend",
         "description": "Filing portal unavailable Saturday night; plan submissions earlier.",
         "context": "Systemic, affects all clients.", "source": "news_feed",
         "suggested_action": "Submit pending declarations before Friday EOD.", "anomaly_id": "anom-sys-003", "lifecycle": "open"},
    ]})
    print(f"Seeded {len(CLIENTS)} clients, {sum(len(v) for v in by_client.values())} tasks; collectors dated {td}.")


if __name__ == "__main__":
    main()
