from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit

import pytest
from conftest import (
    FakeClient,
    FakeNotFound,
    TransientError,
    ad_html,
    business_html,
    listing_html,
    search_html,
)

from yellow_pages_scraper import (
    YellowPagesNotFoundError,
    YellowPagesParseError,
    YellowPagesScraper,
)


def make_scraper(responses, **kwargs) -> tuple[YellowPagesScraper, FakeClient, list[float]]:
    client = FakeClient(responses)
    sleeps: list[float] = []
    scraper = YellowPagesScraper(
        client=client,
        transient_errors=(TransientError,),
        sleep=sleeps.append,
        **kwargs,
    )
    return scraper, client, sleeps


def page(*ids: int, has_next: bool = True, ads: list[str] | None = None) -> str:
    return search_html(
        [listing_html(i, rank=n) for n, i in enumerate(ids, 1)], ads=ads, has_next=has_next
    )


def page_param(url: str) -> str | None:
    return dict(parse_qsl(urlsplit(url).query)).get("page")


def test_search_builds_url_routes_through_us_and_labels_results() -> None:
    scraper, client, _ = make_scraper([page(1, 2)])
    result = scraper.search("plumbers", "Chicago, IL", sort="rating", limit=2)
    assert [b.ypid for b in result] == ["1", "2"]
    assert all(b.query == "plumbers" and b.query_location == "Chicago, IL" for b in result)
    url, country = client.calls[0]
    assert url == (
        "https://www.yellowpages.com/search?search_terms=plumbers"
        "&geo_location_terms=Chicago%2C+IL&s=average_rating"
    )
    assert country == "US"


def test_pagination_until_limit() -> None:
    scraper, client, _ = make_scraper([page(1, 2, 3), page(4, 5, 6), page(7, 8, 9)])
    result = scraper.search("plumbers", "Chicago, IL", limit=5)
    assert [b.ypid for b in result] == ["1", "2", "3", "4", "5"]
    assert [page_param(url) for url, _ in client.calls] == [None, "2"]


def test_max_pages_and_start_page() -> None:
    scraper, client, _ = make_scraper([page(1, 2), page(3, 4)])
    result = scraper.search("plumbers", "Chicago, IL", limit=100, start_page=3, max_pages=2)
    assert [b.ypid for b in result] == ["1", "2", "3", "4"]
    assert [page_param(url) for url, _ in client.calls] == ["3", "4"]
    with pytest.raises(ValueError):
        scraper.search("plumbers", "Chicago, IL", max_pages=0)
    with pytest.raises(ValueError):
        scraper.search("plumbers", "Chicago, IL", limit=0)


def test_stops_on_last_page_and_on_repeated_page() -> None:
    scraper, client, _ = make_scraper([page(1, 2, has_next=False)])
    assert len(scraper.search("plumbers", "Chicago, IL", limit=100)) == 2
    assert len(client.calls) == 1

    scraper, client, _ = make_scraper([page(1, 2), page(1, 2)])
    assert [b.ypid for b in scraper.search("plumbers", "Chicago, IL", limit=100)] == ["1", "2"]
    assert len(client.calls) == 2


def test_seen_ids_are_skipped_but_collection_continues() -> None:
    scraper, client, _ = make_scraper([page(1, 2), page(3, 4)])
    result = scraper.search("plumbers", "Chicago, IL", limit=2, seen={"1", "2"})
    assert [b.ypid for b in result] == ["3", "4"]
    assert len(client.calls) == 2


def test_ads_only_when_asked() -> None:
    html = page(1, 2, has_next=False, ads=[ad_html(99)])
    scraper, _, _ = make_scraper([html, html])
    assert [b.ypid for b in scraper.search("plumbers", "Chicago, IL")] == ["1", "2"]
    with_ads = scraper.search("plumbers", "Chicago, IL", include_ads=True)
    assert [(b.ypid, b.sponsored) for b in with_ads] == [("1", False), ("2", False), ("99", True)]


def test_no_results_404_is_an_empty_search() -> None:
    scraper, client, sleeps = make_scraper([FakeNotFound("Requested element not found")])
    assert scraper.search("zzqxv", "Boise, ID") == []
    assert len(client.calls) == 1 and sleeps == []


def test_transient_errors_are_retried_with_doubling_backoff() -> None:
    retries: list[tuple[int, float]] = []
    scraper, client, sleeps = make_scraper(
        [TransientError("timeout"), TransientError("502"), page(1, has_next=False)],
        backoff=2,
        on_retry=lambda attempt, delay, _exc: retries.append((attempt, delay)),
    )
    assert [b.ypid for b in scraper.search("plumbers", "Chicago, IL")] == ["1"]
    assert sleeps == [2.0, 4.0]
    assert retries == [(1, 2.0), (2, 4.0)]
    assert len(client.calls) == 3


def test_unrecognised_pages_are_retried_then_raised() -> None:
    bad = "<html><head><title>Just a moment</title></head></html>"
    scraper, client, sleeps = make_scraper([bad, bad, bad], retries=2, backoff=1, max_backoff=1)
    with pytest.raises(YellowPagesParseError):
        scraper.search("plumbers", "Chicago, IL")
    assert len(client.calls) == 3
    assert sleeps == [1.0, 1.0]


def test_non_transient_errors_are_not_retried() -> None:
    scraper, client, _ = make_scraper([RuntimeError("bad key")])
    with pytest.raises(RuntimeError):
        scraper.search("plumbers", "Chicago, IL")
    assert len(client.calls) == 1


def test_search_url_accepts_category_pages_and_rejects_others() -> None:
    scraper, client, _ = make_scraper([page(1, has_next=False)])
    result = scraper.search_url("https://www.yellowpages.com/chicago-il/plumbers?page=2")
    assert [b.ypid for b in result] == ["1"]
    assert page_param(client.calls[0][0]) == "2"
    with pytest.raises(ValueError):
        scraper.search_url("https://www.yellowpages.com/chicago-il/mip/x-1")


def test_search_many_runs_every_pair_and_dedupes() -> None:
    scraper, client, _ = make_scraper(
        [
            page(1, 2, has_next=False),
            page(2, 3, has_next=False),
            page(4, has_next=False),
            page(1, 5, has_next=False),
        ]
    )
    pages: list[tuple[str, str]] = []
    result = scraper.search_many(
        ["plumbers", " ", "electricians"],
        ["Chicago, IL", "Evanston, IL"],
        limit=10,
        on_page=lambda terms, loc, _page: pages.append((terms, loc)),
    )
    assert [b.ypid for b in result] == ["1", "2", "3", "4", "5"]
    assert [(b.query, b.query_location) for b in result] == [
        ("plumbers", "Chicago, IL"),
        ("plumbers", "Chicago, IL"),
        ("plumbers", "Evanston, IL"),
        ("electricians", "Chicago, IL"),
        ("electricians", "Evanston, IL"),
    ]
    assert pages == [
        ("plumbers", "Chicago, IL"),
        ("plumbers", "Evanston, IL"),
        ("electricians", "Chicago, IL"),
        ("electricians", "Evanston, IL"),
    ]
    assert len(client.calls) == 4  # the blank search term is skipped


def test_get_business_and_not_found() -> None:
    scraper, client, _ = make_scraper([business_html()])
    biz = scraper.get_business("/chicago-il/mip/baethke-plumbing-15128363?lid=77#reviews")
    assert biz.name == "Baethke Plumbing" and biz.has_details
    assert client.calls[0][0] == (
        "https://www.yellowpages.com/chicago-il/mip/baethke-plumbing-15128363?lid=77"
    )

    scraper, _, _ = make_scraper([FakeNotFound("gone")])
    with pytest.raises(YellowPagesNotFoundError):
        scraper.get_business("https://www.yellowpages.com/chicago-il/mip/gone-123")
    with pytest.raises(ValueError):
        scraper.get_business("https://www.yellowpages.com/chicago-il/plumbers")


def test_details_merge_keeps_search_only_fields() -> None:
    listing = listing_html(15128363, rank=7, tripadvisor={"rating": "4.0", "count": "3"})
    scraper, client, _ = make_scraper([search_html([listing], has_next=False), business_html()])
    (biz,) = scraper.search("plumbers", "Chicago, IL", details=True)
    assert len(client.calls) == 2
    assert biz.has_details is True
    assert biz.rank == 7  # from the search page
    assert biz.snippet == "From Business: Licensed, bonded and insured."
    assert biz.tripadvisor_rating == 4.0  # the business page does not repeat it
    assert biz.email == "office@baethkeplumbing.example"
    assert biz.address == "3511 N Cicero Ave, Chicago, IL 60641"  # page beats the card
    assert biz.query == "plumbers"


def test_enrich_keeps_search_result_when_a_page_fails() -> None:
    scraper, _, _ = make_scraper([page(1, 2, has_next=False)])
    found = scraper.search("plumbers", "Chicago, IL")
    failures: list[str] = []
    scraper, _, _ = make_scraper([FakeNotFound("gone"), business_html()], retries=0)
    enriched = scraper.enrich(found, on_error=lambda b, _exc: failures.append(b.ypid))
    assert failures == ["1"]
    assert enriched[0].has_details is False
    assert enriched[1].has_details is True
