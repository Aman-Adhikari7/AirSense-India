"""python -m app.jobs.seed_places  - load/refresh the India places catalogue (safe to re-run)."""
from ..db import SessionLocal, init_db
from ..services.places import seed_places

if __name__ == "__main__":
    init_db()
    with SessionLocal() as db:
        print(f"inserted {seed_places(db)} new places")
