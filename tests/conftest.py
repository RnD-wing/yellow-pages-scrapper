"""Shared fixtures: synthetic Yellow Pages pages shaped like the real ones.

The markup mirrors what the ScrapeUnblocker ``getPageSource`` API returns for
yellowpages.com, so the tests run offline and spend no API credit.
"""

from __future__ import annotations

import json
from typing import Any

import pytest


def listing_html(
    ypid: int,
    *,
    rank: int | None = 1,
    name: str | None = None,
    listing_type: str = "free",
    lid: int | None = None,
    phone: str = "(312) 555-0100",
    street: str | None = "100 N State St",
    locality: str | None = "Chicago, IL 60602",
    serving: str | None = None,
    website: str | None = "https://example-plumbing.com",
    stars: str | None = "four half",
    review_count: int | None = 12,
    tripadvisor: dict[str, str] | None = None,
    years_in_business: int | None = 25,
    years_with_yp: int | None = None,
    open_status: str = "open now",
    amenities: list[str] | None = None,
    snippet: str | None = "From Business: Licensed, bonded and insured.",
    image: str = "https://i2.ypcdn.com/blob/abc_130x130_crop.jpg",
) -> str:
    name = name or f"Plumber {ypid}"
    href = f"/chicago-il/mip/plumber-{ypid}" + (f"?lid={lid}" if lid else "")
    analytics = json.dumps({"ypid": str(ypid), "listing_type": listing_type, "rank": rank})
    heading = f"{rank}. " if rank else ""
    ratings = ""
    if stars:
        ratings = (
            f'<a class="rating" href="{href}#yp-rating"><div class="result-rating {stars}"></div>'
            f'<span class="count">({review_count})</span></a>'
        )
    ta_attr = f" data-tripadvisor='{json.dumps(tripadvisor)}'" if tripadvisor else ""
    links = ""
    if website:
        links += f'<a class="track-visit-website" href="{website}">Website</a>'
    links += f'<a class="track-more-info" href="{href}">More Info</a>'
    badges = ""
    if years_in_business:
        badges += (
            '<div class="years-in-business"><div class="count">'
            f"<strong>{years_in_business} Years</strong></div>"
            '<div class="label">in Business</div></div>'
        )
    if years_with_yp:
        badges += (
            f'<div class="years-with-yp"><div class="count"><strong>{years_with_yp} Years</strong>'
            ' with</div><div class="label">Yellow Pages</div></div>'
        )
    amenity_html = ""
    if amenities:
        spans = "".join(f"<span>{a}</span>" for a in amenities)
        amenity_html = f'<div class="amenities"><div class="amenities-info">{spans}</div></div>'
    if serving:
        adr = f'<div class="adr">{serving}</div>'
    else:
        adr = '<div class="adr">'
        if street:
            adr += f'<div class="street-address">{street}</div>'
        if locality:
            adr += f'<div class="locality">{locality}</div>'
        adr += "</div>"
    snippet_html = f'<div class="snippet"><p class="body"><span>{snippet}</span></p></div>'
    return f"""
<div class="result" data-ypid="{ypid}" data-analytics='{analytics}' id="lid-{ypid}">
 <div class="srp-listing clickable-area">
  <div class="v-card">
   <div class="media-thumbnail"><a href="{href}#gallery"><img alt="" src="{image}"/></a></div>
   <div class="info">
    <div class="info-section info-primary">
     <h2 class="n">
      {heading}<a class="business-name" href="{href}"><span>{name}</span></a>
     </h2>
     <div class="categories">
      <a href="https://www.yellowpages.com/chicago-il/plumbers">Plumbers</a>
      <a href="https://www.yellowpages.com/chicago-il/water-heaters">Water Heaters</a>
     </div>
     <div class="ratings" data-israteable="true"{ta_attr}>{ratings}</div>
     <div class="links">{links}</div>
     <div class="badges">{badges}</div>
     {amenity_html}
    </div>
    <div class="info-section info-secondary">
     <div class="phones phone primary">{phone}</div>
     {adr}
     <div class="open-status open now">{open_status}</div>
    </div>
    {snippet_html if snippet else ""}
   </div>
  </div>
 </div>
</div>"""


def ad_html(ypid: int, *, name: str | None = None) -> str:
    """A promoted card from a "center ads" block (different markup from organic)."""
    analytics = json.dumps({"ypid": str(ypid), "listing_type": "sub"})
    return f"""
<div class="result flash-endt">
 <div class="srp-listing clickable-area paid-listing" data-analytics='{analytics}'>
  <div class="v-card"><div class="info">
   <div class="info-section info-primary">
    <h2 class="n"><a class="business-name" href="/nationwide/mip/ad-{ypid}?lid=9{ypid}">
      {name or f"Advertiser {ypid}"}</a></h2>
    <div class="categories"><a href="/chicago-il/plumbers">Plumbers</a></div>
    <div class="links">
     <a href="https://www.yellowpages.com/nationwide/mip/ad-{ypid}?lid=8{ypid}">Website</a>
    </div>
   </div>
   <div class="info-section info-secondary">
    <div class="phone">(855) 555-0199</div>
    <p class="adr">Serving the Chicago area.</p>
   </div>
   <span class="ad-pill">Ad</span>
  </div></div>
 </div>
</div>"""


def search_html(
    listings: list[str],
    *,
    ads: list[str] | None = None,
    total: int | None = 954,
    page: int = 1,
    has_next: bool = True,
) -> str:
    showing = ""
    if total is not None:
        start = (page - 1) * 30 + 1
        showing = (
            f'<span class="showing-count">Showing {start}-{start + 29} of {total:,}'
            '<span class="result-info">More info</span></span>'
        )
    nxt = (
        f'<a class="next ajax-page" href="/search?search_terms=x&amp;page={page + 1}">Next</a>'
        if has_next
        else ""
    )
    ad_block = '<div class="search-results center-ads">' + "".join(ads or []) + "</div>"
    return f"""<!DOCTYPE html><html><head>
<title>Best 30 Plumbers in Chicago, IL with Reviews | The Real Yellow Pages</title></head>
<body><div id="main-content">
{ad_block}
<div class="search-results organic">{"".join(listings)}</div>
<div class="pagination">{showing}<ul><li>{nxt}</li></ul></div>
</div></body></html>"""


def business_ld(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": ["http://schema.org/Plumber", "LocalBusiness"],
        "@id": "/chicago-il/mip/baethke-plumbing-15128363",
        "name": "Baethke Plumbing",
        "description": "Family plumbing company.",
        "address": {
            "@type": "PostalAddress",
            "addressCountry": "US",
            "streetAddress": "3511 N Cicero Ave",
            "addressLocality": "Chicago",
            "addressRegion": "IL",
            "postalCode": "60641",
        },
        "geo": {"@type": "GeoCoordinates", "latitude": 41.94512, "longitude": -87.746765},
        "telephone": "(312) 697-1550",
        "url": "https://www.baethkeplumbing.com",
        "email": "mailto:office@baethkeplumbing.example",
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": 5, "reviewCount": 64},
        "paymentAccepted": "check, visa, cash",
        "foundingDate": "1993",
        "openingHours": ["Mo-Fr 06:00-19:00", "Sa 07:00-12:00"],
        "knowsLanguage": "English, Polish",
        "hasOfferCatalog": {
            "@type": "OfferCatalog",
            "itemListElement": [
                {"@type": "Offer", "itemOffered": {"@type": "Service", "name": "Drain Cleaning"}},
                {
                    "@type": "Offer",
                    "itemOffered": {"@type": "Service", "name": "Owner&apos;s Water Heaters"},
                },
            ],
        },
        "image": {"@type": "ImageObject", "url": "https://i2.ypcdn.com/blob/f2d6"},
    }
    data.update(overrides)
    return data


def business_html(ld: dict[str, Any] | None = None, *, info: str | None = None) -> str:
    ld = business_ld() if ld is None else ld
    analytics = json.dumps({"ypid": "15128363", "listing_type": "free"})
    if info is None:
        info = """
  <dt>General Info</dt><dd class="general-info">Plumbing and remodeling since 1993.</dd>
  <dt>Email</dt><dd><a class="email-business" href="/cdn-cgi/l/email-protection#00">
    Email Business</a></dd>
  <dt>Services/Products</dt><dd>Drain Cleaning Water Heaters</dd>
  <dt>Ownership</dt><dd class="ownership">Locally Owned</dd>
  <dt>Brands</dt><dd class="brands">bradford white, rheem</dd>
  <dt>Payment method</dt><dd class="payment">check, debit, visa</dd>
  <dt>Free Estimates</dt><dd class="free-estimates">Yes</dd>
  <dt class="neighborhoods">Neighborhoods</dt><dd class="neighborhoods">
    <span><a href="/northwest-side-chicago-il/plumbers">Northwest Side</a>,</span>
    <span><a href="/portage-park-chicago-il/plumbers">Portage Park</a></span></dd>
  <dt>Languages</dt><dd class="languages">English, Polish, Spanish</dd>
  <dt>AKA</dt><dd class="aka"><p>Baethke Plumbing Inc</p><p>Baethke &amp; Sons</p></dd>
  <dt>Location</dt><dd class="location-description">Near Addison St</dd>
  <dt>Amenities</dt><dd class="amenities">Free Parking,Emergency Service</dd>
  <dt>Accreditation</dt><dd class="accreditation">Licensed Master Plumber</dd>
  <dt>Associations</dt><dd class="associations">PHCC</dd>
  <dt class="weblinks">Other Link</dt><dd class="weblinks">
    <p><a class="other-links" href="https://www.baethkeplumbing.com">website</a></p>
    <p><a class="other-links" href="https://www.yellowpages.com/chicago-il/plumbers">yp</a></p>
  </dd>
  <dt>Social Links</dt><dd class="social-links">
    <a class="fb-link" href="http://www.facebook.com/platform">f</a>
    <a class="fb-link" href="https://www.facebook.com/BaethkePlumbing">f</a>
    <a href="https://www.instagram.com/baethke/">i</a></dd>
  <dt class="categories">Categories</dt><dd class="categories"><div class="categories">
    <a href="/chicago-il/plumbers">Plumbers</a>,
    <a href="/chicago-il/water-heaters">Water Heaters</a>,
    <a href="/chicago-il/plumbing-drain-sewer-cleaning">Plumbing-Drain &amp; Sewer Cleaning</a>
  </div></dd>
  <dt>Other Information</dt><dd class="other-information">
    <p><strong>Free Consultation</strong>:\u00a0Yes</p>
    <p><strong>Parking</strong>:\u00a0Street</p></dd>
"""
    return f"""<!DOCTYPE html><html><head>
<title>Baethke Plumbing - Chicago, IL 60641</title>
<script type="application/ld+json">{json.dumps(ld)}</script>
<script type="application/ld+json">{{"@context":"https://schema.org","@type":"BreadcrumbList"}}</script>
</head><body><main id="bpp">
<header id="main-header"><article class="business-card">
 <a class="media-thumbnail" data-analytics='{analytics}' href="#">
   <img class="biz-card-thumbnail" src="https://i2.ypcdn.com/blob/f2d6_150x150_crop.jpg"/></a>
 <div class="sales-info"><h1 class="dockable business-name">Baethke Plumbing</h1></div>
 <section class="primary-info">
  <div class="categories"><a href="/chicago-il/plumbers">Plumbers</a></div>
  <section class="ratings"><a class="yp-ratings"><div class="rating-stars five"></div>
   <span class="count">(64)</span></a></section>
  <div class="time-info"><div class="status-text closed now">closed now</div></div>
  <div class="additional-attributes"><div class="years-in-business"><div class="count">
   <strong>33 Years</strong></div><div class="label">in Business</div></div></div>
 </section>
</article></header>
<section id="default-ctas"><a class="phone" href="tel:3126971550">(312) 697-1550</a>
 <a class="website-link" href="https://www.baethkeplumbing.com">Visit Website</a></section>
<div class="open-details"><span class="hour-category">Regular Hours</span><table>
 <tr><th class="day-label">Mon - Fri:</th><td class="day-hours">
   <time datetime="Mo-Fr 06:00-19:00">6:00 am - 7:00 pm</time></td></tr>
 <tr><th class="day-label">Sat:</th><td class="day-hours">7:00 am - 12:00 pm</td></tr>
 <tr><th class="day-label">Sun</th><td class="day-hours">Closed</td></tr>
</table></div>
<section id="business-info"><h2 class="section-title">More Info</h2><dl>{info}</dl></section>
<section id="reviews">
 <article class="clearfix" id="rev-1"><div class="entry">
  <div class="review-info"><a class="author" href="/user/1/reviews">dude555</a>
   <div class="review-dates"><span class="date-posted updated">Edited:\u00a002/23/2017</span>
   </div></div>
  <div class="result-ratings overall"><div class="rating-indicator five"></div></div>
  <div class="review-response"><p>Great techs, clear explanations.</p></div>
 </div></article>
 <article class="clearfix has-attribution" id="rev-2"><div class="entry">
  <div class="review-info"><div class="author">Shirley W.</div>
   <div class="review-dates"><p class="date-posted"><span>08/27/2024</span></p>
    <span class="attribution">Provided by <a href="">DexKnows</a></span></div></div>
  <div class="result-ratings overall"><div class="rating-indicator three half"></div></div>
  <div class="review-response"><p>Quick response.</p></div>
 </div></article>
</section>
</main></body></html>"""


class FakeClient:
    """Stands in for ``scrapeunblocker.Client``: replays queued responses."""

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str | None]] = []

    def get_page_source(self, url: str, *, proxy_country: str | None = None) -> str:
        self.calls.append((url, proxy_country))
        if not self.responses:
            raise AssertionError(f"unexpected request: {url}")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            return response(url)
        return response


class TransientError(Exception):
    """A retryable API failure in tests."""


class FakeNotFound(Exception):
    """Mimics the SDK's NotFoundError: the target page answered 404."""

    status_code = 404


@pytest.fixture
def one_page() -> str:
    return search_html([listing_html(1, rank=1), listing_html(2, rank=2)], has_next=False)
