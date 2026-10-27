"""LIVES ONE API entrypoint."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .database import SessionLocal
from .routers import admin, auth, dashboard, flow, growth, mdm, sap
from .services import workflow
from .services.errors import DomainError

log = logging.getLogger("lives_one")
settings = get_settings()


async def _sla_loop():
    """Deterministic SLA reminder/escalation sweep every 5 minutes (idempotent per task)."""
    while True:
        try:
            with SessionLocal() as db:
                workflow.run_sla_checks(db)
                db.commit()
        except Exception:  # pragma: no cover - background resilience
            log.exception("SLA sweep failed")
        await asyncio.sleep(settings.sla_sweep_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_sla_loop()) if settings.sla_sweep_seconds > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="LIVES ONE API", version="1.0.0", lifespan=lifespan,
              description="Smart MDM · Flow Engine · Growth Intelligence. Prototype — synthetic data and mock integrations are labelled.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(DomainError)
async def domain_error(_: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "detail": exc.message, **exc.detail})


@app.exception_handler(PermissionError)
async def permission_error(_: Request, exc: PermissionError):
    return JSONResponse(status_code=403, content={"error": "forbidden", "detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def request_validation(_: Request, exc: RequestValidationError):
    problems = [f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"error": "invalid_request", "detail": "Invalid request.", "problems": problems})


for r in (auth.router, mdm.router, flow.router, sap.router, growth.router, admin.router, dashboard.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "demo_mode": settings.demo_mode, "sap_adapter": settings.sap_adapter,
            "notification_adapter": settings.notification_adapter}
