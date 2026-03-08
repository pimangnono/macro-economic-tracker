from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIStatus(BaseModel):
    status: str
    timestamp: datetime
    services: dict[str, str] | None = None


class SummaryFrame(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    what_changed: str | None = Field(default=None, alias="whatChanged")
    why_it_matters: str | None = Field(default=None, alias="whyItMatters")
    what_to_watch: str | None = Field(default=None, alias="whatToWatch")


class SourceSnippet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    source_name: str | None = Field(default=None, alias="sourceName")
    source_type: str | None = Field(default=None, alias="sourceType")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    document_type: str | None = Field(default=None, alias="documentType")


class EvidenceSnippet(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    quote_text: str = Field(alias="quoteText")
    source_name: str | None = Field(default=None, alias="sourceName")
    source_type: str | None = Field(default=None, alias="sourceType")
    support_status: str | None = Field(default=None, alias="supportStatus")


class BaseAPIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class MetadataEnvelope(BaseAPIModel):
    generated_at: datetime = Field(alias="generatedAt")
    meta: dict[str, Any] = Field(default_factory=dict)
