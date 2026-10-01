from __future__ import annotations

import csv
import json

from conftest import business_html, listing_html, search_html

from yellow_pages_scraper import (
    FIELDNAMES,
    business_row,
    parse_business_page,
    parse_search_page,
    to_csv,
    to_json,
)


def test_to_json_round_trip() -> None:
    biz = parse_business_page(business_html())
    data = json.loads(to_json([biz], indent=2))
    assert data[0]["name"] == "Baethke Plumbing"
    assert data[0]["reviews"][0]["author"] == "dude555"
    assert data[0]["hours"][0] == {"days": "Mon - Fri", "hours": "6:00 am - 7:00 pm"}
    assert json.loads(to_json(biz))["ypid"] == "15128363"


def test_business_row_flattens_lists_and_dicts() -> None:
    row = business_row(parse_business_page(business_html()))
    assert set(row) == set(FIELDNAMES)
    assert row["categories"] == "Plumbers | Water Heaters | Plumbing-Drain & Sewer Cleaning"
    assert row["payment_methods"] == "check | debit | visa"
    assert row["other_info"] == "Free Consultation: Yes | Parking: Street"
    assert row["social_links"].startswith("https://www.facebook.com/BaethkePlumbing")
    assert "reviews" not in row


def test_to_csv(tmp_path) -> None:
    page = parse_search_page(
        search_html([listing_html(1, stars=None), listing_html(2, rank=2)], has_next=False)
    )
    path = tmp_path / "out.csv"
    assert to_csv(page.businesses, str(path)) == 2
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == list(FIELDNAMES)
    assert rows[0]["rating"] == ""  # None -> empty cell
    assert rows[1]["rating"] == "4.5"
    assert rows[0]["sponsored"] == "false"
    assert rows[0]["categories"] == "Plumbers | Water Heaters"
