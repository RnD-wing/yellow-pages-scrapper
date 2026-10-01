"""Typed records returned by yellow-pages-scraper."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any


@dataclass
class Review:
    """One customer review shown on a business page."""

    review_id: str | None
    author: str | None
    date: str | None  # ISO YYYY-MM-DD
    rating: float | None
    text: str | None
    source: str | None = None  # partner site that supplied the review, if any


@dataclass
class Business:
    """A Yellow Pages business listing.

    Search results fill the first block of fields. Business pages (``--details``
    / :meth:`~yellow_pages_scraper.YellowPagesScraper.get_business`) add the
    second block and set ``has_details``.
    """

    ypid: str
    name: str
    url: str
    rank: int | None = None
    categories: list[str] = field(default_factory=list)
    phone: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    address: str | None = None
    service_area: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    tripadvisor_rating: float | None = None
    tripadvisor_review_count: int | None = None
    years_in_business: int | None = None
    years_with_yp: int | None = None
    open_status: str | None = None
    amenities: list[str] = field(default_factory=list)
    snippet: str | None = None
    image_url: str | None = None
    advertiser: bool | None = None
    sponsored: bool = False
    # --- business page only ---
    has_details: bool = False
    business_type: str | None = None
    email: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    founded: int | None = None
    description: str | None = None
    aka: list[str] = field(default_factory=list)
    hours: list[dict[str, str]] = field(default_factory=list)
    opening_hours: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)
    payment_methods: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    neighborhoods: list[str] = field(default_factory=list)
    ownership: str | None = None
    free_estimates: bool | None = None
    accreditation: str | None = None
    associations: str | None = None
    location_note: str | None = None
    other_info: dict[str, str] = field(default_factory=dict)
    social_links: dict[str, str] = field(default_factory=dict)
    other_links: list[str] = field(default_factory=list)
    reviews: list[Review] = field(default_factory=list)
    # --- labels of the search that found the listing ---
    query: str | None = None
    query_location: str | None = None

    # Fields that only a search results page knows; a business page never
    # overwrites them when the two are merged.
    SEARCH_ONLY = ("rank", "snippet", "sponsored", "advertiser", "query", "query_location")

    def merge_details(self, details: Business) -> Business:
        """Copy every non-empty field of ``details`` onto this record and return it."""
        for item in fields(self):
            if item.name in self.SEARCH_ONLY:
                continue
            value: Any = getattr(details, item.name)
            if value is None or value == [] or value == {} or value == "":
                continue
            setattr(self, item.name, value)
        return self


@dataclass
class SearchPage:
    """One parsed search results page."""

    url: str
    page: int
    businesses: list[Business]
    ads: list[Business] = field(default_factory=list)
    total: int | None = None
    has_next: bool = False


__all__ = ["Business", "Review", "SearchPage"]
