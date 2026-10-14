"""Festival / seasonal calendar used as forecast features (dates are Gregorian).

VERIFY BEFORE RELYING: Diwali 2026 = Sunday 8 Nov 2026 was confirmed from several sources on 2026-10-13.
All other dates were entered from memory and must be re-checked against a panchang/official calendar.
Add new years here every year - the model only knows the dates listed.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

FESTIVALS: Dict[str, List[date]] = {
    # Lakshmi Puja night (the firecracker peak). Several regions celebrate a day apart.
    "diwali": [date(2022, 10, 24), date(2023, 11, 12), date(2024, 11, 1), date(2025, 10, 20),
               date(2026, 11, 8), date(2027, 10, 29)],
    "dussehra": [date(2022, 10, 5), date(2023, 10, 24), date(2024, 10, 12), date(2025, 10, 2),
                 date(2026, 10, 20), date(2027, 10, 9)],
    "holi": [date(2022, 3, 18), date(2023, 3, 8), date(2024, 3, 25), date(2025, 3, 14),
             date(2026, 3, 4), date(2027, 3, 22)],
    "new_year_eve": [date(y, 12, 31) for y in range(2022, 2029)],
}

CLIP = 10  # days; beyond +/-CLIP a festival is "far" and clipped


def signed_days_to_nearest(day: date, festival: str) -> int:
    """Days from `day` to the nearest occurrence (negative = the festival was in the past), clipped to +/-CLIP."""
    best: Optional[int] = None
    for f in FESTIVALS[festival]:
        d = (f - day).days
        if best is None or abs(d) < abs(best):
            best = d
    return max(-CLIP, min(CLIP, best if best is not None else CLIP))


def in_stubble_season(day: date) -> int:
    """North India crop-residue burning window (approx. 15 Oct - 30 Nov)."""
    md = (day.month, day.day)
    return int((10, 15) <= md <= (11, 30))


def festival_features(day: date) -> Dict[str, float]:
    return {
        "d_diwali": signed_days_to_nearest(day, "diwali"),
        "d_dussehra": signed_days_to_nearest(day, "dussehra"),
        "d_holi": signed_days_to_nearest(day, "holi"),
        "d_newyear": signed_days_to_nearest(day, "new_year_eve"),
        "stubble": in_stubble_season(day),
    }


def upcoming(day: date, within_days: int = 14) -> List[dict]:
    out = []
    for name, dates in FESTIVALS.items():
        for f in dates:
            delta = (f - day).days
            if 0 <= delta <= within_days:
                out.append({"festival": name, "date": f.isoformat(), "in_days": delta})
    return sorted(out, key=lambda x: x["in_days"])
