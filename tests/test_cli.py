from __future__ import annotations

import csv
import json

import pytest
from conftest import FakeClient, FakeNotFound, business_html, listing_html, search_html

from yellow_pages_scraper import YellowPagesScraper, cli


def parse(argv: list[str]):
    parser = cli.build_parser()
    args = parser.parse_args(argv)
    cli.validate(args)
    return args


def scraper_for(responses) -> YellowPagesScraper:
    return YellowPagesScraper(
        client=FakeClient(responses), transient_errors=(), sleep=lambda _: None
    )


def test_search_arguments() -> None:
    args = parse(
        [
            "search",
            "plumbers",
            " electricians ",
            "-l",
            "Chicago, IL",
            "--location",
            "60614",
            "--sort",
            "rating",
            "-n",
            "60",
            "--max-pages",
            "2",
            "--include-ads",
            "--details",
        ]
    )
    assert args.command == "search"
    assert args.terms == ["plumbers", "electricians"]
    assert args.locations == ["Chicago, IL", "60614"]
    assert args.sort == "rating"
    assert args.limit == 60 and args.max_pages == 2
    assert args.include_ads and args.details
    assert args.format == "json" and args.proxy_country == "US" and args.retries == 3


def test_defaults() -> None:
    args = parse(["search", "pizza", "-l", "Brooklyn, NY"])
    assert args.sort == "default"
    assert args.limit == 30
    assert args.start_page is None and args.max_pages is None
    assert not args.details and not args.include_ads


@pytest.mark.parametrize(
    "argv",
    [
        ["search", "plumbers"],  # --location is required
        ["search", "plumbers", "-l", "Chicago, IL", "--sort", "price"],
        ["search", "plumbers", "-l", "Chicago, IL", "-f", "csv"],  # csv needs --output
        ["search", "plumbers", "-l", "Chicago, IL", "--limit", "0"],
        ["search", "plumbers", "-l", "Chicago, IL", "--start-page", "101"],
        ["search", "plumbers", "-l", "Chicago, IL", "--max-pages", "0"],
        ["search", "plumbers", "-l", "Chicago, IL", "--retries", "-1"],
        ["search", " ", "-l", "Chicago, IL"],
        ["search", "plumbers", "-l", " "],
        ["url", "https://example.com/search?search_terms=x"],
        ["business", "https://www.yellowpages.com/chicago-il/plumbers"],
    ],
)
def test_invalid_arguments_exit(argv) -> None:
    with pytest.raises(SystemExit):
        cli.main(argv)


def test_run_search_json(capsys) -> None:
    args = parse(["search", "plumbers", "-l", "Chicago, IL", "-l", "Evanston, IL", "-q"])
    scraper = scraper_for(
        [
            search_html([listing_html(1), listing_html(2, rank=2)], has_next=False),
            search_html([listing_html(2), listing_html(3, rank=2)], has_next=False),
        ]
    )
    records, count = cli.run(args, scraper)
    assert count == 3
    assert [r.ypid for r in records] == ["1", "2", "3"]
    assert records[2].query_location == "Evanston, IL"
    assert capsys.readouterr().err == ""


def test_run_search_csv_with_details(tmp_path) -> None:
    out = tmp_path / "plumbers.csv"
    args = parse(
        ["search", "plumbers", "-l", "Chicago, IL", "--details", "-q", "-f", "csv", "-o", str(out)]
    )
    scraper = scraper_for([search_html([listing_html(15128363)], has_next=False), business_html()])
    written, count = cli.run(args, scraper)
    assert written == count == 1
    with open(out, encoding="utf-8-sig", newline="") as fh:
        (row,) = list(csv.DictReader(fh))
    assert row["ypid"] == "15128363"
    assert row["email"] == "office@baethkeplumbing.example"
    assert row["has_details"] == "true"
    assert row["hours"].startswith("Mon - Fri: 6:00 am - 7:00 pm | ")


def test_run_business_command() -> None:
    args = parse(["business", "https://www.yellowpages.com/chicago-il/mip/baethke-15128363", "-q"])
    records, count = cli.run(args, scraper_for([business_html()]))
    assert count == 1 and records[0].email == "office@baethkeplumbing.example"


def test_main_reports_missing_business(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli, "YellowPagesScraper", lambda **_kwargs: scraper_for([FakeNotFound("gone")])
    )
    code = cli.main(["business", "https://www.yellowpages.com/chicago-il/mip/gone-1", "-q"])
    assert code == 1
    assert "not found" in capsys.readouterr().err


def test_main_prints_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "YellowPagesScraper",
        lambda **_kwargs: scraper_for([search_html([listing_html(1)], has_next=False)]),
    )
    assert cli.main(["search", "plumbers", "-l", "Chicago, IL", "-q", "--pretty"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["ypid"] == "1"
    assert data[0]["query"] == "plumbers"
