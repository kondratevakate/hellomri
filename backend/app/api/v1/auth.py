"""Authentication and authorization endpoints for the API."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.models.session.models import Session
from app.models.user.models import User
from app.schemas.auth import SessionResponse, TokenResponse, UserCreate, UserResponse
from app.services.database import async_session_maker
from app.utils.auth import create_access_token, verify_token
from app.utils.sanitization import sanitize_email, sanitize_string, validate_password_strength

router = APIRouter()
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    token = sanitize_string(credentials.credentials)
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    async with async_session_maker() as session:
        user = await session.get(User, int(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Session:
    token = sanitize_string(credentials.credentials)
    session_id = verify_token(token)
    if not session_id:
        raise HTTPException(status_code=401, detail="Invalid session token")

    async with async_session_maker() as session:
        db_session = await session.get(Session, session_id)
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")
        return db_session


@router.post("/register", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["register"][0])
async def register_user(request: Request, user_data: UserCreate):
    sanitized_email = sanitize_email(user_data.email)
    password = user_data.password.get_secret_value()
    validate_password_strength(password)

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == sanitized_email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(email=sanitized_email, hashed_password=User.hash_password(password))
        session.add(user)
        await session.commit()
        await session.refresh(user)

    token = create_access_token(str(user.id))
    return UserResponse(id=user.id, email=user.email, token=token)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["login"][0])
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    grant_type: str = Form(default="password"),
):
    username = sanitize_string(username)
    password = sanitize_string(password)

    if grant_type != "password":
        raise HTTPException(status_code=400, detail="Unsupported grant type. Must be 'password'")

    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == username))
        user = result.scalar_one_or_none()

    if not user or not user.verify_password(password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token.access_token,
        token_type="bearer",
        expires_at=token.expires_at,
    )


@router.post("/session", response_model=SessionResponse)
async def create_session(user: User = Depends(get_current_user)):
    session_id = str(uuid.uuid4())
    async with async_session_maker() as session:
        db_session = Session(id=session_id, user_id=user.id)
        session.add(db_session)
        await session.commit()
        await session.refresh(db_session)

    token = create_access_token(session_id)
    return SessionResponse(
        session_id=session_id,
        name=db_session.name,
        token=token,
    )


@router.patch("/session/{session_id}/name", response_model=SessionResponse)
async def update_session_name(
    session_id: str,
    name: str = Form(...),
    current_session: Session = Depends(get_current_session),
):
    session_id = sanitize_string(session_id)
    name = sanitize_string(name)

    if session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Cannot modify other sessions")

    async with async_session_maker() as session:
        db_session = await session.get(Session, session_id)
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        db_session.name = name
        await session.commit()
        await session.refresh(db_session)

    token = create_access_token(session_id)
    return SessionResponse(
        session_id=session_id,
        name=db_session.name,
        token=token,
    )


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_session: Session = Depends(get_current_session),
):
    session_id = sanitize_string(session_id)
    if session_id != current_session.id:
        raise HTTPException(status_code=403, detail="Cannot delete other sessions")

    async with async_session_maker() as session:
        db_session = await session.get(Session, session_id)
        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")
        await session.delete(db_session)
        await session.commit()

    logger.info("session_deleted", session_id=session_id, user_id=current_session.user_id)
    return {"detail": "Session deleted"}


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(user: User = Depends(get_current_user)):
    async with async_session_maker() as session:
        result = await session.execute(select(Session).where(Session.user_id == user.id))
        sessions = result.scalars().all()

    return [
        SessionResponse(
            session_id=session.id,
            name=session.name,
            token=create_access_token(session.id),
        )
        for session in sessions
    ]
