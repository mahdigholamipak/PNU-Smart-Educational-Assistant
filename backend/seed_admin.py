"""Create an initial admin user and a default demo course.

Usage:
    cd backend
    python seed_admin.py
"""

import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.core.security import hash_password  # noqa: E402
from app.database import SessionLocal, Base, engine  # noqa: E402
from app.models import Course, User  # noqa: E402


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create admin if not exists
        admin_email = input("Admin email [admin@pnu.ac.ir]: ").strip() or "admin@pnu.ac.ir"
        existing = db.query(User).filter(User.email == admin_email).first()
        if existing:
            print(f"Admin already exists with email {admin_email}. Skipping.")
        else:
            full_name = input("Admin full name [مدیر سامانه]: ").strip() or "مدیر سامانه"
            password = getpass.getpass("Admin password (min 8 chars): ")
            if len(password) < 8:
                print("Password too short. Aborting.")
                return

            user = User(
                email=admin_email,
                password_hash=hash_password(password),
                full_name=full_name,
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
            print(f"Admin created: {admin_email}")

        # Create a demo course if no courses exist
        if db.query(Course).count() == 0:
            demo = Course(
                code="DEMO-101",
                title="درس نمونه",
                description="یک درس نمونه برای شروع استفاده از سامانه.",
            )
            db.add(demo)
            db.commit()
            print("Demo course created: DEMO-101")
        else:
            print("Courses already exist. Skipping demo course.")

    except KeyboardInterrupt:
        print("\nAborted.")
    finally:
        db.close()


if __name__ == "__main__":
    main()