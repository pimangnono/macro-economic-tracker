from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseAPIModel, MetadataEnvelope


class SourceHealthItem(BaseAPIModel):
    source_key: str = Field(alias="sourceKey")
    display_name: str = Field(alias="displayName")
    source_type: str = Field(alias="sourceType")
    document_type: str = Field(alias="documentType")
    feed_kind: str = Field(alias="feedKind")
    feed_url: str = Field(alias="feedUrl")
    status: str
    is_active: bool = Field(alias="isActive")
    last_run_status: str | None = Field(default=None, alias="lastRunStatus")
    last_run_started_at: datetime | None = Field(default=None, alias="lastRunStartedAt")
    last_run_finished_at: datetime | None = Field(default=None, alias="lastRunFinishedAt")
    last_success_at: datetime | None = Field(default=None, alias="lastSuccessAt")
    last_published_at: datetime | None = Field(default=None, alias="lastPublishedAt")
    discovered_count: int = Field(alias="discoveredCount")
    inserted_count: int = Field(alias="insertedCount")
    updated_count: int = Field(alias="updatedCount")
    failed_count: int = Field(alias="failedCount")
    error_text: str | None = Field(default=None, alias="errorText")


class SourceHealthResponse(MetadataEnvelope):
    items: list[SourceHealthItem]


class RecentNotificationItem(BaseAPIModel):
    id: str
    title: str
    body_text: str | None = Field(default=None, alias="bodyText")
    reason: str
    channel: str
    created_at: datetime = Field(alias="createdAt")
    scheduled_for: datetime | None = Field(default=None, alias="scheduledFor")
    sent_at: datetime | None = Field(default=None, alias="sentAt")
    read_at: datetime | None = Field(default=None, alias="readAt")
    track_id: str | None = Field(default=None, alias="trackId")
    track_name: str | None = Field(default=None, alias="trackName")
    story_id: str | None = Field(default=None, alias="storyId")
    story_title: str | None = Field(default=None, alias="storyTitle")
    episode_id: str | None = Field(default=None, alias="episodeId")
    episode_headline: str | None = Field(default=None, alias="episodeHeadline")


class RecentNotificationsResponse(MetadataEnvelope):
    items: list[RecentNotificationItem]
