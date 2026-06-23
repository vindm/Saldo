"""
Jurisdiction packs — pluggable, per-client tax-system definitions.

A pack lives in ../jurisdictions/<code>/ as declared data (yaml). The engine
reads it; it invents nothing. A client is bound to a pack by its
`regime.jurisdiction` field; when that field is absent the default is "ru"
(the historical single-jurisdiction behaviour). An *unknown* code — a code with
no pack directory — is a hard, named error, never a silent RU fallback.

Phase 2, Deliverable 1. See PHASE2_PLAN.md.
"""
import os
import functools

_HERE = os.path.dirname(os.path.abspath(__file__))
_PACKS_DIR = os.path.abspath(os.path.join(_HERE, "..", "jurisdictions"))

DEFAULT_JURISDICTION = "ru"


class JurisdictionError(Exception):
    """Raised when a client names a jurisdiction code with no pack on disk."""


class Pack:
    """Thin read-only view over one jurisdiction's declared data."""

    def __init__(self, code, regimes):
        self.code = code
        self._regimes = regimes or {}

    @property
    def regimes(self):
        return self._regimes.get("regimes") or {}

    @property
    def patent(self):
        return self._regimes.get("patent") or {}

    @property
    def manifest(self):
        return getattr(self, "_manifest", {}) or {}

    @property
    def authorities(self):
        return getattr(self, "_authorities", {}) or {}

    @property
    def lint(self):
        return getattr(self, "_lint", {}) or {}

    def checklist_for(self, task_type):
        """Resolve the checklist path for a task type, or None if the type does
        not apply in this jurisdiction (caller must surface that, never RF-fallback)."""
        return (self.manifest.get("checklists") or {}).get(task_type)


def _read_yaml(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@functools.lru_cache(maxsize=None)
def load_jurisdiction(code):
    """Load the pack for `code`. Empty/None -> DEFAULT_JURISDICTION.

    Raises JurisdictionError if the resolved code has no pack directory, so a
    typo or a not-yet-authored pack fails loudly instead of silently rendering
    under RU rules.
    """
    code = (code or DEFAULT_JURISDICTION).strip().lower()
    pack_dir = os.path.join(_PACKS_DIR, code)
    if not os.path.isdir(pack_dir):
        raise JurisdictionError(
            "unknown jurisdiction %r: no pack at %s" % (code, pack_dir)
        )
    regimes_path = os.path.join(pack_dir, "regimes.yaml")
    regimes = _read_yaml(regimes_path) if os.path.isfile(regimes_path) else {}
    pack = Pack(code, regimes)
    man_path = os.path.join(pack_dir, "manifest.yaml")
    pack._manifest = _read_yaml(man_path) if os.path.isfile(man_path) else {}
    auth_path = os.path.join(pack_dir, "authorities.yaml")
    pack._authorities = _read_yaml(auth_path) if os.path.isfile(auth_path) else {}
    lint_path = os.path.join(pack_dir, "lint.yaml")
    pack._lint = _read_yaml(lint_path) if os.path.isfile(lint_path) else {}
    return pack


def render_regime_label(pack, primary, patents):
    """Build the dashboard regime string from a pack + a client's regime data.

    Faithful re-implementation of the if/elif block previously inlined in
    _loaders.apply_regime_to_client: base token (by type, then object, then raw),
    optional rate token, optional patent suffix; joined by single spaces.
    """
    primary = primary or {}
    rtype = primary.get("type")
    obj = primary.get("object")
    rate = primary.get("rate")

    parts = []
    spec = pack.regimes.get(rtype)
    if spec is None:
        parts.append(rtype or "")
    else:
        objects = spec.get("objects") or {}
        base = objects.get(obj)
        if base is None:
            base = spec.get("label") or (rtype or "")
        parts.append(base)
        if spec.get("show_rate") and rate is not None:
            parts.append(str(rate) + "%")

    pat = pack.patent or {}
    active_status = pat.get("active_status", "active")
    suffix = pat.get("suffix")
    if suffix and any((p.get("status") == active_status) for p in (patents or [])):
        parts.append(suffix)

    return " ".join([p for p in parts if p]).strip()
