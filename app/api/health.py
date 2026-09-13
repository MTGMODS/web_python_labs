"""Службові перевірки стану.

Розділення на liveness і readiness зроблено наперед: у наступних роботах саме ці
маршрути опитуватиме балансувальник, щоб не надсилати трафік на екземпляр,
який втратив зв'язок з базою.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep
from app.core.config import settings

router = APIRouter(tags=["service"])


@router.get("/health", summary="Liveness: процес живий")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name}


@router.get("/health/db", summary="Readiness: база відповідає")
def health_db(session: SessionDep) -> dict[str, str]:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="База даних недоступна",
        ) from exc
    return {"status": "ok", "database": "reachable"}
