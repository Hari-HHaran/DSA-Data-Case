from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user
from ..models import BusinessEntity, Country, Role, User
from ..schemas import DemoLoginIn, LoginIn
from ..serializers import user_out
from ..services import audit
from ..services.forms import DOMAIN_LABELS
from ..services.security import create_access_token, verify_password
from ..services.state_machine import STATUS_LABELS

router = APIRouter(prefix="/api", tags=["auth"])


def _token_response(db: Session, user: User, how: str):
    audit.record(db, "USER_LOGIN", actor_id=user.id, entity_type="USER", entity_ref=user.username, comment=how)
    db.commit()
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user_out(user)}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == body.username.lower().strip())).scalar_one_or_none()
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return _token_response(db, user, "Password login")


@router.post("/auth/demo-login")
def demo_login(body: DemoLoginIn, db: Session = Depends(get_db)):
    """DEMO MODE ONLY: one-click persona switching. Disabled when LIVES_DEMO_MODE=false.
    Every API call is still authorised server-side against the persona's roles."""
    if not get_settings().demo_mode:
        raise HTTPException(404, "Not found")
    user = db.execute(select(User).where(User.username == body.username, User.is_demo.is_(True))).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Unknown demo persona")
    return _token_response(db, user, "Demo persona switch")


@router.get("/auth/demo-personas")
def demo_personas(db: Session = Depends(get_db)):
    if not get_settings().demo_mode:
        return {"demo_mode": False, "personas": []}
    users = db.execute(select(User).where(User.is_demo.is_(True)).order_by(User.id)).scalars().all()
    return {"demo_mode": True, "personas": [user_out(u) for u in users]}


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.get("/users")
def users(role: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q = select(User).where(User.is_active.is_(True)).order_by(User.full_name)
    if role:
        q = q.join(User.roles).where(Role.code == role)
    return [{"id": u.id, "name": u.full_name, "title": u.title, "roles": u.role_codes, "country_code": u.country_code}
            for u in db.execute(q).scalars().unique()]


@router.get("/roles")
def roles_list(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [{"code": r.code, "name": r.name, "description": r.description, "is_approver": r.is_approver}
            for r in db.execute(select(Role).order_by(Role.id)).scalars()]


@router.get("/reference")
def reference(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return {
        "countries": [{"code": c.code, "name": c.name, "timezone": c.timezone, "illustrative": c.is_illustrative}
                      for c in db.execute(select(Country).order_by(Country.display_order)).scalars()],
        "entities": [{"code": e.code, "name": e.name, "description": e.description} for e in db.execute(select(BusinessEntity)).scalars()],
        "domains": [{"code": k, "label": v} for k, v in DOMAIN_LABELS.items()],
        "statuses": STATUS_LABELS,
    }
