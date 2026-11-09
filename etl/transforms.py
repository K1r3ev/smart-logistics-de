from __future__ import annotations

import math
from typing import Optional


BODY_GROUP_STD = {
    56: ("Тент", 56),
    57: ("Тент", 56),
    58: ("Тент", 56),
    59: ("Тент", 56),
    60: ("Тент", 56),
    61: ("Тент", 56),
    4: ("Рефрижератор", 4),
    46: ("Рефрижератор", 4),
    47: ("Рефрижератор", 4),
    48: ("Рефрижератор", 4),
    2: ("Изотерм", 2),
    1: ("Борт", 15),
    15: ("Борт", 15),
}


def map_body_group(body_type_id: Optional[int]) -> tuple[str, Optional[int]]:
    if body_type_id is None:
        return "Не указан", None
    mapped = BODY_GROUP_STD.get(int(body_type_id))
    if mapped:
        return mapped
    return "Прочие", int(body_type_id)


def weight_category(total_weight: float) -> str:
    w = round(float(total_weight) + 1e-12, 1)
    if w >= 30:
        return "G20T"
    if w >= 10:
        return "FTL"
    if w >= 5:
        return "10T"
    if w >= 2.5:
        return "5T"
    if w >= 0.5:
        return "L5T"
    return "OTH"


def volume_category(total_volume: float) -> str:
    v = float(total_volume)
    if 0 < v <= 120:
        return "FTL"
    return "OTH"


def parse_region(full_name_local: Optional[str]) -> str:
    if not full_name_local:
        return "UNKNOWN"
    parts = [p.strip() for p in str(full_name_local).split(",", 1)]
    if len(parts) == 2 and parts[1]:
        return parts[1]
    return parts[0] or "UNKNOWN"


def cyclical(value: float, period: float) -> tuple[float, float]:
    angle = 2.0 * math.pi * float(value) / period
    return math.sin(angle), math.cos(angle)