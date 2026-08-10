from fastapi import Depends
from sqlalchemy.orm import Session

from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import get_db
from app.models import User


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.get(User, BOOTSTRAP_USER_ID)
    if user is None:
        raise RuntimeError("Bootstrap user missing; run migrations and startup bootstrap")
    return user
