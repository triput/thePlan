from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None
    email: str
    display_name: str | None
    is_admin: bool = False
    must_change_password: bool = False


class AuthRegisterBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)


class AuthLoginBody(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class AuthMeUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=12, max_length=128)
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "AuthMeUpdate":
        if self.password is None and self.email is None and self.display_name is None:
            raise ValueError("At least one field is required")
        return self


class AuthUserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str | None
    email: str
    display_name: str | None
    is_admin: bool
    is_disabled: bool
    must_change_password: bool = False


class AuthUserAdminCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)
    is_admin: bool = False


class AuthUserAdminUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    is_disabled: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=128)
    must_change_password: bool | None = None
