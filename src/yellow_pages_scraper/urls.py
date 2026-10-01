"""URL helpers for yellowpages.com searches and business pages."""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

BASE_URL = "https://www.yellowpages.com"

# Yellow Pages shows 30 organic results per page and at most 3,000 results
# (100 pages) for any one search.
PAGE_SIZE = 30
MAX_PAGES = 100

# CLI / library sort names -> the site's ``s`` query parameter.
SORTS: dict[str, str | None] = {
    "default": None,
    "distance": "distance",
    "rating": "average_rating",
    "name": "name",
}

# Category browse pages such as /chicago-il/plumbers use the same result markup
# as /search. Business pages live under /<place>/mip/<slug>-<ypid>.
_BROWSE_PATH = re.compile(r"^/[a-z0-9-]+/[a-z0-9-]+/?$", re.IGNORECASE)
_MIP_PATH = re.compile(r"^/[a-z0-9-]+/mip/[a-z0-9-]*?-?(\d+)/?$", re.IGNORECASE)


def _is_yp_host(host: str) -> bool:
    host = host.lower().split(":")[0]
    return host == "yellowpages.com" or host.endswith(".yellowpages.com")


def build_search_url(
    terms: str,
    location: str,
    *,
    sort: str = "default",
    page: int = 1,
) -> str:
    """Build a ``/search`` URL.

    Args:
        terms: What to search for, e.g. ``"plumbers"`` or ``"pizza"``.
        location: Where, e.g. ``"Chicago, IL"`` or a ZIP code (``"90210"``).
        sort: ``default``, ``distance``, ``rating`` or ``name`` (A-Z).
        page: Results page, 1-100.

    Example:
        >>> build_search_url("plumbers", "Chicago, IL", sort="rating")
        'https://www.yellowpages.com/search?search_terms=plumbers&geo_location_terms=Chicago%2C+IL&s=average_rating'
    """
    terms = (terms or "").strip()
    location = (location or "").strip()
    if not terms:
        raise ValueError("search terms must not be empty")
    if not location:
        raise ValueError("location must not be empty (a city and state, or a ZIP code)")
    if sort not in SORTS:
        raise ValueError(f"unknown sort {sort!r}; choose from {', '.join(SORTS)}")
    if not 1 <= page <= MAX_PAGES:
        raise ValueError(f"page must be between 1 and {MAX_PAGES}")
    params = [("search_terms", terms), ("geo_location_terms", location)]
    if SORTS[sort]:
        params.append(("s", SORTS[sort]))
    if page > 1:
        params.append(("page", str(page)))
    return f"{BASE_URL}/search?{urlencode(params)}"


def is_search_url(url: str) -> bool:
    """True for a yellowpages.com ``/search?...`` or category browse URL."""
    parts = urlsplit(url or "")
    if parts.scheme not in ("http", "https") or not _is_yp_host(parts.netloc):
        return False
    if parts.path.rstrip("/") == "/search":
        return bool(dict(parse_qsl(parts.query)).get("search_terms"))
    return bool(_BROWSE_PATH.match(parts.path)) and "/mip" not in parts.path


def page_of(url: str) -> int:
    """The ``page`` parameter of a search URL (1 when absent or invalid)."""
    value = dict(parse_qsl(urlsplit(url).query)).get("page", "1")
    try:
        return max(1, int(value))
    except ValueError:
        return 1


def with_page(url: str, page: int) -> str:
    """Return ``url`` pointing at results page ``page`` (page 1 drops the parameter)."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "page"]
    if page > 1:
        query.append(("page", str(page)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def absolute_url(href: str | None) -> str | None:
    """Resolve a site-relative or protocol-relative link against yellowpages.com."""
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    return urljoin(BASE_URL + "/", href)


def build_business_url(value: str) -> str:
    """Canonical business-page URL from a full URL or a ``/<place>/mip/...`` path.

    The ``lid`` (listing ID) parameter search results link with is kept: it
    selects the advertiser's own listing, whose page carries the most specific
    business type. Every other query parameter and the fragment are dropped.

    Raises:
        ValueError: when ``value`` is not a Yellow Pages business page.
    """
    url = absolute_url(value)
    parts = urlsplit(url or "")
    if not _is_yp_host(parts.netloc) or not _MIP_PATH.match(parts.path):
        raise ValueError(
            f"not a Yellow Pages business URL: {value!r} "
            "(expected https://www.yellowpages.com/<place>/mip/<name>-<id>)"
        )
    lid = dict(parse_qsl(parts.query)).get("lid", "")
    query = urlencode({"lid": lid}) if lid.isdigit() else ""
    return urlunsplit(("https", "www.yellowpages.com", parts.path.rstrip("/"), query, ""))


def parse_ypid(url: str | None) -> str | None:
    """The numeric Yellow Pages business ID at the end of a business URL."""
    if not url:
        return None
    match = _MIP_PATH.match(urlsplit(absolute_url(url) or "").path)
    return match.group(1) if match else None


def is_yellowpages_link(url: str | None) -> bool:
    """True when ``url`` points back to yellowpages.com (not a business's own site)."""
    if not url:
        return False
    return _is_yp_host(urlsplit(absolute_url(url) or "").netloc)


__all__ = [
    "BASE_URL",
    "PAGE_SIZE",
    "MAX_PAGES",
    "SORTS",
    "build_search_url",
    "build_business_url",
    "is_search_url",
    "page_of",
    "with_page",
    "absolute_url",
    "parse_ypid",
    "is_yellowpages_link",
]
