"""Профілі користувачів за ідентифікатором.

Маршрут існує саме для перевірки горизонтального розмежування прав: пасажир
не має змінювати чужий профіль, навіть знаючи його ідентифікатор (IDOR).
"""

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models.user import User
from app.schemas.auth import ProfileUpdateRequest, UserRead
from app.services import users as users_service

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/{user_id}", response_model=UserRead, summary="Змінити профіль користувача")
def update_user_profile(
    user_id: int,
    payload: ProfileUpdateRequest,
    actor: CurrentUser,
    session: SessionDep,
) -> User:
    return users_service.update_profile(
        session,
        actor=actor,
        user_id=user_id,
        full_name=payload.full_name,
    )
