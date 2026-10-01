"""Turn Yellow Pages HTML into :class:`~yellow_pages_scraper.models.Business` records.

Search results are read from the listing cards (``div.result``). Business pages
are read from their schema.org JSON-LD block (address, geolocation, email,
opening hours, rating) plus the "More Info" section and the review list.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from .models import Business, Review, SearchPage
from .urls import absolute_url, build_business_url, is_yellowpages_link, parse_ypid


class YellowPagesError(Exception):
    """Base class for errors raised by this package."""


class YellowPagesParseError(YellowPagesError):
    """The page is not a recognisable Yellow Pages page (retried by the scraper)."""


class YellowPagesNotFoundError(YellowPagesError):
    """The business page does not exist (Yellow Pages answered 404)."""


# Star ratings are rendered as CSS classes: "result-rating four half" = 4.5.
_STAR_WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_LOCALITY = re.compile(r"^(?P<city>.+?),\s*(?P<state>[A-Z]{2})(?:\s+(?P<zip>\d{5}(?:-\d{4})?))?$")
_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_INT = re.compile(r"\d[\d,]*")
_PLACEHOLDER_SOCIAL = ("facebook.com/platform",)
_SOCIAL_HOSTS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "twitter.com": "twitter",
    "x.com": "x",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "pinterest.com": "pinterest",
    "tiktok.com": "tiktok",
    "yelp.com": "yelp",
    "foursquare.com": "foursquare",
}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def clean_text(value: Any) -> str | None:
    """Collapse whitespace (the API returns indented HTML) and drop empties."""
    if value is None:
        return None
    if isinstance(value, Tag):
        value = value.get_text(" ")
    text = " ".join(str(value).split())
    # Punctuation glued to the previous word in the source loses its space
    # once text nodes are joined back together ("Plumbers , Electricians").
    text = re.sub(r"\s+([,.;:!?)])", r"\1", text)
    return text or None


def _text(node: Tag | None, selector: str | None = None) -> str | None:
    if node is None:
        return None
    found = node.select_one(selector) if selector else node
    return clean_text(found) if found is not None else None


def to_int(value: Any) -> int | None:
    """First integer in ``value`` ("(64)" -> 64, "12 Years" -> 12, "1,201" -> 1201)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    match = _INT.search(str(value))
    return int(match.group().replace(",", "")) if match else None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def stars_from_classes(classes: list[str] | None) -> float | None:
    """``["result-rating", "four", "half"]`` -> ``4.5``."""
    if not classes:
        return None
    whole = next((_STAR_WORDS[c] for c in classes if c in _STAR_WORDS), None)
    if whole is None:
        return None
    return whole + (0.5 if "half" in classes else 0.0)


def split_locality(text: str | None) -> tuple[str | None, str | None, str | None]:
    """``"Chicago, IL 60625"`` -> ``("Chicago", "IL", "60625")``."""
    if not text:
        return None, None, None
    match = _LOCALITY.match(text.strip())
    if not match:
        return text.strip() or None, None, None
    return match.group("city").strip(), match.group("state"), match.group("zip")


def format_address(
    street: str | None, city: str | None, state: str | None, zip_code: str | None
) -> str | None:
    region = " ".join(part for part in (state, zip_code) if part)
    tail = ", ".join(part for part in (city, region) if part)
    full = ", ".join(part for part in (street, tail) if part)
    return full or None


def iso_date(value: str | None) -> str | None:
    """``"Edited: 02/23/2017"`` -> ``"2017-02-23"`` (Yellow Pages dates are US MM/DD/YYYY)."""
    if not value:
        return None
    match = _DATE.search(value)
    if not match:
        return None
    month, day, year = (int(g) for g in match.groups())
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year:04d}-{month:02d}-{day:02d}"


def _json_attr(node: Tag | None, name: str) -> dict[str, Any]:
    if node is None:
        return {}
    raw = node.get(name)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _split_list(text: str | None) -> list[str]:
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _website(href: str | None) -> str | None:
    """A business's own site; links that loop back to yellowpages.com are not one."""
    if not href or href.startswith("#") or is_yellowpages_link(href):
        return None
    return href.strip()


def _photo(url: str | None) -> str | None:
    """Image URL, or ``None`` for Yellow Pages' generic placeholder thumbnails."""
    if not url or "default-thumbnails" in url:
        return None
    return url


def social_network(url: str) -> str:
    host = re.sub(r"^https?://", "", url.lower()).split("/")[0]
    host = host[4:] if host.startswith("www.") else host
    for domain, name in _SOCIAL_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host or "link"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _looks_like_yellow_pages(soup: BeautifulSoup) -> bool:
    title = soup.title.get_text() if soup.title else ""
    return "Yellow Pages" in title or soup.select_one("#main-content, #bpp") is not None


# --------------------------------------------------------------------------- #
# Search results
# --------------------------------------------------------------------------- #


def parse_listing(node: Tag, *, sponsored: bool = False) -> Business | None:
    """Parse one ``div.result`` card. Returns ``None`` for cards without a business."""
    link = node.select_one("a.business-name")
    if link is None:
        return None
    analytics = {**_json_attr(node.select_one(".srp-listing"), "data-analytics")}
    analytics.update(_json_attr(node, "data-analytics"))

    href = absolute_url(link.get("href"))
    ypid = node.get("data-ypid") or analytics.get("ypid") or parse_ypid(href)
    try:
        url = build_business_url(href or "")
    except ValueError:
        url = href or ""
    name = clean_text(link)
    if not name or not ypid:
        return None

    rank = None
    heading = _text(node, "h2.n")
    if heading and not sponsored:
        match = re.match(r"(\d+)\.", heading)
        rank = int(match.group(1)) if match else None

    street = _text(node, ".adr .street-address")
    city, state, zip_code = split_locality(_text(node, ".adr .locality"))
    service_area = None
    if street is None and city is None:
        adr = _text(node, ".adr")
        if adr and adr.lower().startswith("serving"):
            service_area = adr
        elif adr:
            # Ad cards print the whole address on one line: "5701 W 73rd St, Chicago, IL 60638".
            city, state, zip_code = split_locality(adr)
            if city and ", " in city:
                street, city = city.rsplit(", ", 1)

    ratings = node.select_one(".ratings")
    stars = node.select_one(".ratings .result-rating")
    tripadvisor = _json_attr(ratings, "data-tripadvisor")

    website = None
    visit = node.select_one("a.track-visit-website")
    if visit is not None:
        website = _website(visit.get("href"))
    else:
        for anchor in node.select(".links a"):
            if clean_text(anchor) == "Website":
                website = _website(anchor.get("href"))
                break

    image = node.select_one(".media-thumbnail img")
    image_url = _photo(absolute_url(image.get("src")) if image is not None else None)
    listing_type = analytics.get("listing_type")
    snippet = _text(node, ".snippet .body")
    if snippet:
        snippet = snippet.strip('"').strip() or None

    return Business(
        ypid=str(ypid),
        name=name,
        url=url,
        rank=rank,
        categories=[t for t in (clean_text(a) for a in node.select(".categories a")) if t],
        phone=_text(node, ".phones") or _text(node, ".phone"),
        street=street,
        city=city,
        state=state,
        zip_code=zip_code,
        address=format_address(street, city, state, zip_code),
        service_area=service_area,
        website=website,
        rating=stars_from_classes(stars.get("class") if stars is not None else None),
        review_count=to_int(_text(node, ".ratings .count")),
        tripadvisor_rating=to_float(tripadvisor.get("rating")),
        tripadvisor_review_count=to_int(tripadvisor.get("count")),
        years_in_business=to_int(_text(node, ".years-in-business .count")),
        years_with_yp=to_int(_text(node, ".years-with-yp .count")),
        open_status=(_text(node, ".open-status") or "").lower() or None,
        amenities=[t for t in (clean_text(s) for s in node.select(".amenities-info span")) if t],
        snippet=snippet,
        image_url=image_url,
        advertiser=None if listing_type is None else listing_type != "free",
        sponsored=sponsored,
    )


def _showing(soup: BeautifulSoup) -> int | None:
    text = _text(soup, ".pagination .showing-count") or _text(soup, ".showing-count")
    if not text:
        return None
    match = re.search(r"of\s+([\d,]+)", text)
    return int(match.group(1).replace(",", "")) if match else None


def parse_search_page(html: str, *, url: str = "", page: int = 1) -> SearchPage:
    """Parse a search or category results page.

    Promoted cards from the "center ads" blocks are returned separately in
    ``SearchPage.ads``.

    Raises:
        YellowPagesParseError: when the HTML is not a Yellow Pages page at all
            (for example an interstitial or an empty response).
    """
    soup = _soup(html)
    if not _looks_like_yellow_pages(soup):
        raise YellowPagesParseError("unexpected page: no Yellow Pages search results found")

    businesses: list[Business] = []
    for node in soup.select("div.search-results.organic div.result"):
        business = parse_listing(node)
        if business is not None:
            businesses.append(business)

    organic_ids = {b.ypid for b in businesses}
    ads: list[Business] = []
    for node in soup.select("div.search-results.center-ads div.result"):
        ad = parse_listing(node, sponsored=True)
        if ad is not None and ad.ypid not in organic_ids:
            ads.append(ad)

    return SearchPage(
        url=url,
        page=page,
        businesses=businesses,
        ads=ads,
        total=_showing(soup),
        has_next=soup.select_one(".pagination a.next") is not None,
    )


def empty_search_page(*, url: str = "", page: int = 1) -> SearchPage:
    """What a search with no matches looks like (Yellow Pages answers it with a 404)."""
    return SearchPage(url=url, page=page, businesses=[], total=0, has_next=False)


# --------------------------------------------------------------------------- #
# Business pages
# --------------------------------------------------------------------------- #


def _ld_business(soup: BeautifulSoup) -> dict[str, Any]:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if not isinstance(item, dict):
                continue
            types = item.get("@type")
            types = types if isinstance(types, list) else [types]
            if "BreadcrumbList" not in types and ("address" in item or "telephone" in item):
                return item
    return {}


def _business_type(ld: dict[str, Any]) -> str | None:
    types = ld.get("@type")
    for value in types if isinstance(types, list) else [types]:
        if isinstance(value, str):
            name = value.rsplit("/", 1)[-1]
            # Some pages only declare the generic type; report nothing rather than that.
            if name and name != "LocalBusiness":
                return name
    return None


def _ld_services(ld: dict[str, Any]) -> list[str]:
    catalog = ld.get("hasOfferCatalog")
    if not isinstance(catalog, dict):
        return []
    names = []
    for offer in catalog.get("itemListElement") or []:
        item = offer.get("itemOffered") if isinstance(offer, dict) else None
        name = item.get("name") if isinstance(item, dict) else None
        if name:
            names.append(clean_text(html_lib.unescape(name)) or "")
    return [n for n in names if n]


def _info_section(soup: BeautifulSoup) -> dict[str, Tag]:
    """``{"Payment method": <dd>, ...}`` from the "More Info" definition list."""
    section: dict[str, Tag] = {}
    for dt in soup.select("#business-info dt"):
        dd = dt.find_next_sibling("dd")
        label = clean_text(dt)
        if label and isinstance(dd, Tag):
            section[label] = dd
    return section


def _other_info(dd: Tag) -> dict[str, str]:
    info: dict[str, str] = {}
    for p in dd.select("p") or [dd]:
        label = _text(p, "strong")
        text = clean_text(p) or ""
        if label:
            value = text[len(label) :] if text.startswith(label) else text
            info[label] = value.lstrip(" :").strip()
        elif text:
            info.setdefault("info", text)
    return info


def _social_links(dd: Tag) -> dict[str, str]:
    links: dict[str, str] = {}
    for anchor in dd.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href.startswith("http") or any(p in href for p in _PLACEHOLDER_SOCIAL):
            continue
        links.setdefault(social_network(href), href)
    return links


def _hours(soup: BeautifulSoup) -> list[dict[str, str]]:
    rows = []
    table = soup.select_one(".open-details")
    for tr in table.select("tr") if table is not None else []:
        days = _text(tr, "th")
        hours = _text(tr, "td")
        if days and hours:
            rows.append({"days": days.rstrip(":").strip(), "hours": hours})
    return rows


def parse_review(article: Tag) -> Review:
    rating_node = article.select_one(".result-ratings.overall .rating-indicator")
    if rating_node is None:
        rating_node = article.select_one(".rating-indicator")
    source = _text(article, ".attribution a")
    return Review(
        review_id=article.get("id") or None,
        author=_text(article, ".review-info .author") or _text(article, ".author"),
        date=iso_date(_text(article, ".date-posted")),
        rating=stars_from_classes(rating_node.get("class") if rating_node is not None else None),
        text=_text(article, ".review-response"),
        source=source,
    )


def parse_business_page(html: str, *, url: str = "") -> Business:
    """Parse a business page (``/<place>/mip/<name>-<id>``).

    Raises:
        YellowPagesParseError: when the HTML is not a Yellow Pages business page.
    """
    soup = _soup(html)
    ld = _ld_business(soup)
    header = soup.select_one("#main-header")
    if header is None and not ld:
        raise YellowPagesParseError("unexpected page: no Yellow Pages business details found")

    analytics = _json_attr(soup.select_one("#main-header [data-analytics]"), "data-analytics")
    canonical = None
    for candidate in (url, ld.get("@id")):
        try:
            canonical = build_business_url(candidate or "")
            break
        except ValueError:
            continue
    canonical = canonical or url
    ypid = analytics.get("ypid") or parse_ypid(canonical) or parse_ypid(ld.get("@id"))
    name = _text(soup, "h1.business-name") or clean_text(html_lib.unescape(ld.get("name") or ""))
    if not name or not ypid:
        raise YellowPagesParseError("unexpected page: business name or ID missing")

    info = _info_section(soup)

    address = ld.get("address") if isinstance(ld.get("address"), dict) else {}
    street = clean_text(address.get("streetAddress"))
    city = clean_text(address.get("addressLocality"))
    state = clean_text(address.get("addressRegion"))
    zip_code = clean_text(address.get("postalCode"))
    if not (street or city):
        street = _text(soup, "#default-ctas .address span")
        city, state, zip_code = split_locality(
            _text(soup, "#default-ctas .address span:nth-of-type(2)")
        )

    geo = ld.get("geo") if isinstance(ld.get("geo"), dict) else {}
    aggregate = ld.get("aggregateRating") if isinstance(ld.get("aggregateRating"), dict) else {}
    stars = soup.select_one("#main-header .rating-stars")

    website = _website(ld.get("url"))
    if website is None:
        link = soup.select_one("#main-header a.website-link, #default-ctas a.website-link")
        website = _website(link.get("href")) if link is not None else None

    email = ld.get("email")
    if isinstance(email, str) and email.strip():
        email = email.strip()
        email = email[7:] if email.lower().startswith("mailto:") else email
    else:
        email = None

    founded = to_int(ld.get("foundingDate"))
    opening = ld.get("openingHours")
    opening_hours = [opening] if isinstance(opening, str) else list(opening or [])

    services = _ld_services(ld)
    if not services and "Services/Products" in info:
        text = clean_text(info["Services/Products"])
        services = [text] if text else []

    def field_text(*labels: str) -> str | None:
        for label in labels:
            if label in info:
                return clean_text(info[label])
        return None

    def field_links(*labels: str) -> list[str]:
        for label in labels:
            if label in info:
                return [t for t in (clean_text(a) for a in info[label].select("a")) if t]
        return []

    languages = _split_list(field_text("Languages")) or _split_list(
        clean_text(ld.get("knowsLanguage"))
    )
    payment = _split_list(field_text("Payment method")) or _split_list(
        clean_text(ld.get("paymentAccepted"))
    )
    free = field_text("Free Estimates")
    aka_node = info.get("AKA")
    aka = []
    if aka_node is not None:
        parts = aka_node.select("p") or [aka_node]
        aka = [t for t in (clean_text(p) for p in parts) if t]

    other_links = []
    if "Other Link" in info or "Other Links" in info:
        dd = info.get("Other Link") or info.get("Other Links")
        for anchor in dd.select("a[href]") if dd is not None else []:
            href = _website(anchor.get("href"))
            if href and href not in other_links:
                other_links.append(href)

    other_info = _other_info(info["Other Information"]) if "Other Information" in info else {}
    image = ld.get("image") if isinstance(ld.get("image"), dict) else {}
    thumb = soup.select_one("#main-header img.biz-card-thumbnail")

    return Business(
        ypid=str(ypid),
        name=name,
        url=canonical,
        categories=field_links("Categories")
        or [t for t in (clean_text(a) for a in soup.select("#main-header .categories a")) if t],
        phone=clean_text(ld.get("telephone")) or _text(soup, "#main-header a.phone"),
        street=street,
        city=city,
        state=state,
        zip_code=zip_code,
        address=format_address(street, city, state, zip_code),
        website=website,
        rating=to_float(aggregate.get("ratingValue"))
        or stars_from_classes(stars.get("class") if stars is not None else None),
        review_count=to_int(aggregate.get("reviewCount"))
        or to_int(_text(soup, "#main-header .ratings .count")),
        years_in_business=to_int(_text(soup, "#main-header .years-in-business .count")),
        open_status=(_text(soup, "#main-header .status-text") or "").lower() or None,
        image_url=_photo(image.get("url"))
        or _photo(absolute_url(thumb.get("src")) if thumb is not None else None),
        has_details=True,
        business_type=_business_type(ld),
        email=email,
        latitude=to_float(geo.get("latitude")),
        longitude=to_float(geo.get("longitude")),
        founded=founded,
        description=field_text("General Info") or clean_text(ld.get("description")),
        aka=aka,
        hours=_hours(soup),
        opening_hours=[str(h) for h in opening_hours if h],
        services=services,
        brands=_split_list(field_text("Brands")),
        payment_methods=payment,
        languages=languages,
        neighborhoods=field_links("Neighborhoods", "Neighborhood"),
        ownership=field_text("Ownership"),
        free_estimates=None if free is None else free.lower().startswith("yes"),
        accreditation=field_text("Accreditation"),
        associations=field_text("Associations"),
        location_note=field_text("Location"),
        amenities=_split_list(field_text("Amenities")),
        other_info=other_info,
        social_links=_social_links(info["Social Links"]) if "Social Links" in info else {},
        other_links=other_links,
        reviews=[parse_review(a) for a in soup.select("#reviews article[id]")],
    )


__all__ = [
    "YellowPagesError",
    "YellowPagesParseError",
    "YellowPagesNotFoundError",
    "parse_listing",
    "parse_search_page",
    "empty_search_page",
    "parse_business_page",
    "parse_review",
    "clean_text",
    "stars_from_classes",
    "split_locality",
    "iso_date",
    "social_network",
]
