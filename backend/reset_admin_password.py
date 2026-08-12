"""Reset the admin user's password to a known value.

Usage:
    cd backend
    python reset_admin_password.py admin@pnu.ac.ir NewPassword123
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal, Base, engine  # noqa: E402
from app.models import User  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python reset_admin_password.py <email> <new_password>")
        sys.exit(1)

    email = sys.argv[1].strip()
    new_password = sys.argv[2]

    if len(new_password) < 8:
        print("Password must be at least 8 characters.")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"User with email '{email}' not found.")
            sys.exit(1)

        user.password_hash = hash_password(new_password)
        db.commit()
        print(f"Password reset successfully for {email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()