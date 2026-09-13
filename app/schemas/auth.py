"""Схеми реєстрації, входу та профілю."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.security import PASSWORD_MAX_BYTES
from app.models.user import UserRole


class RegisterRequest(BaseModel):
    """Реєстрація пасажира.

    Роль у запиті свідомо відсутня: інакше будь-хто міг би створити собі
    адміністратора. Адміністратори створюються лише скриптом scripts/create_admin.py.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=PASSWORD_MAX_BYTES)
    full_name: str = Field(min_length=2, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_BYTES)


class ProfileUpdateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
