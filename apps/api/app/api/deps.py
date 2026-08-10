from fastapi import Depends
from sqlalchemy.orm import Session, joinedload

from app.bootstrap import BOOTSTRAP_USER_ID
from app.db import get_db
from app.models import User


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = (
        db.query(User)
        .options(joinedload(User.settings))
        .filter(User.id == BOOTSTRAP_USER_ID)
        .one_or_none()
    )
    if user is None:
        raise RuntimeError("Bootstrap user missing; run migrations and startup bootstrap")
    return user
