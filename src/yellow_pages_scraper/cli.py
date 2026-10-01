"""Command-line interface for yellow-pages-scraper.

Examples:
    yellow-pages-scraper search plumbers --location "Chicago, IL" --pretty
    yellow-pages-scraper search dentists "orthodontists" -l 90210 -l "Pasadena, CA" \\
        --sort rating --limit 60 --format csv --output dentists.csv
    yellow-pages-scraper search lawyers -l "Houston, TX" --limit 10 --details --pretty
    yellow-pages-scraper url "https://www.yellowpages.com/chicago-il/plumbers" --max-pages 2
    yellow-pages-scraper business https://www.yellowpages.com/chicago-il/mip/baethke-plumbing-15128363
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import Any

from . import __version__
from .export import to_csv, to_json
from .models import Business, SearchPage
from .parsing import YellowPagesError, YellowPagesNotFoundError
from .scraper import DEFAULT_PROXY_COUNTRY, YellowPagesScraper
from .urls import MAX_PAGES, PAGE_SIZE, SORTS, build_business_url, is_search_url

PROG = "yellow-pages-scraper"


def _output_options() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    out = common.add_argument_group("output and requests")
    out.add_argument(
        "-f",
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format (default: json).",
    )
    out.add_argument("-o", "--output", metavar="PATH", help="Write to this file, not stdout.")
    out.add_argument("--pretty", action="store_true", help="Pretty-print JSON (indented).")
    out.add_argument(
        "--proxy-country",
        default=DEFAULT_PROXY_COUNTRY,
        metavar="ISO",
        help=f"Country to route requests through (default: {DEFAULT_PROXY_COUNTRY}).",
    )
    out.add_argument(
        "--retries",
        type=int,
        default=3,
        metavar="N",
        help="Retries per page on timeouts and transient errors, with doubling backoff "
        "(default: 3).",
    )
    out.add_argument("-q", "--quiet", action="store_true", help="No progress output on stderr.")
    return common


def _collection_options(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("collection")
    group.add_argument(
        "-n",
        "--limit",
        type=int,
        default=PAGE_SIZE,
        metavar="N",
        help=f"Maximum number of businesses per search (default: {PAGE_SIZE}; "
        f"one request per {PAGE_SIZE}).",
    )
    group.add_argument(
        "--start-page",
        type=int,
        metavar="N",
        help=f"First results page to fetch (1-{MAX_PAGES}; default: 1, or the URL's page).",
    )
    group.add_argument(
        "--max-pages",
        type=int,
        metavar="N",
        help="Fetch at most N results pages per search (caps requests; default: until --limit).",
    )
    group.add_argument(
        "--include-ads",
        action="store_true",
        help="Also keep promoted listings from the ad blocks (marked sponsored).",
    )
    group.add_argument(
        "--details",
        action="store_true",
        help="Also fetch every business page: email, hours, geolocation, services, "
        "payment methods, social links, latest reviews (one extra request each).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Scrape Yellow Pages (yellowpages.com) business listings into clean JSON "
        "or CSV via the ScrapeUnblocker getPageSource API.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    common = _output_options()
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.required = True

    search = commands.add_parser(
        "search",
        parents=[common],
        help="Search Yellow Pages.",
        description="Search Yellow Pages. Every search term runs in every location; the "
        "results are merged and de-duplicated by business ID.",
    )
    search.add_argument(
        "terms",
        nargs="+",
        metavar="TERMS",
        help='What to look for, e.g. plumbers, "pizza", "auto repair". Repeatable.',
    )
    search.add_argument(
        "-l",
        "--location",
        dest="locations",
        action="append",
        required=True,
        metavar="PLACE",
        help='City and state ("Chicago, IL") or ZIP code (90210). Repeat for several.',
    )
    search.add_argument(
        "-s",
        "--sort",
        choices=tuple(SORTS),
        default="default",
        help="default (best match), distance, rating or name (A-Z).",
    )
    _collection_options(search)

    url = commands.add_parser(
        "url",
        parents=[common],
        help="Scrape a search or category URL copied from your browser.",
        description="Scrape a yellowpages.com /search?... URL or a category page such as "
        "/chicago-il/plumbers, as-is.",
    )
    url.add_argument("url", metavar="URL", help="A https://www.yellowpages.com/... results URL.")
    _collection_options(url)

    business = commands.add_parser(
        "business",
        parents=[common],
        help="Scrape one or more business pages.",
        description="Scrape business pages: contact details, email, hours, geolocation, "
        "services, payment methods, social links and the latest reviews.",
    )
    business.add_argument(
        "businesses",
        nargs="+",
        metavar="URL",
        help="Business page URL (https://www.yellowpages.com/<place>/mip/<name>-<id>).",
    )
    return parser


def validate(args: argparse.Namespace) -> None:
    """Check argument combinations argparse cannot express.

    Raises:
        ValueError: with a message suitable for ``parser.error``.
    """
    if args.format == "csv" and not args.output:
        raise ValueError("--format csv requires --output PATH")
    if args.retries < 0:
        raise ValueError("--retries must not be negative")
    if args.command in ("search", "url"):
        if args.limit < 1:
            raise ValueError("--limit must be at least 1")
        if args.start_page is not None and not 1 <= args.start_page <= MAX_PAGES:
            raise ValueError(f"--start-page must be between 1 and {MAX_PAGES}")
        if args.max_pages is not None and args.max_pages < 1:
            raise ValueError("--max-pages must be at least 1")
    if args.command == "search":
        args.terms = [t.strip() for t in args.terms if t.strip()]
        args.locations = [loc.strip() for loc in args.locations if loc.strip()]
        if not args.terms:
            raise ValueError("give at least one search term")
        if not args.locations:
            raise ValueError("give at least one --location")
    if args.command == "url" and not is_search_url(args.url):
        raise ValueError(
            "URL must be a https://www.yellowpages.com/search?... or category results URL"
        )
    if args.command == "business":
        for item in args.businesses:
            build_business_url(item)


def _say(line: str) -> None:
    try:
        print(line, file=sys.stderr)
    except UnicodeEncodeError:  # legacy console
        print(line.encode("ascii", "replace").decode("ascii"), file=sys.stderr)


def _page_progress(label: str):
    def report(page: SearchPage) -> None:
        total = f" of {page.total:,}" if page.total is not None else ""
        _say(f"[yellowpages] {label} page {page.page}: {len(page.businesses)} listings{total}")

    return report


def _retrying(attempt: int, delay: float, error: BaseException) -> None:
    reason = str(error) or type(error).__name__
    _say(f"[yellowpages] {reason[:200]}; retry {attempt} in {delay:g}s")


def _detail_failed(business: Business, error: BaseException) -> None:
    reason = str(error) or type(error).__name__
    _say(f"[yellowpages] {business.name}: {reason[:200]}; keeping the search result")


def _write_output(text: str, output: str | None) -> None:
    if output:
        with open(output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        # Business names carry curly quotes and accents; force UTF-8 so printing
        # on a legacy Windows console does not raise.
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
        print(text)


def _collect(args: argparse.Namespace, scraper: YellowPagesScraper) -> list[Business]:
    quiet = args.quiet
    collection = {
        "limit": args.limit,
        "start_page": args.start_page,
        "max_pages": args.max_pages,
        "include_ads": args.include_ads,
    }
    if args.command == "url":
        results = scraper.search_url(
            args.url, on_page=None if quiet else _page_progress("url"), **collection
        )
    else:
        seen: set[str] = set()
        results = []
        for terms in args.terms:
            for location in args.locations:
                label = f'"{terms}" in {location}'
                results += scraper.search(
                    terms,
                    location,
                    sort=args.sort,
                    seen=seen,
                    on_page=None if quiet else _page_progress(label),
                    **collection,
                )
    if args.details and results:
        if not quiet:
            _say(f"[yellowpages] fetching {len(results)} business pages")
        results = scraper.enrich(results, on_error=None if quiet else _detail_failed)
    return results


def run(args: argparse.Namespace, scraper: YellowPagesScraper) -> tuple[Any, int]:
    """Execute a parsed command. Returns ``(records, count)``."""
    if args.command == "business":
        results = []
        for item in args.businesses:
            business = scraper.get_business(item)
            if not args.quiet:
                _say(f"[yellowpages] {business.name} ({business.ypid})")
            results.append(business)
    else:
        results = _collect(args, scraper)
    if args.format == "csv":
        return to_csv(results, args.output), len(results)
    return results, len(results)


def _sdk_errors() -> tuple[type[BaseException], ...]:
    try:
        from scrapeunblocker import ScrapeUnblockerError  # type: ignore
    except Exception:  # pragma: no cover - depends on SDK availability
        return ()
    return (ScrapeUnblockerError,)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate(args)
    except ValueError as exc:
        parser.error(str(exc))

    scraper = YellowPagesScraper(
        proxy_country=args.proxy_country or None,
        retries=args.retries,
        on_retry=None if args.quiet else _retrying,
    )
    try:
        records, count = run(args, scraper)
    except YellowPagesNotFoundError as exc:
        print(f"error: {exc}.", file=sys.stderr)
        return 1
    except (YellowPagesError, *_sdk_errors()) as exc:
        reason = str(exc) or type(exc).__name__
        print(
            f"error: {reason[:300]}. Try again in a few minutes or raise --retries.",
            file=sys.stderr,
        )
        return 1

    if args.format == "json":
        _write_output(to_json(records, indent=2 if args.pretty else None), args.output)
    if args.output:
        print(f"Wrote {count} businesses to {args.output}", file=sys.stderr)
    elif count == 0:
        print("No businesses found.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
