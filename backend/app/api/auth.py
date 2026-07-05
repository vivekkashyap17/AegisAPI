from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis.asyncio import Redis
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.core.db import get_db
from app.core.redis import get_redis
from app.core.dependencies import get_current_user, oauth2_scheme
from app.models.user import User, UserRole
from app.services.auth import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.services.trust import restore_trust
from app.services.quarantine import release_user
from app.services.policy_rules import get_policy_rules

router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.analyst


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class StepUpRequest(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where(User.username == payload.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role
    )
    db.add(user)
    await db.flush()

    return {
        "message": "User registered successfully",
        "user_id": str(user.id),
        "username": user.username,
        "role": user.role
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    user.last_login = datetime.utcnow()

    token_data = {"sub": user.username, "role": user.role}

    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer"
    }


@router.post("/step-up")
async def step_up(
    payload: StepUpRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    """Re-authentication challenge: a quarantined subject proves identity with
    credentials (not just a bearer token) to lift quarantine and restore trust.

    The traffic subject is the user's own username. On success the quarantine is
    cleared, trust is raised to the `step_up_trust` baseline, and fresh tokens
    are issued.
    """
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account is disabled")

    subject = user.username
    quarantine_cleared = await release_user(redis, subject)
    rules = await get_policy_rules(redis)
    trust_score = await restore_trust(redis, subject, rules["step_up_trust"])

    user.last_login = datetime.utcnow()
    token_data = {"sub": user.username, "role": user.role}

    return {
        "message": "Step-up authentication successful",
        "user_id": subject,
        "quarantine_cleared": quarantine_cleared,
        "trust_score": trust_score,
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer",
    }


@router.get("/me")
async def get_me(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.username == payload.get("sub")))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": str(user.id),
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "last_login": user.last_login.isoformat() if user.last_login else None
    }