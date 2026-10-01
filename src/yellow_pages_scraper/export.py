"""JSON and CSV export for yellow-pages-scraper records."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, is_dataclass
from typing import Any

from .models import Business

# CSV columns, in order. List fields are joined with " | "; reviews are only
# exported to JSON (a CSV row keeps the business-level rating and count).
FIELDNAMES: tuple[str, ...] = (
    "ypid",
    "name",
    "rank",
    "categories",
    "phone",
    "email",
    "website",
    "street",
    "city",
    "state",
    "zip_code",
    "address",
    "service_area",
    "latitude",
    "longitude",
    "rating",
    "review_count",
    "tripadvisor_rating",
    "tripadvisor_review_count",
    "years_in_business",
    "years_with_yp",
    "founded",
    "open_status",
    "hours",
    "business_type",
    "description",
    "services",
    "brands",
    "payment_methods",
    "languages",
    "neighborhoods",
    "amenities",
    "aka",
    "ownership",
    "free_estimates",
    "accreditation",
    "associations",
    "other_info",
    "social_links",
    "other_links",
    "snippet",
    "image_url",
    "advertiser",
    "sponsored",
    "has_details",
    "url",
    "query",
    "query_location",
)

SEPARATOR = " | "


def _plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def to_json(records: Any, *, indent: int | None = None) -> str:
    """Serialize a business, or a list of businesses, to a JSON string."""
    return json.dumps(_plain(records), ensure_ascii=False, indent=indent)


def business_row(business: Business) -> dict[str, Any]:
    """Flatten a :class:`Business` into a CSV row."""
    data = asdict(business)
    row: dict[str, Any] = {name: data.get(name) for name in FIELDNAMES}
    for name in (
        "categories",
        "services",
        "brands",
        "payment_methods",
        "languages",
        "neighborhoods",
        "amenities",
        "aka",
        "other_links",
    ):
        row[name] = SEPARATOR.join(data.get(name) or [])
    row["hours"] = SEPARATOR.join(f"{h['days']}: {h['hours']}" for h in business.hours)
    row["other_info"] = SEPARATOR.join(f"{k}: {v}" for k, v in business.other_info.items())
    row["social_links"] = SEPARATOR.join(business.social_links.values())
    return row


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_csv(rows: Sequence[dict[str, Any]], path: str) -> int:
    """Write already-flattened rows to ``path``. Returns the number of rows."""
    # utf-8-sig so Excel opens names with accents and curly quotes correctly.
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(FIELDNAMES), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _cell(row.get(name)) for name in FIELDNAMES})
    return len(rows)


def to_csv(businesses: Iterable[Business], path: str) -> int:
    """Write businesses to ``path`` as CSV. Returns the number of rows."""
    return write_csv([business_row(b) for b in businesses], path)


__all__ = ["FIELDNAMES", "SEPARATOR", "to_json", "to_csv", "business_row", "write_csv"]
