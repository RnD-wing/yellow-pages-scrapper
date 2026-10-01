from __future__ import annotations

import pytest

from yellow_pages_scraper.urls import (
    absolute_url,
    build_business_url,
    build_search_url,
    is_search_url,
    is_yellowpages_link,
    page_of,
    parse_ypid,
    with_page,
)


def test_build_search_url() -> None:
    assert build_search_url("plumbers", "Chicago, IL") == (
        "https://www.yellowpages.com/search?search_terms=plumbers&geo_location_terms=Chicago%2C+IL"
    )
    assert build_search_url(" auto repair ", "90210", sort="distance", page=3) == (
        "https://www.yellowpages.com/search?search_terms=auto+repair"
        "&geo_location_terms=90210&s=distance&page=3"
    )
    assert "s=average_rating" in build_search_url("pizza", "Brooklyn, NY", sort="rating")
    assert "s=name" in build_search_url("pizza", "Brooklyn, NY", sort="name")


@pytest.mark.parametrize(
    ("terms", "location", "kwargs"),
    [
        ("", "Chicago, IL", {}),
        ("plumbers", " ", {}),
        ("plumbers", "Chicago, IL", {"sort": "price"}),
        ("plumbers", "Chicago, IL", {"page": 0}),
        ("plumbers", "Chicago, IL", {"page": 101}),
    ],
)
def test_build_search_url_rejects_bad_input(terms, location, kwargs) -> None:
    with pytest.raises(ValueError):
        build_search_url(terms, location, **kwargs)


def test_is_search_url() -> None:
    assert is_search_url("https://www.yellowpages.com/search?search_terms=x&geo_location_terms=y")
    assert is_search_url("https://www.yellowpages.com/chicago-il/plumbers")
    assert is_search_url("https://www.yellowpages.com/chicago-il/plumbers?page=2")
    assert not is_search_url("https://www.yellowpages.com/search?geo_location_terms=y")
    assert not is_search_url("https://www.yellowpages.com/chicago-il/mip/x-123")
    assert not is_search_url("https://example.com/search?search_terms=x")
    assert not is_search_url("not a url")


def test_pages() -> None:
    url = "https://www.yellowpages.com/search?search_terms=x&geo_location_terms=y&page=4"
    assert page_of(url) == 4
    assert page_of("https://www.yellowpages.com/search?search_terms=x") == 1
    assert page_of("https://www.yellowpages.com/search?page=abc") == 1
    assert with_page(url, 5).endswith("&page=5")
    assert "page=" not in with_page(url, 1)


def test_build_business_url() -> None:
    expected = "https://www.yellowpages.com/chicago-il/mip/baethke-plumbing-15128363"
    assert build_business_url(expected) == expected
    assert build_business_url("/chicago-il/mip/baethke-plumbing-15128363#gallery") == expected
    assert build_business_url(expected + "/?utm=1") == expected
    assert build_business_url(expected + "?lid=1002166423741&x=1") == (
        expected + "?lid=1002166423741"
    )
    with pytest.raises(ValueError):
        build_business_url("https://www.yellowpages.com/chicago-il/plumbers")
    with pytest.raises(ValueError):
        build_business_url("https://example.com/chicago-il/mip/x-123")


def test_parse_ypid_and_links() -> None:
    assert parse_ypid("/chicago-il/mip/4900-r-w-holdings-llc-538982808?lid=1") == "538982808"
    assert parse_ypid("https://www.yellowpages.com/nationwide/mip/roto-rooter-573057505") == (
        "573057505"
    )
    assert parse_ypid("https://www.yellowpages.com/chicago-il/plumbers") is None
    assert parse_ypid(None) is None
    assert absolute_url("//i1.ypcdn.com/x.svg") == "https://i1.ypcdn.com/x.svg"
    assert absolute_url("/l/123") == "https://www.yellowpages.com/l/123"
    assert is_yellowpages_link("https://www.yellowpages.com/nationwide/mip/x-1")
    assert is_yellowpages_link("/chicago-il/mip/x-1")
    assert not is_yellowpages_link("https://alledelectricil.com")
