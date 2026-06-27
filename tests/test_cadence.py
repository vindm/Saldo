"""Unit tests for engine/_cadence.py — the derived bookkeeping cadence (docs/CADENCE.md).

Self-contained: run with `python3 tests/test_cadence.py` from the saldo/ root. No pytest.
Exercises the PURE core against plain-dict fixtures and against the REAL pack obligations
(jurisdictions/ru/obligations.yaml), so a future change to the declared cadences is caught here.
"""

import datetime
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "engine"))

import _cadence as C  # noqa: E402


def _ru_obligations():
    import yaml
    path = os.path.join(_ROOT, "jurisdictions", "ru", "obligations.yaml")
    with open(path, encoding="utf-8") as f:
        return (yaml.safe_load(f) or {}).get("obligations") or {}


OBL = _ru_obligations()


# ── fixtures (synthetic, mirror the CADENCE.md examples) ────────────────────
def st(regime_type=None, employees=None, patents=None, periods=None, vat_threshold=None):
    reg = {}
    if regime_type:
        reg["primary"] = {"type": regime_type}
    if patents is not None:
        reg["patents"] = patents
    fin = {}
    if periods is not None:
        fin["periods"] = periods
    if vat_threshold is not None:
        fin["nds_threshold_2026"] = vat_threshold
    return {
        "regime": reg,
        "payroll": {"employees": employees or []},
        "financials": fin,
    }


AURORA = st("USN")                                             # USN income, no staff
COBALT = st("USN", employees=[{"hired": "2025-01-01"}])        # USN + employees
HARBOR = st("AUSN")                                            # AUSN
PATMOS = st("USN", patents=[{"status": "active",
                             "from": "2026-01-01", "to": "2026-06-30"}])


# ── tests ───────────────────────────────────────────────────────────────────
def test_period_bounds():
    assert C.period_bounds("2026-06") == (datetime.date(2026, 6, 1), datetime.date(2026, 6, 30))
    assert C.period_bounds("2026-Q2") == (datetime.date(2026, 4, 1), datetime.date(2026, 6, 30))
    assert C.period_bounds("2026-H1") == (datetime.date(2026, 1, 1), datetime.date(2026, 6, 30))
    assert C.period_bounds("2026-H2") == (datetime.date(2026, 7, 1), datetime.date(2026, 12, 31))
    assert C.period_bounds("2026") == (datetime.date(2026, 1, 1), datetime.date(2026, 12, 31))
    assert C.period_bounds("garbage") is None
    assert C.period_bounds("2026-13") is None


def test_period_cadence():
    assert C.period_cadence("2026-06") == "monthly"
    assert C.period_cadence("2026-Q2") == "quarterly"
    assert C.period_cadence("2026-H1") == "semester"
    assert C.period_cadence("2026") == "annual"
    assert C.period_cadence("garbage") is None


def test_min_period():
    assert C.min_period(["quarterly", "monthly"]) == "monthly"
    assert C.min_period(["quarterly", "annual"]) == "quarterly"
    assert C.min_period(["semester", "annual"]) == "semester"
    assert C.min_period(["per_term"]) is None        # patent term is not a bookkeeping floor
    assert C.min_period(["event"]) is None
    assert C.min_period([]) is None


def test_named_scenarios():
    assert C.resolve_bookkeeping_cadence(OBL, AURORA, "2026-Q2") == "quarterly"
    assert C.resolve_bookkeeping_cadence(OBL, COBALT, "2026-Q2") == "monthly"   # payroll floor
    assert C.resolve_bookkeeping_cadence(OBL, HARBOR, "2026-06") == "monthly"
    assert C.resolve_bookkeeping_cadence(OBL, PATMOS, "2026-Q2") == "quarterly"  # patent ignored for floor


def test_as_of_dynamic_hire():
    # A USN client who hires on 2026-08-01: quarterly through H1, monthly from the hire on.
    client = st("USN", employees=[{"hired": "2026-08-01"}])
    assert C.applies_as_of("has_employees", client, "2026-Q2") is False
    assert C.applies_as_of("has_employees", client, "2026-09") is True
    assert C.resolve_bookkeeping_cadence(OBL, client, "2026-Q2") == "quarterly"
    assert C.resolve_bookkeeping_cadence(OBL, client, "2026-09") == "monthly"


def test_has_employees_declaration_fallback():
    # Declared staff (regime.has_employees) but the roster is not yet filled — still counts, so the
    # floor is monthly. has_employees is a primary declaration, not a cache derived from the roster.
    client = {"regime": {"primary": {"type": "USN"}, "has_employees": True},
              "payroll": {"employees": []}, "financials": {}}
    assert C.applies_as_of("has_employees", client, "2026-Q2") is True
    assert C.resolve_bookkeeping_cadence(OBL, client, "2026-Q2") == "monthly"


def test_as_of_terminated_employee():
    client = st("USN", employees=[{"hired": "2025-01-01", "terminated": "2026-03-31"}])
    assert C.applies_as_of("has_employees", client, "2026-Q1") is True
    assert C.applies_as_of("has_employees", client, "2026-Q2") is False


def test_vat_threshold_crossing():
    # USN turnover crosses the VAT threshold mid-year; the predicate flips on the period it crosses.
    client = st("USN",
                periods=[{"period": "2026-Q1", "turnover": 3_000_000},
                         {"period": "2026-Q2", "turnover": 3_000_000}],
                vat_threshold=5_000_000)
    assert C.applies_as_of("vat_liable", client, "2026-Q1") is False   # 3M < 5M
    assert C.applies_as_of("vat_liable", client, "2026-Q2") is True    # 6M cumulative >= 5M
    # VAT is quarterly, so the USN floor (already quarterly) is unchanged either way.
    assert C.resolve_bookkeeping_cadence(OBL, client, "2026-Q2") == "quarterly"


def test_osno_always_vat():
    assert C.applies_as_of("vat_liable", st("OSNO"), "2026-Q2") is True


def test_active_patent():
    assert C.applies_as_of("has_active_patent", PATMOS, "2026-Q1") is True
    assert C.applies_as_of("has_active_patent", PATMOS, "2026-Q3") is False  # term ended 06-30
    revoked = st("USN", patents=[{"status": "revoked", "from": "2026-01-01", "to": "2026-12-31"}])
    assert C.applies_as_of("has_active_patent", revoked, "2026-Q1") is False


def test_delivery_cadence_parse():
    assert C.delivery_cadence("monthly_via_client_export") == "monthly"
    assert C.delivery_cadence("quarterly") == "quarterly"
    assert C.delivery_cadence("on_request") is None
    assert C.delivery_cadence("") is None
    assert C.delivery_cadence(None) is None


def test_is_delivery_looser():
    # Looser = longer period than required = a problem.
    assert C.is_delivery_looser("quarterly", "monthly") is True    # quarterly docs, monthly books
    assert C.is_delivery_looser("monthly", "quarterly") is False   # tighter delivery is fine
    assert C.is_delivery_looser("quarterly", "quarterly") is False  # equal is fine
    assert C.is_delivery_looser("monthly", None) is False           # undetermined -> silent
    assert C.is_delivery_looser(None, "monthly") is False


def test_undetermined_returns_none():
    # Unknown / empty regime -> no applicable stream -> None (caller surfaces, never assumes monthly).
    assert C.resolve_bookkeeping_cadence(OBL, st(None), "2026-Q2") is None
    assert C.applies_as_of("unknown_token", AURORA, "2026-Q2") is False
    assert C.resolve_bookkeeping_cadence(OBL, AURORA, "garbage") is None


# ── runner ──────────────────────────────────────────────────────────────────
def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print("  PASS %s" % t.__name__)
        except AssertionError as e:
            failed += 1
            print("  FAIL %s — %s" % (t.__name__, e or "assertion"))
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("  ERROR %s — %r" % (t.__name__, e))
    print("\n%d passed, %d failed" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run())
