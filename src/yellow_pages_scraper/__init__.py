"""yellow-pages-scraper - clean Yellow Pages business data via the ScrapeUnblocker API.

Search yellowpages.com for any kind of business in any US city or ZIP code and
get clean, typed JSON for every listing: name, Yellow Pages ID, categories,
phone, street address, city, state and ZIP, website, star rating and review
count, TripAdvisor rating, years in business, open status and amenities.
Business pages add the email address, opening hours, geolocation, services,
brands, payment methods, languages, neighborhoods, social links and the latest
reviews. Pages are loaded in a real browser through the ScrapeUnblocker
``getPageSource`` API.

Example:
    >>> from yellow_pages_scraper import YellowPagesScraper
    >>> yp = YellowPagesScraper()                      # reads SCRAPEUNBLOCKER_KEY
    >>> plumbers = yp.search("plumbers", "Chicago, IL", limit=30)    # doctest: +SKIP
    >>> plumbers[0].name, plumbers[0].phone, plumbers[0].zip_code    # doctest: +SKIP
    ('ALL ED ELECTRIC', '(312) 549-9745', '60625')
"""

from __future__ import annotations

from .export import FIELDNAMES, business_row, to_csv, to_json, write_csv
from .models import Business, Review, SearchPage
from .parsing import (
    YellowPagesError,
    YellowPagesNotFoundError,
    YellowPagesParseError,
    parse_business_page,
    parse_listing,
    parse_search_page,
)
from .scraper import DEFAULT_PROXY_COUNTRY, YellowPagesScraper
from .urls import (
    MAX_PAGES,
    PAGE_SIZE,
    SORTS,
    build_business_url,
    build_search_url,
    is_search_url,
    parse_ypid,
    with_page,
)

__all__ = [
    "YellowPagesScraper",
    "Business",
    "Review",
    "SearchPage",
    "YellowPagesError",
    "YellowPagesParseError",
    "YellowPagesNotFoundError",
    "parse_listing",
    "parse_search_page",
    "parse_business_page",
    "build_search_url",
    "build_business_url",
    "is_search_url",
    "parse_ypid",
    "with_page",
    "to_json",
    "to_csv",
    "write_csv",
    "business_row",
    "FIELDNAMES",
    "SORTS",
    "PAGE_SIZE",
    "MAX_PAGES",
    "DEFAULT_PROXY_COUNTRY",
]

__version__ = "0.1.0"
