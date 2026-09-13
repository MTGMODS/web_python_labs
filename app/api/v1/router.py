"""Збірка маршрутів версії v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, fleet, schedule, tickets, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(fleet.router)
api_router.include_router(schedule.router)
api_router.include_router(tickets.router)
api_router.include_router(admin.router)
