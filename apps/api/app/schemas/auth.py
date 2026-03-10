from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import BaseAPIModel


class WorkspaceMembership(BaseAPIModel):
    id: str
    name: str
    slug: str
    role: str


class CurrentUser(BaseAPIModel):
    id: str
    email: str
    display_name: str = Field(alias="displayName")
    timezone: str
    is_active: bool = Field(alias="isActive")
    default_workspace_id: str | None = Field(default=None, alias="defaultWorkspaceId")
    workspaces: list[WorkspaceMembership]


class LoginRequest(BaseAPIModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Invalid email address")
        return value


class LoginResponse(BaseAPIModel):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    expires_at: datetime = Field(alias="expiresAt")
    user: CurrentUser


class LogoutResponse(BaseAPIModel):
    status: str = "ok"


class InviteAcceptanceRequest(BaseAPIModel):
    invite_token: str = Field(alias="inviteToken")
    display_name: str = Field(alias="displayName")
    password: str

    @field_validator("display_name", "password")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value
