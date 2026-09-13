"""Збірка маршрутів версії v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import fleet, schedule

api_router = APIRouter()
api_router.include_router(fleet.router)
api_router.include_router(schedule.router)
