from __future__ import annotations

import pytest
from conftest import ad_html, business_html, business_ld, listing_html, search_html

from yellow_pages_scraper import (
    YellowPagesParseError,
    parse_business_page,
    parse_search_page,
)
from yellow_pages_scraper.parsing import (
    clean_text,
    iso_date,
    social_network,
    split_locality,
    stars_from_classes,
)


def test_listing_fields() -> None:
    html = search_html(
        [
            listing_html(
                579608019,
                rank=1,
                name="ALL ED ELECTRIC",
                listing_type="sub",
                lid=1002195574696,
                years_with_yp=3,
                amenities=["Wheelchair accessible"],
            )
        ]
    )
    page = parse_search_page(html, url="u", page=1)
    assert page.total == 954
    assert page.has_next is True
    (biz,) = page.businesses
    assert biz.ypid == "579608019"
    assert biz.name == "ALL ED ELECTRIC"
    assert biz.url == (
        "https://www.yellowpages.com/chicago-il/mip/plumber-579608019?lid=1002195574696"
    )
    assert biz.rank == 1
    assert biz.categories == ["Plumbers", "Water Heaters"]
    assert biz.phone == "(312) 555-0100"
    assert (biz.street, biz.city, biz.state, biz.zip_code) == (
        "100 N State St",
        "Chicago",
        "IL",
        "60602",
    )
    assert biz.address == "100 N State St, Chicago, IL 60602"
    assert biz.website == "https://example-plumbing.com"
    assert biz.rating == 4.5
    assert biz.review_count == 12
    assert biz.years_in_business == 25
    assert biz.years_with_yp == 3
    assert biz.open_status == "open now"
    assert biz.amenities == ["Wheelchair accessible"]
    assert biz.snippet == "From Business: Licensed, bonded and insured."
    assert biz.image_url.startswith("https://i2.ypcdn.com/")
    assert biz.advertiser is True
    assert biz.sponsored is False
    assert biz.has_details is False


def test_listing_without_rating_tripadvisor_and_service_area() -> None:
    html = search_html(
        [
            listing_html(
                7,
                stars=None,
                tripadvisor={"rating": "4.5", "count": "8"},
                serving="Serving the Chicago Area",
                website=None,
                years_in_business=None,
                image="https://i2.ypcdn.com/ypu/images/default-thumbnails-v2/thumbnail-2.svg",
            )
        ]
    )
    (biz,) = parse_search_page(html).businesses
    assert biz.rating is None and biz.review_count is None
    assert biz.tripadvisor_rating == 4.5
    assert biz.tripadvisor_review_count == 8
    assert biz.service_area == "Serving the Chicago Area"
    assert biz.street is None and biz.address is None
    assert biz.website is None
    assert biz.years_in_business is None
    assert biz.image_url is None  # placeholder thumbnail
    assert biz.advertiser is False


def test_website_link_back_to_yellow_pages_is_not_a_website() -> None:
    html = search_html(
        [listing_html(3, website="https://www.yellowpages.com/nationwide/mip/x-3?lid=1")]
    )
    assert parse_search_page(html).businesses[0].website is None


def test_ads_are_separated_and_deduplicated_against_organic() -> None:
    html = search_html(
        [listing_html(1), listing_html(2, rank=2)],
        ads=[ad_html(2), ad_html(99, name="Best Home Savings")],
    )
    page = parse_search_page(html)
    assert [b.ypid for b in page.businesses] == ["1", "2"]
    (ad,) = page.ads
    assert ad.ypid == "99"
    assert ad.sponsored is True
    assert ad.rank is None
    assert ad.phone == "(855) 555-0199"
    assert ad.service_area == "Serving the Chicago area."
    assert ad.website is None


def test_last_page_and_empty_page() -> None:
    page = parse_search_page(search_html([listing_html(1)], has_next=False))
    assert page.has_next is False
    empty = parse_search_page(search_html([], total=None, has_next=False))
    assert empty.businesses == [] and empty.total is None


def test_unrecognised_page_raises_parse_error() -> None:
    with pytest.raises(YellowPagesParseError):
        parse_search_page("<html><head><title>Just a moment...</title></head></html>")


def test_business_page_fields() -> None:
    biz = parse_business_page(
        business_html(), url="https://www.yellowpages.com/chicago-il/mip/baethke-plumbing-15128363"
    )
    assert biz.has_details is True
    assert biz.ypid == "15128363"
    assert biz.name == "Baethke Plumbing"
    assert biz.url == "https://www.yellowpages.com/chicago-il/mip/baethke-plumbing-15128363"
    assert biz.business_type == "Plumber"
    assert biz.email == "office@baethkeplumbing.example"
    assert biz.phone == "(312) 697-1550"
    assert biz.address == "3511 N Cicero Ave, Chicago, IL 60641"
    assert (biz.latitude, biz.longitude) == (41.94512, -87.746765)
    assert biz.website == "https://www.baethkeplumbing.com"
    assert (biz.rating, biz.review_count) == (5.0, 64)
    assert biz.founded == 1993
    assert biz.years_in_business == 33
    assert biz.open_status == "closed now"
    assert biz.description == "Plumbing and remodeling since 1993."
    assert biz.hours == [
        {"days": "Mon - Fri", "hours": "6:00 am - 7:00 pm"},
        {"days": "Sat", "hours": "7:00 am - 12:00 pm"},
        {"days": "Sun", "hours": "Closed"},
    ]
    assert biz.opening_hours == ["Mo-Fr 06:00-19:00", "Sa 07:00-12:00"]
    assert biz.services == ["Drain Cleaning", "Owner's Water Heaters"]
    assert biz.brands == ["bradford white", "rheem"]
    assert biz.payment_methods == ["check", "debit", "visa"]
    assert biz.languages == ["English", "Polish", "Spanish"]
    assert biz.neighborhoods == ["Northwest Side", "Portage Park"]
    assert biz.aka == ["Baethke Plumbing Inc", "Baethke & Sons"]
    assert biz.ownership == "Locally Owned"
    assert biz.free_estimates is True
    assert biz.location_note == "Near Addison St"
    assert biz.amenities == ["Free Parking", "Emergency Service"]
    assert biz.accreditation == "Licensed Master Plumber"
    assert biz.associations == "PHCC"
    assert biz.categories == ["Plumbers", "Water Heaters", "Plumbing-Drain & Sewer Cleaning"]
    assert biz.other_info == {"Free Consultation": "Yes", "Parking": "Street"}
    # the generic "facebook.com/platform" placeholder link is dropped
    assert biz.social_links == {
        "facebook": "https://www.facebook.com/BaethkePlumbing",
        "instagram": "https://www.instagram.com/baethke/",
    }
    assert biz.other_links == ["https://www.baethkeplumbing.com"]
    assert biz.image_url == "https://i2.ypcdn.com/blob/f2d6"


def test_business_reviews() -> None:
    first, second = parse_business_page(business_html()).reviews
    assert first.review_id == "rev-1"
    assert first.author == "dude555"
    assert first.date == "2017-02-23"
    assert first.rating == 5.0
    assert first.text == "Great techs, clear explanations."
    assert first.source is None
    assert second.author == "Shirley W."
    assert second.date == "2024-08-27"
    assert second.rating == 3.5
    assert second.source == "DexKnows"


def test_business_page_with_sparse_data_falls_back_to_html() -> None:
    ld = business_ld(
        **{"@type": ["http://schema.org/LocalBusiness", "LocalBusiness"]},
    )
    for key in ("email", "aggregateRating", "url", "hasOfferCatalog", "paymentAccepted"):
        ld.pop(key)
    biz = parse_business_page(business_html(ld, info=""))
    assert biz.business_type is None  # generic type only
    assert biz.email is None
    assert biz.rating == 5.0  # from the header stars
    assert biz.review_count == 64
    assert biz.website == "https://www.baethkeplumbing.com"  # from the Visit Website button
    assert biz.services == []
    assert biz.payment_methods == []
    assert biz.languages == ["English", "Polish"]  # from JSON-LD knowsLanguage
    assert biz.description == "Family plumbing company."
    assert biz.categories == ["Plumbers"]  # header categories


def test_business_page_without_markup_raises() -> None:
    with pytest.raises(YellowPagesParseError):
        parse_business_page("<html><body>Access denied</body></html>")


@pytest.mark.parametrize(
    ("classes", "expected"),
    [
        (["result-rating", "five"], 5.0),
        (["result-rating", "four", "half"], 4.5),
        (["rating-indicator", "one"], 1.0),
        (["result-rating"], None),
        (None, None),
    ],
)
def test_stars_from_classes(classes, expected) -> None:
    assert stars_from_classes(classes) == expected


def test_helpers() -> None:
    assert split_locality("Chicago, IL 60625") == ("Chicago", "IL", "60625")
    assert split_locality("Beverly Hills, CA") == ("Beverly Hills", "CA", None)
    assert split_locality("Springfield") == ("Springfield", None, None)
    assert iso_date("Edited:\u00a002/23/2017") == "2017-02-23"
    assert iso_date("13/45/2020") is None
    assert iso_date(None) is None
    assert clean_text("  Plumbers ,\n   Electricians  ") == "Plumbers, Electricians"
    assert social_network("https://www.facebook.com/x") == "facebook"
    assert social_network("https://m.yelp.com/biz/x") == "yelp"
    assert social_network("https://example.org/x") == "example.org"
