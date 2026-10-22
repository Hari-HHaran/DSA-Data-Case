"""Reset and seed the demo database:  python -m app.seed  (from backend/)."""
import sys

import numpy as np
from sqlalchemy import update

from ..config import get_settings
from ..database import Base, SessionLocal, engine
from ..models import CommercialOpportunity, NotificationEvent, PurchasingEvent, SalesFollowup
from ..services import forecasting, opportunities, workflow
from ..services.clock import utcnow
from .history import seed_history
from .reference import seed_reference
from .synthetic import prospect_events, seed_master_and_purchasing, seed_other_master_data


def reset_schema():
    import app.models  # noqa: F401  (register tables)
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    url = get_settings().database_url
    with engine.begin() as conn:
        if url.startswith("sqlite"):
            # Drop in place (FKs off) so a running API server keeps valid connections.
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            names = [r[0] for r in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            for name in names:
                conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{name}"')
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        else:
            Base.metadata.drop_all(conn)
            conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")


def seed(quiet: bool = False):
    settings = get_settings()
    rng = np.random.default_rng(settings.synthetic_seed)
    reset_schema()
    for f in settings.upload_dir.glob("*"):
        if f.name != ".gitkeep":
            f.unlink()
    with SessionLocal() as db:
        users = seed_reference(db)
        seed_other_master_data(db)
        info = seed_master_and_purchasing(db, rng, users)
        hist = seed_history(db, users, rng)
        db.bulk_insert_mappings(PurchasingEvent, prospect_events(rng, hist["pr_links"]))
        db.flush()
        run = forecasting.run(db, users["priya"])
        opp = opportunities.refresh(db)
        _seed_opportunity_progress(db, users)
        sla = workflow.run_sla_checks(db)
        # Old notifications are marked read so each persona starts with a meaningful unread set.
        cutoff = utcnow().replace(microsecond=0)
        from datetime import timedelta
        db.execute(update(NotificationEvent).where(NotificationEvent.created_at < cutoff - timedelta(days=3)).values(read_at=cutoff))
        db.commit()
    if not quiet:
        print(f"Seeded: {info['events']} purchasing events, {hist['requests']} MDM requests, forecast run #{run.id} "
              f"(selected {run.selected_model}), opportunities {opp['created']}, SLA {sla}.")


def _seed_opportunity_progress(db, users):
    """A few opportunities already worked, so outcome tracking is visible. Synthetic outcomes."""
    opps = db.query(CommercialOpportunity).order_by(CommercialOpportunity.priority_score.desc()).all()
    xs = [o for o in opps if o.category == "CROSS_SELL" and o.country_code != "SG"][:2]
    ina = [o for o in opps if o.category == "INACTIVITY"][:1]
    for o, outcome, note in zip(xs + ina, ["QUOTE_SENT", "NOT_CLINICALLY_SUITABLE", "CUSTOMER_RETAINED"],
                                ["Quote issued after product discussion (synthetic outcome).", "Lab workflow does not fit this product (synthetic).",
                                 "Customer had switched supplier temporarily; resumed orders (synthetic)."]):
        o.status, o.outcome, o.outcome_note = "COMPLETED", outcome, note
        db.add(SalesFollowup(opportunity_id=o.id, assigned_to_id=o.owner_id or users["marcus"].id, assigned_by_id=users["marcus"].id,
                             note="Synthetic follow-up", status="DONE", outcome=outcome))
    db.flush()


if __name__ == "__main__":
    seed(quiet="--quiet" in sys.argv)
