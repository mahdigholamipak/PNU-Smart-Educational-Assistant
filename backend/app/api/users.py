from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas.auth import UserResponse
from app.schemas.user import ChangePasswordRequest, UpdateProfileRequest

router = APIRouter(prefix="/users", tags=["Users"])


@router.put("/me", response_model=UserResponse)
def update_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the current user's profile information."""
    if payload.student_id and payload.student_id != current_user.student_id:
        existing = db.query(User).filter(User.student_id == payload.student_id).first()
        if existing:
            raise HTTPException(status_code=400, detail="این شماره دانشجویی قبلاً ثبت شده است")

    current_user.full_name = payload.full_name
    current_user.student_id = payload.student_id
    current_user.phone = payload.phone
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/me/password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change the current user's password."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="رمز عبور فعلی اشتباه است")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "رمز عبور با موفقیت تغییر کرد"}