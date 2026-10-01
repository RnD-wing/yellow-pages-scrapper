# Yellow Pages Scraper

[![CI](https://github.com/ScrapeUnblocker/yellow-pages-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/ScrapeUnblocker/yellow-pages-scraper/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Powered by ScrapeUnblocker](https://img.shields.io/badge/powered%20by-ScrapeUnblocker-6f42c1.svg)](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)

**Scrape [Yellow Pages](https://www.yellowpages.com) (yellowpages.com) business listings into clean JSON or CSV.**
Search any kind of business in any US city or ZIP code and get the name, phone, full
address, website, categories, star rating, review count and years in business for every
listing. Turn on `--details` to also get the email address, opening hours, geolocation,
services, payment methods, languages, social links and the latest reviews.

Powered by [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos):
the `getPageSource` API loads each Yellow Pages page in a real browser and returns the
HTML, and this package turns it into typed records. You don't need to run proxies,
headless browsers or retry logic yourself.

## Features

- **Search like the website does.** Any search term (`plumbers`, `pizza`, `auto repair`,
  a business name) in any city and state or ZIP code. Sort by best match, distance,
  rating or name.
- **Category pages and browser URLs.** Scrape `/chicago-il/plumbers` or a
  `/search?...` URL copied from your browser as-is.
- **Rich, typed listings.** Each record has the Yellow Pages ID, name, rank, categories,
  phone, street, city, state, ZIP, service area, website, YP star rating and review count,
  TripAdvisor rating, years in business, years with Yellow Pages, open status, amenities,
  snippet, photo and an advertiser flag.
- **Business details.** `--details` (or `get_business()`) adds the email, opening hours
  (human-readable and schema.org), latitude/longitude, year founded, business type,
  description, services, brands, payment methods, languages, neighborhoods, ownership,
  free estimates, accreditations, social links and the latest reviews.
- **Multi-page, multi-city collection.** 30 listings per page, up to Yellow Pages' limit of
  3,000 results. You can cap requests with `--max-pages`. Several search terms and
  locations run in one go, de-duplicated by business ID.
- **Clean results.** Promoted cards from the ad blocks are dropped unless you ask for them
  (`--include-ads`). Placeholder photos, and "website" links that just loop back to
  yellowpages.com, are set to `null`.
- **Resilient.** Timeouts, transient API errors and unrecognisable pages are retried with
  doubling backoff. A search with no matches returns an empty list, not an error.
- **JSON or CSV output.** CSV has one row per business with list fields joined by `" | "`,
  written as UTF-8 with a BOM so Excel reads it cleanly.
- **CLI + Python library.** Fully typed, and tested offline with a mocked client.

## Install

```bash
git clone https://github.com/ScrapeUnblocker/yellow-pages-scraper.git
cd yellow-pages-scraper
pip install .
```

Get an API key at [scrapeunblocker.com](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos)
and expose it as `SCRAPEUNBLOCKER_KEY` (the official SDK reads it from there):

```bash
export SCRAPEUNBLOCKER_KEY=your_key_here        # Windows PowerShell: $env:SCRAPEUNBLOCKER_KEY="your_key_here"
```

You can also copy `.env.example` to `.env` and load it with your tool of choice.

## CLI usage

```bash
# Plumbers in Chicago, first page (30 listings)
yellow-pages-scraper search plumbers --location "Chicago, IL" --pretty

# Dentists around two ZIP codes, best rated first, 60 per location, to CSV
yellow-pages-scraper search dentists -l 90210 -l 90024 --sort rating --limit 60 \
    --format csv --output dentists.csv

# A lead list with email, hours and geolocation (one extra request per business)
yellow-pages-scraper search "roofing contractors" "hvac contractors" -l "Austin, TX" \
    --limit 10 --details -f csv -o austin_leads.csv

# A category page or a search URL copied from your browser
yellow-pages-scraper url "https://www.yellowpages.com/austin-tx/roofing-contractors" --max-pages 3

# One or more business pages
yellow-pages-scraper business \
    "https://www.yellowpages.com/austin-tx/mip/j-conn-roofing-repair-service-inc-458552965" --pretty
```

| Option | Meaning |
| --- | --- |
| `TERMS ...` | One or more search terms: a business type, category or name |
| `-l, --location` | City and state (`"Chicago, IL"`) or ZIP code (`90210`); repeat for several |
| `-s, --sort` | `default` (best match), `distance`, `rating` or `name` (A-Z) |
| `-n, --limit` | Maximum businesses per term and location (default 30 = one page) |
| `--start-page`, `--max-pages` | Where to start and how many pages to fetch at most |
| `--details` | Fetch every business page too (email, hours, geolocation, services, reviews, ...) |
| `--include-ads` | Keep promoted listings from the ad blocks (`sponsored: true`) |
| `-f, --format json\|csv`, `-o, --output` | Output format and file (CSV needs `--output`) |
| `--proxy-country` | Country to route requests through (default `US`) |
| `--retries` | Retries per page on transient errors (default 3) |

Run `yellow-pages-scraper <command> --help` for every option. `python -m yellow_pages_scraper`
works too.

## Library usage

```python
from yellow_pages_scraper import YellowPagesScraper, to_csv

yp = YellowPagesScraper()  # reads SCRAPEUNBLOCKER_KEY; or YellowPagesScraper(api_key="...")

plumbers = yp.search("plumbers", "Chicago, IL", sort="rating", limit=60)
for biz in plumbers[:5]:
    print(biz.rating, biz.review_count, biz.name, biz.phone, biz.address)

# Several trades x several cities, de-duplicated, with business-page details
leads = yp.search_many(
    ["roofing contractors", "hvac contractors"],
    ["Austin, TX", "Round Rock, TX"],
    limit=10,
    details=True,
)
print([lead.email for lead in leads if lead.email])

# A category page or browser URL, and a single business page
roofers = yp.search_url("https://www.yellowpages.com/austin-tx/roofing-contractors", limit=90)
biz = yp.get_business(roofers[0].url)
print(biz.hours, biz.latitude, biz.longitude, biz.payment_methods)

to_csv(leads, "leads.csv")
```

To de-duplicate across your own calls, pass the same `seen=set()` to each `search()`.
`enrich(businesses)` adds business-page details to search results you already have.

### Examples

| Script | What it does |
| --- | --- |
| [`examples/search_to_json.py`](examples/search_to_json.py) | Search and save the listings as JSON |
| [`examples/leads_to_csv.py`](examples/leads_to_csv.py) | Trades x cities lead list with email, hours and website, to CSV |
| [`examples/top_rated.py`](examples/top_rated.py) | Best-rated businesses of a kind in a city, using YP or TripAdvisor ratings |

## Example output

`yellow-pages-scraper business <url> --pretty` (reviewer name redacted, review text and
service list shortened):

```json
[
  {
    "ypid": "458552965",
    "name": "J-Conn Roofing & Repair Service Inc",
    "url": "https://www.yellowpages.com/austin-tx/mip/j-conn-roofing-repair-service-inc-458552965?lid=1002186231623",
    "rank": null,
    "categories": ["Roofing Contractors"],
    "phone": "(512) 524-9558",
    "street": "7302 Elm Forest Road",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78745",
    "address": "7302 Elm Forest Road, Austin, TX 78745",
    "service_area": null,
    "website": "https://j-connroofing.com",
    "rating": 5.0,
    "review_count": 3,
    "tripadvisor_rating": null,
    "tripadvisor_review_count": null,
    "years_in_business": 47,
    "years_with_yp": null,
    "open_status": "closed now",
    "amenities": [],
    "snippet": null,
    "image_url": "https://i4.ypcdn.com/blob/a514b9e1986a1422de831f567bae02347c28f526",
    "advertiser": null,
    "sponsored": false,
    "has_details": true,
    "business_type": "RoofingContractor",
    "email": "info@j-connroofing.com",
    "latitude": 30.194273,
    "longitude": -97.800255,
    "founded": 1979,
    "description": "J-Conn Roofing & Repair Service, Inc. is locally family owned and operated roofing contractor. ...",
    "aka": [],
    "hours": [
      {"days": "Mon - Fri", "hours": "7:30 am - 5:00 pm"},
      {"days": "Sat - Sun", "hours": "Closed"}
    ],
    "opening_hours": ["Mo-Fr 07:30-17:00"],
    "services": ["Roof Repair", "Roof Leak Repair", "Roof Replacement", "Hail Damage Roof Repair", "..."],
    "brands": ["Certainteed", "GAF", "Owens Corning"],
    "payment_methods": ["check", "discover", "visa", "amex", "cash", "mastercard"],
    "languages": ["English", "Spanish"],
    "neighborhoods": ["Elm Wood Estates"],
    "ownership": "Locally Owned, Family Owned",
    "free_estimates": true,
    "accreditation": "Better Business Bureau Austin Roofing Contractors Association ...",
    "associations": "BBB Accredited Business",
    "location_note": "Austin-Westlake-Oak Hill-Round Rock-Cedar Park-Buda-Bee Cave-Lakeway-Leander-Pflugerville--Manchaca",
    "other_info": {},
    "social_links": {
      "facebook": "https://www.facebook.com/JConnRoofingRepair",
      "twitter": "https://twitter.com/JConnRoofing",
      "youtube": "https://www.youtube.com/user/JConnRoofing",
      "foursquare": "https://foursquare.com/v/jconn-roofing--repair-services-inc/510965ff45b0d888589b4bcb",
      "yelp": "http://www.yelp.com/biz/j-conn-roofing-and-repair-service-inc-austin-2"
    },
    "other_links": ["https://j-connroofing.com"],
    "reviews": [
      {
        "review_id": "85c5818a-a20f-4b9b-b586-cf41e1cc5061",
        "author": "<reviewer>",
        "date": "2014-05-05",
        "rating": 5.0,
        "text": "We've used J-Conn twice. Once was for a repair and most recently for a full roof replacement. ...",
        "source": null
      }
    ],
    "query": null,
    "query_location": null
  }
]
```

Field notes:

- Search results fill everything down to `sponsored`. `rank` is the position on the results
  page, and `snippet` is the "From Business" blurb or a review excerpt. Business pages
  (`has_details: true`) add the fields from `business_type` onward and replace the card
  fields with the page's own values. With `--details`, the search-only fields (`rank`,
  `snippet`, `advertiser`, `sponsored`, `query`, `query_location`) are kept.
- `rating` / `review_count` are Yellow Pages' own star ratings. Many restaurants show a
  TripAdvisor rating instead (`tripadvisor_rating` / `tripadvisor_review_count`). The
  `rating` sort takes both into account.
- `advertiser` is `true` for listings from Yellow Pages advertisers, which rank first under
  the default sort.
- `email` only exists when the business published one, and only on business pages.
- `hours` is what the page shows. `opening_hours` is the same data in schema.org format
  (`Mo-Fr 07:30-17:00`), which is easier to parse.
- `reviews` holds the latest reviews shown on the business page (up to 10). Dates are ISO
  `YYYY-MM-DD`, and `source` names the partner site when a review was syndicated.
- Chains with a "Serving the Chicago Area" card have a `service_area` and no street
  address.
- Yellow Pages caps every search at 3,000 results (100 pages). To go wider, split the
  search by ZIP code or neighbouring cities, and let the de-duplication merge the results.

## Project layout

```
yellow-pages-scraper/
├── src/yellow_pages_scraper/
│   ├── __init__.py      # public API + __version__
│   ├── scraper.py       # YellowPagesScraper: fetching, retries, pagination, dedupe, details
│   ├── parsing.py       # listing cards, business pages (JSON-LD + HTML), reviews
│   ├── urls.py          # search / business URL builders, sorts, page helpers
│   ├── models.py        # Business, Review and SearchPage dataclasses
│   ├── export.py        # JSON and CSV export
│   ├── cli.py           # argparse CLI (yellow-pages-scraper)
│   └── __main__.py      # python -m yellow_pages_scraper
├── examples/            # runnable scripts
├── tests/               # offline tests with a mocked client (no API calls)
├── pyproject.toml
├── Makefile
└── .github/workflows/ci.yml
```

## Development

```bash
python -m venv .venv && source .venv/bin/activate
make install      # pip install -e ".[dev]"
make lint         # ruff check
make format       # ruff format
make test         # pytest (offline, no API key needed)
pre-commit install
```

The tests replay synthetic Yellow Pages pages through a fake client. They spend no API
credit and run in CI on Python 3.9 and 3.12.

## Responsible use

Scrape at a reasonable pace and respect Yellow Pages' terms of use. Business listings
include contact details, and some belong to sole proprietors. If you store them or use them
for outreach, laws such as CAN-SPAM, the TCPA and the GDPR / CCPA apply. This project is
not affiliated with or endorsed by Yellow Pages.

## Links

- [ScrapeUnblocker](https://scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos) - the web scraping API behind this project
- [ScrapeUnblocker documentation](https://docs.scrapeunblocker.com/?utm_source=github&utm_medium=integration&utm_campaign=example-repos) - `getPageSource`, SDKs, parsing options
- [Python SDK on PyPI](https://pypi.org/project/scrapeunblocker/) - `pip install scrapeunblocker`

## License

[MIT](LICENSE) - Copyright (c) 2026 ScrapeUnblocker
