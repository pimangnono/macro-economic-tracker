"""Entity Linker Agent — resolves entity mentions to canonical entities."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.agents.base import BaseAgent
from app.services.llm.client import chat_completion

logger = logging.getLogger(__name__)

# Deterministic alias dictionary for common macro entities
BUILTIN_ALIASES: dict[str, tuple[str, str]] = {
    # alias_lower -> (canonical_name, entity_type)
    "fed": ("Federal Reserve", "organization"),
    "the fed": ("Federal Reserve", "organization"),
    "federal reserve": ("Federal Reserve", "organization"),
    "federal reserve board": ("Federal Reserve", "organization"),
    "fomc": ("Federal Open Market Committee", "policy_body"),
    "federal open market committee": ("Federal Open Market Committee", "policy_body"),
    "ecb": ("European Central Bank", "organization"),
    "european central bank": ("European Central Bank", "organization"),
    "boj": ("Bank of Japan", "organization"),
    "bank of japan": ("Bank of Japan", "organization"),
    "boe": ("Bank of England", "organization"),
    "bank of england": ("Bank of England", "organization"),
    "bls": ("Bureau of Labor Statistics", "organization"),
    "bureau of labor statistics": ("Bureau of Labor Statistics", "organization"),
    "cpi": ("Consumer Price Index", "metric"),
    "consumer price index": ("Consumer Price Index", "metric"),
    "ppi": ("Producer Price Index", "metric"),
    "producer price index": ("Producer Price Index", "metric"),
    "pce": ("Personal Consumption Expenditures", "metric"),
    "personal consumption expenditures": ("Personal Consumption Expenditures", "metric"),
    "gdp": ("Gross Domestic Product", "metric"),
    "gross domestic product": ("Gross Domestic Product", "metric"),
    "nfp": ("Non-Farm Payrolls", "metric"),
    "non-farm payrolls": ("Non-Farm Payrolls", "metric"),
    "us": ("United States", "country"),
    "united states": ("United States", "country"),
    "usa": ("United States", "country"),
    "eurozone": ("Eurozone", "region"),
    "euro area": ("Eurozone", "region"),
    "china": ("China", "country"),
    "japan": ("Japan", "country"),
    "uk": ("United Kingdom", "country"),
    "united kingdom": ("United Kingdom", "country"),
    "jerome powell": ("Jerome Powell", "person"),
    "powell": ("Jerome Powell", "person"),
    "chair powell": ("Jerome Powell", "person"),
    "christine lagarde": ("Christine Lagarde", "person"),
    "lagarde": ("Christine Lagarde", "person"),
    "inflation": ("Inflation", "theme"),
    "interest rates": ("Interest Rates", "theme"),
    "unemployment": ("Unemployment Rate", "metric"),
    "unemployment rate": ("Unemployment Rate", "metric"),
    "treasury": ("US Treasury", "instrument"),
    "treasuries": ("US Treasury", "instrument"),
    "us treasury": ("US Treasury", "instrument"),
    "s&p 500": ("S&P 500", "index"),
    "s&p": ("S&P 500", "index"),
    "tariffs": ("Tariffs", "theme"),
    "recession": ("Recession", "theme"),
    "shelter": ("Shelter Costs", "metric"),
}

SYSTEM_PROMPT = """\
You are an entity extraction system for macro-economic documents.
Given a document title and body, identify the key entities mentioned.

For each entity, output:
- mention: the text as it appears in the document
- canonical_name: the standard/full name
- entity_type: one of (country, region, organization, person, asset, instrument, currency, commodity, index, theme, metric, policy_body, location, facility, sector)
- salience: a float 0.0-1.0 indicating how central this entity is to the document

Return JSON: {"entities": [...]}
Only include entities that are meaningful to the macro-economic context.
Limit to the 10 most salient entities.
"""


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "entity"


class EntityLinkerAgent(BaseAgent[dict[str, Any], dict[str, Any]]):
    @property
    def agent_name(self) -> str:
        return "entity_linker"

    @property
    def model_name(self) -> str:
        return get_settings().openai_default_model

    async def run_impl(
        self,
        session: AsyncSession,
        input_data: dict[str, Any],
        trace_id: str,
    ) -> dict[str, Any]:
        document_id = input_data["document_id"]
        title = input_data.get("title", "")
        body_text = input_data.get("body_text", "")
        actor = input_data.get("actor")
        object_text = input_data.get("object_text")

        # Step 1: Collect mentions from deterministic sources
        mentions: list[dict[str, Any]] = []

        # Check built-in aliases for actor and object_text
        for raw_mention in [actor, object_text]:
            if not raw_mention:
                continue
            resolved = self._resolve_builtin(raw_mention)
            if resolved:
                mentions.append(resolved)

        # Step 2: Also scan title for builtin matches
        title_lower = title.lower()
        for alias, (canonical, etype) in BUILTIN_ALIASES.items():
            if alias in title_lower and not any(
                m["canonical_name"] == canonical for m in mentions
            ):
                mentions.append(
                    {
                        "mention": alias,
                        "canonical_name": canonical,
                        "entity_type": etype,
                        "salience": 0.6,
                    }
                )

        # Step 3: Check DB aliases for anything not yet resolved
        db_resolved = await self._resolve_from_db(session, title_lower)
        for item in db_resolved:
            if not any(m["canonical_name"] == item["canonical_name"] for m in mentions):
                mentions.append(item)

        # Step 4: LLM extraction for comprehensive coverage
        llm_entities = await self._extract_via_llm(title, body_text, trace_id)
        for ent in llm_entities:
            if not any(m["canonical_name"] == ent["canonical_name"] for m in mentions):
                mentions.append(ent)

        # Step 5: Upsert entities and link to document
        entity_ids: list[str] = []
        for mention in mentions[:15]:
            entity_id = await self._upsert_entity(
                session,
                canonical_name=mention["canonical_name"],
                entity_type=mention["entity_type"],
            )
            entity_ids.append(entity_id)

            # Add alias
            await self._upsert_alias(
                session,
                entity_id=entity_id,
                alias=mention.get("mention") or mention["canonical_name"],
            )

            # Link to document
            await self._upsert_document_entity(
                session,
                document_id=document_id,
                entity_id=entity_id,
                salience=mention.get("salience", 0.5),
            )

        return {
            "entities_linked": len(entity_ids),
            "entity_ids": entity_ids,
            "document_id": document_id,
        }

    def _resolve_builtin(self, mention: str) -> dict[str, Any] | None:
        key = mention.strip().lower()
        if key in BUILTIN_ALIASES:
            canonical, etype = BUILTIN_ALIASES[key]
            return {
                "mention": mention,
                "canonical_name": canonical,
                "entity_type": etype,
                "salience": 0.7,
            }
        return None

    async def _resolve_from_db(
        self, session: AsyncSession, text_lower: str
    ) -> list[dict[str, Any]]:
        result = await session.execute(
            text(
                """
                SELECT ea.alias, e.canonical_name, e.entity_type::text
                FROM app.entity_aliases ea
                JOIN app.entities e ON e.id = ea.entity_id
                WHERE LOWER(:text_input) LIKE '%' || LOWER(ea.alias) || '%'
                LIMIT 10
                """
            ),
            {"text_input": text_lower},
        )
        return [
            {
                "mention": row["alias"],
                "canonical_name": row["canonical_name"],
                "entity_type": row["entity_type"],
                "salience": 0.5,
            }
            for row in result.mappings().all()
        ]

    async def _extract_via_llm(
        self, title: str, body_text: str, trace_id: str
    ) -> list[dict[str, Any]]:
        user_content = f"Title: {title}\n\nBody:\n{body_text[:4000]}"
        try:
            raw_response, _ = await chat_completion(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                model=self.model_name,
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(raw_response)
            return parsed.get("entities", [])
        except Exception:
            logger.warning("[%s] LLM entity extraction failed", trace_id, exc_info=True)
            return []

    async def _upsert_entity(
        self, session: AsyncSession, *, canonical_name: str, entity_type: str
    ) -> str:
        slug = _slugify(canonical_name)
        result = await session.execute(
            text(
                """
                INSERT INTO app.entities (entity_type, canonical_name, slug)
                VALUES (CAST(:entity_type AS app.entity_type), :canonical_name, :slug)
                ON CONFLICT (entity_type, canonical_name) DO UPDATE
                SET updated_at = now()
                RETURNING id
                """
            ),
            {"entity_type": entity_type, "canonical_name": canonical_name, "slug": slug},
        )
        return str(result.scalar_one())

    async def _upsert_alias(
        self, session: AsyncSession, *, entity_id: str, alias: str
    ) -> None:
        normalized = alias.strip().lower()
        if not normalized:
            return
        await session.execute(
            text(
                """
                INSERT INTO app.entity_aliases (entity_id, alias, normalized_alias)
                VALUES (CAST(:entity_id AS uuid), :alias, :normalized_alias)
                ON CONFLICT (entity_id, normalized_alias) DO NOTHING
                """
            ),
            {"entity_id": entity_id, "alias": alias.strip(), "normalized_alias": normalized},
        )

    async def _upsert_document_entity(
        self,
        session: AsyncSession,
        *,
        document_id: str,
        entity_id: str,
        salience: float,
    ) -> None:
        await session.execute(
            text(
                """
                INSERT INTO app.document_entities (document_id, entity_id, salience_score, mention_count)
                VALUES (
                    CAST(:document_id AS uuid),
                    CAST(:entity_id AS uuid),
                    :salience,
                    1
                )
                ON CONFLICT (document_id, entity_id) DO UPDATE
                SET salience_score = GREATEST(app.document_entities.salience_score, EXCLUDED.salience_score),
                    mention_count = app.document_entities.mention_count + 1
                """
            ),
            {
                "document_id": document_id,
                "entity_id": entity_id,
                "salience": min(salience, 1.0),
            },
        )
