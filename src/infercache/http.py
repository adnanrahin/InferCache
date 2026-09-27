"""HTTP helpers that refuse non-http(s) URLs (Bandit B310)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen as _stdlib_urlopen

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def require_http_url(url: str) -> str:
    """Return *url* if it uses http/https; otherwise raise ValueError."""
    scheme = urlparse(url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Refusing URL with scheme {scheme!r}; only http/https are allowed")
    return url


def urlopen(url: str | Request, timeout: float | None = None) -> Any:
    """``urllib.request.urlopen`` restricted to http and https."""
    target = url.get_full_url() if isinstance(url, Request) else url
    require_http_url(target)
    # Scheme is checked above; nosec is only for the stdlib call itself.
    return _stdlib_urlopen(url, timeout=timeout)  # nosec B310
