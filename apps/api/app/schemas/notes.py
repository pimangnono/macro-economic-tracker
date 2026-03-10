from datetime import datetime
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.schemas.common import BaseAPIModel, MetadataEnvelope


class NoteDetail(BaseAPIModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    author_user_id: str | None = Field(default=None, alias="authorUserId")
    author_name: str | None = Field(default=None, alias="authorName")
    scope: str
    track_id: str | None = Field(default=None, alias="trackId")
    story_id: str | None = Field(default=None, alias="storyId")
    episode_id: str | None = Field(default=None, alias="episodeId")
    evidence_span_id: str | None = Field(default=None, alias="evidenceSpanId")
    body_md: str = Field(alias="bodyMd")
    pinned: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class NoteResponse(BaseAPIModel):
    note: NoteDetail


class NotesResponse(MetadataEnvelope):
    items: list[NoteDetail]


class CreateNoteRequest(BaseAPIModel):
    scope: str
    track_id: str | None = Field(default=None, alias="trackId")
    story_id: str | None = Field(default=None, alias="storyId")
    episode_id: str | None = Field(default=None, alias="episodeId")
    evidence_span_id: str | None = Field(default=None, alias="evidenceSpanId")
    body_md: str = Field(alias="bodyMd")
    pinned: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("body_md", "scope")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be empty")
        return value

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        allowed = {"track", "story", "episode", "evidence"}
        if value not in allowed:
            raise ValueError(f"Scope must be one of {sorted(allowed)}")
        return value

    @model_validator(mode="after")
    def validate_scope_target(self) -> "CreateNoteRequest":
        targets = {
            "track": self.track_id,
            "story": self.story_id,
            "episode": self.episode_id,
            "evidence": self.evidence_span_id,
        }
        provided = [scope for scope, value in targets.items() if value]
        if len(provided) != 1:
            raise ValueError("Exactly one note target must be provided")
        if provided[0] != self.scope:
            raise ValueError(f"Scope '{self.scope}' must match the provided target '{provided[0]}'")
        return self


class UpdateNoteRequest(BaseAPIModel):
    body_md: str | None = Field(default=None, alias="bodyMd")
    pinned: bool | None = None
    metadata: dict[str, Any] | None = None
