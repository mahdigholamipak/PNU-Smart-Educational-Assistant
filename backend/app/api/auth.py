from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new student account and return an access token."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است")

    if payload.student_id:
        existing_student = db.query(User).filter(User.student_id == payload.student_id).first()
        if existing_student:
            raise HTTPException(status_code=400, detail="این شماره دانشجویی قبلاً ثبت شده است")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        student_id=payload.student_id,
        phone=payload.phone,
        role="student",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate a user and return an access token."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="ایمیل یا رمز عبور اشتباه است")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="حساب کاربری شما غیرفعال شده است")

    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user