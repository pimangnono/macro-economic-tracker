from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.schemas.common import BaseAPIModel, MetadataEnvelope, SummaryFrame


class StoryPreview(BaseAPIModel):
    story_id: str = Field(alias="storyId")
    title: str
    story_state: str = Field(alias="storyState")
    hotness_score: float = Field(alias="hotnessScore")
    confidence_score: float = Field(alias="confidenceScore")
    contradiction_score: float = Field(alias="contradictionScore")
    latest_episode_id: str | None = Field(default=None, alias="latestEpisodeId")
    latest_episode_type: str | None = Field(default=None, alias="latestEpisodeType")
    headline: str | None = None
    what_changed: str | None = Field(default=None, alias="whatChanged")
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")
    what_to_watch: str | None = Field(default=None, alias="whatToWatch")
    episode_created_at: datetime | None = Field(default=None, alias="episodeCreatedAt")
    priority_score: float = Field(alias="priorityScore")
    relevance_score: float = Field(alias="relevanceScore")


class LiveBoardTrackItem(BaseAPIModel):
    track_id: str = Field(alias="trackId")
    track_name: str = Field(alias="trackName")
    mode: str
    story_count: int = Field(alias="storyCount")
    top_summary: SummaryFrame | None = Field(default=None, alias="topSummary")
    stories: list[StoryPreview]


class LiveBoardResponse(MetadataEnvelope):
    items: list[LiveBoardTrackItem]


class TrackMetrics(BaseAPIModel):
    story_count: int = Field(alias="storyCount")
    active_story_count: int = Field(alias="activeStoryCount")
    last_activity_at: datetime | None = Field(default=None, alias="lastActivityAt")


class TrackDetail(BaseAPIModel):
    track_id: str = Field(alias="trackId")
    name: str
    slug: str
    description: str | None = None
    mode: str
    state: str
    memory_window_days: int = Field(alias="memoryWindowDays")
    alert_policy: dict = Field(alias="alertPolicy")
    top_summary: SummaryFrame | None = Field(default=None, alias="topSummary")
    metrics: TrackMetrics


class TrackStoriesResponse(MetadataEnvelope):
    track: TrackDetail
    stories: list[StoryPreview]


class BootstrapOption(BaseAPIModel):
    id: str
    label: str
    value: str


class BootstrapResponse(BaseAPIModel):
    workspaces: list[BootstrapOption]
    modes: list[BootstrapOption]
    states: list[BootstrapOption]


class CreateTrackRequest(BaseAPIModel):
    workspace_id: str = Field(alias="workspaceId")
    owner_user_id: str | None = Field(default=None, alias="ownerUserId")
    name: str
    description: str | None = None
    mode: str
    state: str = "active"
    memory_window_days: int = Field(default=30, alias="memoryWindowDays")
    alert_policy: dict[str, Any] = Field(default_factory=dict, alias="alertPolicy")
    evidence_policy: dict[str, Any] = Field(
        default_factory=lambda: {"strict": True}, alias="evidencePolicy"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Track name must be at least 3 characters long")
        return value


class UpdateTrackRequest(BaseAPIModel):
    name: str | None = None
    description: str | None = None
    mode: str | None = None
    state: str | None = None
    memory_window_days: int | None = Field(default=None, alias="memoryWindowDays")


class AlertPolicyRequest(BaseAPIModel):
    alert_policy: dict[str, Any] = Field(alias="alertPolicy")


class CreateNoteRequest(BaseAPIModel):
    author_user_id: str | None = Field(default=None, alias="authorUserId")
    body_md: str = Field(alias="bodyMd")
    pinned: bool = False

    @field_validator("body_md")
    @classmethod
    def validate_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Note body cannot be empty")
        return value


class NoteDetail(BaseAPIModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    track_id: str = Field(alias="trackId")
    body_md: str = Field(alias="bodyMd")
    pinned: bool
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class NoteResponse(BaseAPIModel):
    note: NoteDetail
