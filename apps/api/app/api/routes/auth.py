from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import (
    clear_session_user,
    get_admin_user,
    get_current_user,
    set_session_user,
)
from app.api.errors import ApiError
from app.db import get_db
from app.models import User
from app.schemas import (
    AuthLoginBody,
    AuthMeUpdate,
    AuthRegisterBody,
    AuthUserAdminCreate,
    AuthUserAdminOut,
    AuthUserAdminUpdate,
    UserOut,
)
from app.services.auth_users import (
    assert_email_available,
    authenticate_user,
    claim_bootstrap_user,
    create_household_user,
    is_setup_required,
    validate_password,
)
from app.services.passwords import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def auth_register(
    body: AuthRegisterBody,
    request: Request,
    db: Session = Depends(get_db),
) -> UserOut:
    user = claim_bootstrap_user(
        db,
        username=body.username,
        email=str(body.email),
        password=body.password,
        display_name=body.display_name,
    )
    set_session_user(request, user.id)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
def auth_login(
    body: AuthLoginBody,
    request: Request,
    db: Session = Depends(get_db),
) -> UserOut:
    if is_setup_required(db):
        raise ApiError(401, "Initial setup required", "SETUP_REQUIRED")
    user = authenticate_user(db, body.identifier, body.password)
    if user is None:
        raise ApiError(401, "Invalid credentials", "INVALID_CREDENTIALS")
    set_session_user(request, user.id)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def auth_logout(request: Request) -> None:
    clear_session_user(request)


@router.get("/me", response_model=UserOut)
def auth_me(
    request: Request,
    db: Session = Depends(get_db),
) -> UserOut:
    if is_setup_required(db):
        raise ApiError(401, "Initial setup required", "SETUP_REQUIRED")
    from app.api.deps import get_current_user_optional

    user = get_current_user_optional(request, db)
    if user is None:
        raise ApiError(401, "Not authenticated", "UNAUTHENTICATED")
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def auth_me_update(
    body: AuthMeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserOut:
    updates = body.model_dump(exclude_unset=True)

    if "password" in updates:
        validate_password(updates["password"])
        user.password_hash = hash_password(updates["password"])
        user.must_change_password = False

    if "email" in updates:
        user.email = assert_email_available(
            db,
            str(updates["email"]),
            exclude_user_id=user.id,
        )

    if "display_name" in updates:
        user.display_name = updates["display_name"]

    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/users", response_model=list[AuthUserAdminOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[AuthUserAdminOut]:
    users = db.query(User).order_by(User.created_at).all()
    return [AuthUserAdminOut.model_validate(user) for user in users]


@router.post("/users", response_model=AuthUserAdminOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: AuthUserAdminCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> AuthUserAdminOut:
    user = create_household_user(
        db,
        username=body.username,
        email=str(body.email),
        password=body.password,
        display_name=body.display_name,
        is_admin=body.is_admin,
    )
    return AuthUserAdminOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=AuthUserAdminOut)
def update_user(
    user_id: UUID,
    body: AuthUserAdminUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> AuthUserAdminOut:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "User not found", "USER_NOT_FOUND")

    updates = body.model_dump(exclude_unset=True)
    if "is_disabled" in updates and updates["is_disabled"] and user.id == admin.id:
        raise ApiError(403, "Cannot disable your own account", "CANNOT_DISABLE_SELF")

    password_present = "password" in updates
    new_password = updates.pop("password", None)
    if new_password is not None:
        validate_password(new_password)
        user.password_hash = hash_password(new_password)

    if "email" in updates:
        user.email = assert_email_available(
            db,
            str(updates.pop("email")),
            exclude_user_id=user.id,
        )

    explicit_must_change = updates.pop("must_change_password", None)
    for field, value in updates.items():
        setattr(user, field, value)

    if password_present:
        user.must_change_password = True
    elif explicit_must_change is not None:
        user.must_change_password = explicit_must_change

    db.commit()
    db.refresh(user)
    return AuthUserAdminOut.model_validate(user)
