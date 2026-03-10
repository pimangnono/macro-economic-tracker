from datetime import datetime

from pydantic import Field

from app.schemas.common import (
    BaseAPIModel,
    EvidenceSnippet,
    MetadataEnvelope,
    SourceSnippet,
    SummaryFrame,
)


class EpisodeDetail(BaseAPIModel):
    episode_id: str = Field(alias="episodeId")
    episode_type: str = Field(alias="episodeType")
    headline: str
    state_from: str | None = Field(default=None, alias="stateFrom")
    state_to: str | None = Field(default=None, alias="stateTo")
    summary: SummaryFrame
    significance_score: float = Field(alias="significanceScore")
    confidence_score: float = Field(alias="confidenceScore")
    contradiction_score: float = Field(alias="contradictionScore")
    created_at: datetime = Field(alias="createdAt")


class StoryDetail(BaseAPIModel):
    story_id: str = Field(alias="storyId")
    title: str
    state: str
    dominant_mode: str = Field(alias="dominantMode")
    scores: dict[str, float]
    summary: SummaryFrame
    latest_episode: EpisodeDetail | None = Field(default=None, alias="latestEpisode")
    episodes: list[EpisodeDetail]
    sources: list[SourceSnippet]
    evidence: list[EvidenceSnippet]


class StoryDetailResponse(MetadataEnvelope):
    story: StoryDetail


class ContradictionItem(BaseAPIModel):
    sentence_id: str = Field(alias="sentenceId")
    sentence_text: str = Field(alias="sentenceText")
    verdict: str
    evidence_span_id: str = Field(alias="evidenceSpanId")
    quote_text: str = Field(alias="quoteText")
    source_name: str | None = Field(default=None, alias="sourceName")
    support_status: str = Field(alias="supportStatus")


class StoryContradictionsResponse(MetadataEnvelope):
    items: list[ContradictionItem]
