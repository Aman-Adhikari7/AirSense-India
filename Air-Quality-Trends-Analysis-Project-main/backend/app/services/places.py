"""The India places catalogue. Only catalogue places can be collected/queried (no free-text geocoding)."""
from __future__ import annotations

import csv
import os
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Place

CATALOGUE_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "india_places.csv")


class PlaceNotFound(RuntimeError):
    pass


class AmbiguousPlace(RuntimeError):
    pass


def resolve_place(db: Session, text: str) -> Place:
    """'Delhi' or 'Aurangabad, Bihar' -> Place. Case-insensitive; raises PlaceNotFound / AmbiguousPlace."""
    name, _, state = (p.strip() for p in text.partition(","))
    q = select(Place).where(func.lower(Place.name) == name.lower())
    if state:
        q = q.where(func.lower(Place.state) == state.lower())
    matches = db.execute(q.order_by(Place.id)).scalars().all()
    if not matches:
        raise PlaceNotFound(f"PlaceNotFound: '{text}' is not in the India places catalogue")
    if len(matches) > 1:
        states = ", ".join(sorted({m.state or "?" for m in matches}))
        raise AmbiguousPlace(f"AmbiguousPlace: '{name}' exists in several states ({states}); use 'Name, State'")
    return matches[0]


def seed_places(db: Session, path: Optional[str] = None) -> int:
    """Insert catalogue rows that do not exist yet (idempotent). Returns the number inserted."""
    inserted = 0
    with open(path or CATALOGUE_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            exists = db.execute(
                select(Place.id).where(Place.name == row["name"], Place.state == row["state"])
            ).first()
            if exists:
                continue
            db.add(Place(name=row["name"], state=row["state"], kind=row["kind"],
                         latitude=float(row["lat"]), longitude=float(row["lon"])))
            inserted += 1
    db.commit()
    return inserted


def seed_if_empty(db: Session) -> int:
    if db.execute(select(func.count()).select_from(Place)).scalar():
        return 0
    return seed_places(db)
