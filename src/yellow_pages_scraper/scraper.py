"""Scrape Yellow Pages through the ScrapeUnblocker ``getPageSource`` API.

ScrapeUnblocker loads every search and business page in a real browser and
returns the HTML, which :mod:`yellow_pages_scraper.parsing` turns into
:class:`~yellow_pages_scraper.models.Business` records.

Timeouts, transient API errors and unrecognisable pages are retried with
doubling backoff, so a long collection run keeps going.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from typing import Any, Callable

from .models import Business, SearchPage
from .parsing import (
    YellowPagesError,
    YellowPagesNotFoundError,
    YellowPagesParseError,
    empty_search_page,
    parse_business_page,
    parse_search_page,
)
from .urls import MAX_PAGES, build_business_url, build_search_url, is_search_url, page_of, with_page

# Yellow Pages is a US directory; a US route sees the same results a US visitor does.
DEFAULT_PROXY_COUNTRY = "US"


def _transient_errors() -> tuple[type[BaseException], ...]:
    """Best-effort tuple of ScrapeUnblocker exceptions worth retrying.

    Imported lazily so the package is usable (and unit-testable) even when the
    ``scrapeunblocker`` SDK is not installed.
    """
    try:
        from scrapeunblocker import (  # type: ignore
            BlockedError,
            BrowserTimeoutError,
            RateLimitError,
            ScrapeTimeoutError,
            ServerError,
            UpstreamOutageError,
        )
        from scrapeunblocker import (
            ConnectionError as SUConnectionError,
        )
    except Exception:  # pragma: no cover - depends on SDK availability
        return ()
    return (
        UpstreamOutageError,
        RateLimitError,
        ScrapeTimeoutError,
        BrowserTimeoutError,
        BlockedError,
        ServerError,
        SUConnectionError,
    )


def is_not_found(error: BaseException) -> bool:
    """True when the API reports that the target page answered 404.

    Yellow Pages serves a 404 for searches with no matches and for business
    pages that no longer exist; the SDK raises ``NotFoundError`` for both.
    """
    return getattr(error, "status_code", None) == 404


class YellowPagesScraper:
    """Scrape Yellow Pages search results and business pages.

    Args:
        api_key: ScrapeUnblocker key. If omitted, the SDK reads
            ``SCRAPEUNBLOCKER_KEY`` from the environment.
        client: A pre-built client (or any object exposing
            ``get_page_source(url, proxy_country=...)``). Mainly for testing.
        proxy_country: Country to route requests through (default ``"US"``).
        retries: Extra attempts per page on transient failures.
        backoff: Seconds before the first retry; doubles on every further retry.
        max_backoff: Upper bound for a single wait between retries.
        timeout: Per-request timeout passed to the SDK client.
        transient_errors: Exception classes treated as retryable. Defaults to
            the ScrapeUnblocker transient set.
        on_retry: Optional callback ``(attempt, delay_seconds, error)`` invoked
            before every retry (handy for progress output).
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Any | None = None,
        proxy_country: str | None = DEFAULT_PROXY_COUNTRY,
        retries: int = 3,
        backoff: float = 5.0,
        max_backoff: float = 60.0,
        timeout: float = 180.0,
        transient_errors: Sequence[type[BaseException]] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        on_retry: Callable[[int, float, BaseException], None] | None = None,
    ) -> None:
        if client is None:
            from scrapeunblocker import Client  # local import: optional dep

            client = Client(api_key=api_key, timeout=timeout)
        self._client = client
        self.proxy_country = proxy_country
        self.retries = max(0, int(retries))
        self.backoff = float(backoff)
        self.max_backoff = float(max_backoff)
        self.on_retry = on_retry
        transient = tuple(transient_errors) if transient_errors is not None else _transient_errors()
        self._transient = (*transient, YellowPagesParseError)
        self._sleep = sleep

    # ------------------------------------------------------------------ #
    # Low-level fetching
    # ------------------------------------------------------------------ #

    def _fetch(
        self,
        url: str,
        parse: Callable[[str], Any],
        on_not_found: Callable[[BaseException], Any],
    ) -> Any:
        """Fetch ``url`` and parse it, retrying transient failures with backoff."""
        attempt = 0
        while True:
            try:
                html = self._client.get_page_source(url, proxy_country=self.proxy_country)
                return parse(html if isinstance(html, str) else "")
            except Exception as exc:
                if is_not_found(exc):
                    return on_not_found(exc)
                if not isinstance(exc, self._transient) or attempt >= self.retries:
                    raise
                attempt += 1
                delay = min(self.backoff * 2 ** (attempt - 1), self.max_backoff)
                if self.on_retry is not None:
                    self.on_retry(attempt, delay, exc)
                self._sleep(delay)

    def fetch_search_page(self, url: str, *, page: int = 1) -> SearchPage:
        """Fetch and parse one search results page (an empty page when nothing matches)."""
        return self._fetch(
            url,
            lambda html: parse_search_page(html, url=url, page=page),
            lambda _exc: empty_search_page(url=url, page=page),
        )

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #

    def search_url(
        self,
        url: str,
        *,
        limit: int = 30,
        start_page: int | None = None,
        max_pages: int | None = None,
        include_ads: bool = False,
        details: bool = False,
        query: str | None = None,
        query_location: str | None = None,
        seen: set[str] | None = None,
        on_page: Callable[[SearchPage], None] | None = None,
    ) -> list[Business]:
        """Collect businesses from a search URL, e.g. one copied from your browser.

        Args:
            url: A ``https://www.yellowpages.com/search?...`` URL or a category
                page such as ``https://www.yellowpages.com/chicago-il/plumbers``.
            limit: Maximum number of businesses to return (30 per page).
            start_page: First results page to fetch. Defaults to the URL's own
                ``page`` parameter, or 1.
            max_pages: Stop after fetching this many pages, even if ``limit``
                is not reached (caps the number of requests).
            include_ads: Also keep the promoted cards from the ad blocks that
                are not in the organic results (``sponsored=True``).
            details: Also fetch every business page for email, hours,
                geolocation, services and reviews (one extra request each).
            query, query_location: Labels stored on every returned record.
            seen: Shared set of business IDs; IDs already in it are skipped.
                Pass the same set to several calls to de-duplicate across searches.
            on_page: Callback invoked with every fetched :class:`SearchPage`.
        """
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if not is_search_url(url):
            raise ValueError(f"not a Yellow Pages search URL: {url!r}")
        if start_page is None:
            start_page = page_of(url)
        if not 1 <= start_page <= MAX_PAGES:
            raise ValueError(f"start_page must be between 1 and {MAX_PAGES}")
        seen = set() if seen is None else seen
        own: set[str] = set()  # IDs met by this collection (guards against repeats)
        results: list[Business] = []
        page_number = start_page
        last_page = MAX_PAGES if max_pages is None else min(MAX_PAGES, start_page + max_pages - 1)
        while len(results) < limit and page_number <= last_page:
            page = self.fetch_search_page(with_page(url, page_number), page=page_number)
            if on_page is not None:
                on_page(page)
            fresh = False
            candidates = page.businesses + (page.ads if include_ads else [])
            for business in candidates:
                if business.ypid in own:
                    continue
                own.add(business.ypid)
                fresh = True
                if business.ypid in seen:
                    continue
                seen.add(business.ypid)
                business.query = query
                business.query_location = query_location
                results.append(business)
                if len(results) >= limit:
                    break
            if not page.has_next or not fresh:
                break
            page_number += 1
        if details:
            results = self.enrich(results)
        return results

    def search(
        self,
        terms: str,
        location: str,
        *,
        sort: str = "default",
        limit: int = 30,
        start_page: int | None = None,
        max_pages: int | None = None,
        include_ads: bool = False,
        details: bool = False,
        seen: set[str] | None = None,
        on_page: Callable[[SearchPage], None] | None = None,
    ) -> list[Business]:
        """Search Yellow Pages and return up to ``limit`` businesses.

        Args:
            terms: What to look for: a business type, a category or a name
                (``"plumbers"``, ``"pizza"``, ``"Roto-Rooter"``).
            location: A city and state (``"Chicago, IL"``) or a ZIP code.
            sort: ``default`` (best match), ``distance``, ``rating`` or ``name``.

        The remaining arguments are described in :meth:`search_url`.

        Example:
            >>> yp.search("plumbers", "Chicago, IL", sort="rating", limit=60)  # doctest: +SKIP
        """
        url = build_search_url(terms, location, sort=sort, page=start_page or 1)
        return self.search_url(
            url,
            limit=limit,
            start_page=start_page,
            max_pages=max_pages,
            include_ads=include_ads,
            details=details,
            query=terms.strip(),
            query_location=location.strip(),
            seen=seen,
            on_page=on_page,
        )

    def search_many(
        self,
        terms: Iterable[str],
        locations: Iterable[str],
        *,
        limit: int = 30,
        details: bool = False,
        on_page: Callable[[str, str, SearchPage], None] | None = None,
        **options: Any,
    ) -> list[Business]:
        """Run :meth:`search` for every (terms, location) pair and merge the results.

        ``limit`` applies per pair; businesses found by an earlier pair are
        skipped, so a chain listed in several cities appears once per branch
        (every branch has its own ID). ``details`` fetches the business pages
        once, after de-duplication. Every other keyword argument is passed to
        :meth:`search`.
        """
        seen: set[str] = set()
        results: list[Business] = []
        locations = [loc.strip() for loc in locations if loc and loc.strip()]
        for term in terms:
            if not term or not term.strip():
                continue
            for location in locations:
                callback = None
                if on_page is not None:
                    callback = (lambda t, loc: lambda page: on_page(t, loc, page))(
                        term.strip(), location
                    )
                results += self.search(
                    term, location, limit=limit, seen=seen, on_page=callback, **options
                )
        return self.enrich(results) if details else results

    # ------------------------------------------------------------------ #
    # Business pages
    # ------------------------------------------------------------------ #

    def get_business(self, business: str) -> Business:
        """Fetch one business page by URL (``https://www.yellowpages.com/<place>/mip/...``).

        Raises:
            YellowPagesNotFoundError: when the business page does not exist.
        """
        url = build_business_url(business)

        def missing(exc: BaseException) -> Any:
            raise YellowPagesNotFoundError(f"business page not found: {url}") from exc

        return self._fetch(url, lambda html: parse_business_page(html, url=url), missing)

    def enrich(
        self,
        businesses: Iterable[Business],
        *,
        on_error: Callable[[Business, BaseException], None] | None = None,
    ) -> list[Business]:
        """Add business-page details (email, hours, geolocation, ...) to search results.

        Search-only fields (rank, snippet, sponsored, query labels) are kept. A
        business that fails keeps its search-result data; ``on_error`` is told
        about it.
        """
        enriched: list[Business] = []
        for business in businesses:
            try:
                details = self.get_business(business.url)
            except (YellowPagesError, ValueError, *self._transient) as exc:
                if on_error is not None:
                    on_error(business, exc)
                enriched.append(business)
                continue
            enriched.append(business.merge_details(details))
        return enriched


__all__ = ["YellowPagesScraper", "DEFAULT_PROXY_COUNTRY", "is_not_found"]
