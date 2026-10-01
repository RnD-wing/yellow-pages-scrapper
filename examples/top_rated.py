"""Print the best-rated businesses of a kind in a city.

Listings carry either a Yellow Pages star rating or, for many restaurants, the
TripAdvisor rating Yellow Pages shows instead. This script uses whichever one a
listing has and skips listings with too few reviews.

export SCRAPEUNBLOCKER_KEY=your_key_here
python examples/top_rated.py pizza "Brooklyn, NY"
"""

from __future__ import annotations

import sys

from yellow_pages_scraper import Business, YellowPagesScraper

MIN_REVIEWS = 5


def score(biz: Business) -> tuple[float | None, int]:
    if biz.rating is not None:
        return biz.rating, biz.review_count or 0
    return biz.tripadvisor_rating, biz.tripadvisor_review_count or 0


def main() -> None:
    terms = sys.argv[1] if len(sys.argv) > 1 else "pizza"
    location = sys.argv[2] if len(sys.argv) > 2 else "Brooklyn, NY"

    yp = YellowPagesScraper()  # reads SCRAPEUNBLOCKER_KEY
    businesses = yp.search(terms, location, sort="rating", limit=60)

    ranked = []
    for biz in businesses:
        stars, reviews = score(biz)
        if stars is not None and reviews >= MIN_REVIEWS:
            ranked.append((stars, reviews, biz))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

    print(f"Top {terms} in {location} (at least {MIN_REVIEWS} reviews):")
    for stars, reviews, biz in ranked[:15]:
        print(f"  {stars:.1f}  ({reviews:>4} reviews)  {biz.name[:40]:<40}  {biz.phone or ''}")


if __name__ == "__main__":
    main()
