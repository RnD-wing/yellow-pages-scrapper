"""Search Yellow Pages and save the listings as JSON.

export SCRAPEUNBLOCKER_KEY=your_key_here
python examples/search_to_json.py plumbers "Chicago, IL"
"""

from __future__ import annotations

import sys

from yellow_pages_scraper import YellowPagesScraper, to_json


def main() -> None:
    terms = sys.argv[1] if len(sys.argv) > 1 else "plumbers"
    location = sys.argv[2] if len(sys.argv) > 2 else "Chicago, IL"

    yp = YellowPagesScraper()  # reads SCRAPEUNBLOCKER_KEY
    businesses = yp.search(terms, location, limit=30)

    for biz in businesses[:5]:
        place = biz.address or biz.service_area or ""
        print(f"{biz.rank:>2}. {biz.name[:40]:<40}  {biz.phone or '':<15}  {place}")

    with open("yellowpages.json", "w", encoding="utf-8") as fh:
        fh.write(to_json(businesses, indent=2))
    print(f"Saved {len(businesses)} businesses to yellowpages.json")


if __name__ == "__main__":
    main()
