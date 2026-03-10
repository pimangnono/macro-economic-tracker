from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import BaseAPIModel


class WorkspaceMember(BaseAPIModel):
    user_id: str = Field(alias="userId")
    email: str
    display_name: str = Field(alias="displayName")
    role: str
    joined_at: datetime = Field(alias="joinedAt")
    last_login_at: datetime | None = Field(default=None, alias="lastLoginAt")


class WorkspaceMembersResponse(BaseAPIModel):
    items: list[WorkspaceMember]


class WorkspaceInviteRequest(BaseAPIModel):
    email: str
    role: str = "viewer"

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value:
            raise ValueError("Invalid email address")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        allowed = {"owner", "editor", "viewer"}
        if value not in allowed:
            raise ValueError(f"Role must be one of {sorted(allowed)}")
        return value


class WorkspaceInviteDetail(BaseAPIModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    email: str
    role: str
    invite_token: str = Field(alias="inviteToken")
    expires_at: datetime = Field(alias="expiresAt")


class WorkspaceInviteResponse(BaseAPIModel):
    invite: WorkspaceInviteDetail


class WorkspaceMemberUpdateRequest(BaseAPIModel):
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        allowed = {"owner", "editor", "viewer"}
        if value not in allowed:
            raise ValueError(f"Role must be one of {sorted(allowed)}")
        return value
