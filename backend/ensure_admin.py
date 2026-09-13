"""Non-interactive, idempotent super-admin bootstrap for containerised deploys.

Runs on every container start (before uvicorn) and guarantees that a "super
admin" account exists with the ``admin`` role.

Configuration (environment variables):
    ADMIN_EMAIL          Email of the admin account   (default: admin@pnu.ac.ir)
    ADMIN_NAME           Display name                 (default: مدیر سامانه)
    ADMIN_PASSWORD       Login password (min 8 chars) (default: _FALLBACK_PASSWORD)

Behaviour:
    * Creates the user with role=admin and is_active=True if it does not exist.
    * If a user already owns ADMIN_EMAIL (e.g. a student who self-registered),
      that user is promoted to role=admin, activated, and its password is reset
      to ADMIN_PASSWORD so login is deterministic across ephemeral instances.

Exit code is always 0: this script never blocks container startup.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.core.security import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import User  # noqa: E402

# Hard fallback; the real secret normally comes from the ADMIN_PASSWORD env var.
_FALLBACK_PASSWORD = os.environ.get("ADMIN_FALLBACK_PASSWORD", "PnuAdmin-ChangeMe!9")


def _ensure_admin() -> None:
    email = (os.environ.get("ADMIN_EMAIL") or "admin@pnu.ac.ir").strip()
    full_name = os.environ.get("ADMIN_NAME") or "مدیر سامانه"
    password = os.environ.get("ADMIN_PASSWORD") or _FALLBACK_PASSWORD
    print(f"[ensure_admin] ensuring admin for {email}", flush=True)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(password),
                    full_name=full_name,
                    role="admin",
                    is_active=True,
                )
            )
            db.commit()
            print("[ensure_admin] created admin account", flush=True)
        else:
            user.role = "admin"
            user.is_active = True
            user.password_hash = hash_password(password)
            if not user.full_name:
                user.full_name = full_name
            db.commit()
            print("[ensure_admin] promoted existing user to admin and reset password", flush=True)
    except Exception as exc:  # pragma: no cover - never crash container boot
        print(f"[ensure_admin] ERROR: {exc!r}", flush=True)
    finally:
        db.close()


def main() -> None:
    try:
        _ensure_admin()
    except Exception as exc:  # pragma: no cover - never crash container boot
        print(f"[ensure_admin] FATAL: {exc!r}", flush=True)


if __name__ == "__main__":
    main()