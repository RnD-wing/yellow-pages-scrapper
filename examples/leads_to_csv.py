"""Build a local-business lead list: several trades x several cities, with details.

Each business page adds email, opening hours, geolocation and payment methods,
at one extra request per business, so keep LIMIT small while you try it out.

export SCRAPEUNBLOCKER_KEY=your_key_here
python examples/leads_to_csv.py
"""

from __future__ import annotations

from yellow_pages_scraper import YellowPagesScraper, to_csv

TRADES = ["roofing contractors", "hvac contractors"]
CITIES = ["Austin, TX", "Round Rock, TX"]
LIMIT = 5  # per trade and city


def main() -> None:
    yp = YellowPagesScraper()  # reads SCRAPEUNBLOCKER_KEY
    leads = yp.search_many(TRADES, CITIES, limit=LIMIT, details=True)

    with_email = [lead for lead in leads if lead.email]
    with_site = [lead for lead in leads if lead.website]
    print(f"{len(leads)} businesses, {len(with_email)} with email, {len(with_site)} with website")

    to_csv(leads, "leads.csv")
    print("Saved leads.csv")


if __name__ == "__main__":
    main()
