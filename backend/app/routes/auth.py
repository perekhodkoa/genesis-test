from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_pg_session
from app.dependencies import get_current_user_id
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_pg_session)):
    return await auth_service.register(session, body.username, body.password)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_pg_session)):
    return await auth_service.login(session, body.username, body.password)


@router.get("/me", response_model=UserResponse)
async def me(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_pg_session),
):
    return await auth_service.get_current_user(session, user_id)
