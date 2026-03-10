from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import BaseAPIModel, MetadataEnvelope
from app.schemas.notes import NoteDetail
from app.schemas.snapshots import SnapshotDetail
from app.schemas.tracks import StoryPreview, TrackDetail


class InboxItem(BaseAPIModel):
    id: str
    workspace_id: str = Field(alias="workspaceId")
    track_id: str | None = Field(default=None, alias="trackId")
    track_name: str | None = Field(default=None, alias="trackName")
    story_id: str | None = Field(default=None, alias="storyId")
    story_title: str | None = Field(default=None, alias="storyTitle")
    episode_id: str | None = Field(default=None, alias="episodeId")
    episode_headline: str | None = Field(default=None, alias="episodeHeadline")
    mode: str | None = None
    state: str | None = None
    reason: str
    priority_score: float = Field(alias="priorityScore")
    confidence_score: float = Field(alias="confidenceScore")
    contradiction_score: float = Field(alias="contradictionScore")
    created_at: datetime = Field(alias="createdAt")
    what_changed: str | None = Field(default=None, alias="whatChanged")
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")
    what_to_watch: str | None = Field(default=None, alias="whatToWatch")
    source_name: str | None = Field(default=None, alias="sourceName")
    is_read: bool = Field(alias="isRead")


class InboxResponse(MetadataEnvelope):
    items: list[InboxItem]


class TrackListItem(BaseAPIModel):
    track_id: str = Field(alias="trackId")
    workspace_id: str = Field(alias="workspaceId")
    name: str
    slug: str
    mode: str
    state: str
    owner_name: str | None = Field(default=None, alias="ownerName")
    story_count: int = Field(alias="storyCount")
    active_story_count: int = Field(alias="activeStoryCount")
    unread_count: int = Field(alias="unreadCount")
    last_activity_at: datetime | None = Field(default=None, alias="lastActivityAt")


class TrackListResponse(MetadataEnvelope):
    items: list[TrackListItem]


class UpcomingEventItem(BaseAPIModel):
    id: str
    title: str
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    document_type: str | None = Field(default=None, alias="documentType")
    source_name: str | None = Field(default=None, alias="sourceName")
    canonical_url: str | None = Field(default=None, alias="canonicalUrl")


class UpcomingEventsResponse(MetadataEnvelope):
    items: list[UpcomingEventItem]


class ModeQuote(BaseAPIModel):
    id: str
    quote_text: str = Field(alias="quoteText")
    source_name: str | None = Field(default=None, alias="sourceName")
    support_status: str | None = Field(default=None, alias="supportStatus")


class ModeData(BaseAPIModel):
    kind: str
    blocks: dict[str, Any] = Field(default_factory=dict)


class TrackCanvasResponse(MetadataEnvelope):
    track: TrackDetail
    stories: list[StoryPreview]
    notes: list[NoteDetail]
    snapshots: list[SnapshotDetail]
    upcoming_events: list[UpcomingEventItem] = Field(alias="upcomingEvents")
    mode_data: ModeData = Field(alias="modeData")
