from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ingestion import IngestionSourceInfo


@dataclass(frozen=True)
class SourceDefinition:
    source_key: str
    display_name: str
    source_type: str
    base_url: str
    feed_url: str
    feed_kind: str
    document_type: str
    trust_score: float
    requires_api_key: bool = False
    auth_env_var: str | None = None


SOURCE_DEFINITIONS: dict[str, SourceDefinition] = {
    "fed_press": SourceDefinition(
        source_key="fed_press",
        display_name="Federal Reserve Press Releases",
        source_type="official",
        base_url="https://www.federalreserve.gov",
        feed_url="https://www.federalreserve.gov/feeds/press_all.xml",
        feed_kind="rss",
        document_type="press_release",
        trust_score=0.99,
    ),
    "fed_speeches": SourceDefinition(
        source_key="fed_speeches",
        display_name="Federal Reserve Speeches",
        source_type="official",
        base_url="https://www.federalreserve.gov",
        feed_url="https://www.federalreserve.gov/feeds/speeches.xml",
        feed_kind="rss",
        document_type="speech",
        trust_score=0.98,
    ),
    "ecb_press": SourceDefinition(
        source_key="ecb_press",
        display_name="ECB Press Releases",
        source_type="official",
        base_url="https://www.ecb.europa.eu",
        feed_url="https://www.ecb.europa.eu/rss/press.html",
        feed_kind="rss",
        document_type="press_release",
        trust_score=0.98,
    ),
    "bls_calendar": SourceDefinition(
        source_key="bls_calendar",
        display_name="BLS Release Calendar",
        source_type="official",
        base_url="https://www.bls.gov",
        feed_url="https://www.bls.gov/schedule/news_release/bls.ics",
        feed_kind="ics",
        document_type="calendar_event",
        trust_score=0.97,
    ),
}


def get_source_definition(source_key: str) -> SourceDefinition | None:
    return SOURCE_DEFINITIONS.get(source_key)


def list_source_infos() -> list[IngestionSourceInfo]:
    return [
        IngestionSourceInfo(
            sourceKey=definition.source_key,
            displayName=definition.display_name,
            sourceType=definition.source_type,
            baseUrl=definition.base_url,
            feedUrl=definition.feed_url,
            feedKind=definition.feed_kind,
            documentType=definition.document_type,
            requiresApiKey=definition.requires_api_key,
            authEnvVar=definition.auth_env_var,
        )
        for definition in SOURCE_DEFINITIONS.values()
    ]
