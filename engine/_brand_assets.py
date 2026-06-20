"""_brand_assets.py — dashboard brand assets (data URI).
Generated from the brand-style kit. Logo — a monogram (PNG), favicon — SVG.
These are placeholder example assets for the public template.
"""

import base64 as _b64
try:
    from _config import BRAND_MONOGRAM as _MONO
except Exception:
    _MONO = "S"


def _logo_data_uri(monogram, bg="#1F4E79"):
    """A clean, neutral monogram logo generated from the brand monogram."""
    m = (monogram or "S")[:3]
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<circle cx="32" cy="32" r="32" fill="' + bg + '"/>'
        '<text x="32" y="33" text-anchor="middle" dominant-baseline="central" '
        'font-family="Arial,Helvetica,sans-serif" font-size="24" font-weight="600" '
        'fill="#ffffff">' + m + '</text></svg>'
    )
    return "data:image/svg+xml;base64," + _b64.b64encode(svg.encode("utf-8")).decode("ascii")


LOGO_DATA_URI = _logo_data_uri(_MONO)

FAVICON_URI = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iMTUuNSIgZmlsbD0iIzFGNEU3OSIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMTYiIHI9IjEyLjciIGZpbGw9Im5vbmUiIHN0cm9rZT0iI0I3OTI1NyIgc3Ryb2tlLXdpZHRoPSIxLjMiLz48dGV4dCB4PSIxNiIgeT0iMTciIHRleHQtYW5jaG9yPSJtaWRkbGUiIGRvbWluYW50LWJhc2VsaW5lPSJjZW50cmFsIiBmb250LWZhbWlseT0iQXJpYWwsSGVsdmV0aWNhLHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTQiIGZvbnQtd2VpZ2h0PSI3MDAiIGZpbGw9IiNmZmZmZmYiPtCY0JI8L3RleHQ+PC9zdmc+"
