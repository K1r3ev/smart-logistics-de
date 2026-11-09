from __future__ import annotations

from typing import Optional


def classify_reason(row: dict) -> Optional[str]:
    """Return the first DQ failure reason code, or None if the row is clean."""
    reasons: list[str] = []
    price = float(row["price"])
    currency = str(row["currency_code"])
    distance = float(row["distance"])
    weight = float(row["total_weight"])
    volume = float(row["total_volume"])

    if price <= 0:
        reasons.append("non_positive_price")
    elif currency == "643" and price <= 1000:
        reasons.append("rub_source_validation_low_price")

    if distance <= 0:
        reasons.append("non_positive_distance")
    if weight < 0:
        reasons.append("negative_weight")
    if volume < 0:
        reasons.append("negative_volume")
    if not row["loading_city_ok"] or not row["unloading_city_ok"]:
        reasons.append("unknown_city")

    if currency != "643":
        if row["nearest_rate_date"] is None or row["fx_rate"] is None:
            reasons.append("missing_fx_rate")

    return reasons[0] if reasons else None