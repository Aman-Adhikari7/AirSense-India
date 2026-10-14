from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.security import (
    clear_auth_cookie, create_access_token, get_auth_user, hash_password,
    set_auth_cookie, verify_password,
)
from ..db import get_db
from ..models import User, utcnow
from ..schemas import LoginRequest, SignupRequest, UserResponse

router = APIRouter()


def _issue_session(response: Response, user: User) -> None:
    token = create_access_token({"sub": str(user.id), "email": user.email})
    set_auth_cookie(response, token)


@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(payload: SignupRequest, response: Response, db: Session = Depends(get_db)):
    email = payload.email.lower()
    if db.execute(select(User.id).where(User.email == email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two signups with the same email at once
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    db.refresh(user)

    _issue_session(response, user)
    return UserResponse(id=user.id, email=user.email)


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()
    # verify_password also runs a dummy hash for unknown emails, so timing does not reveal who is registered
    if not verify_password(payload.password, user.password_hash if user else None) or user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.last_login = utcnow()
    db.commit()
    _issue_session(response, user)
    return UserResponse(id=user.id, email=user.email)


@router.post("/logout")
def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def me(request: Request, db: Session = Depends(get_db)):
    data = get_auth_user(request)
    if not data:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = db.get(User, int(data["id"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return UserResponse(id=user.id, email=user.email)
