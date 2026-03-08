from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseAPIModel, MetadataEnvelope


class IngestionSourceInfo(BaseAPIModel):
    source_key: str = Field(alias="sourceKey")
    display_name: str = Field(alias="displayName")
    source_type: str = Field(alias="sourceType")
    base_url: str | None = Field(default=None, alias="baseUrl")
    feed_url: str = Field(alias="feedUrl")
    feed_kind: str = Field(alias="feedKind")
    document_type: str = Field(alias="documentType")
    requires_api_key: bool = Field(alias="requiresApiKey")
    auth_env_var: str | None = Field(default=None, alias="authEnvVar")


class IngestionSourcesResponse(MetadataEnvelope):
    items: list[IngestionSourceInfo]


class IngestionPullResponse(MetadataEnvelope):
    source_key: str = Field(alias="sourceKey")
    run_id: str = Field(alias="runId")
    discovered_count: int = Field(alias="discoveredCount")
    inserted_count: int = Field(alias="insertedCount")
    updated_count: int = Field(alias="updatedCount")
    failed_count: int = Field(alias="failedCount")
    matched_track_count: int = Field(alias="matchedTrackCount")
    story_count: int = Field(alias="storyCount")
    episode_count: int = Field(alias="episodeCount")
    latest_published_at: datetime | None = Field(default=None, alias="latestPublishedAt")
