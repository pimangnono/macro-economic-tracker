from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes import ingestion as ingestion_routes
from app.api.routes import notifications as notifications_routes
from app.api.routes import tracks as tracks_routes
from app.db.session import get_session
from app.main import app
from app.schemas.dashboard import RecentNotificationItem, SourceHealthItem
from app.schemas.ingestion import IngestionPullResponse
from app.schemas.tracks import BootstrapOption, BootstrapResponse, TrackDetail, TrackMetrics

client = TestClient(app)


async def override_session():
    yield object()


def test_root_exposes_service_metadata() -> None:
    response = client.get("/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Macro Economic Tracker API"
    assert payload["docs"] == "/docs"


def test_live_health_endpoint_is_available() -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "timestamp" in payload


def test_track_bootstrap_endpoint_returns_options(monkeypatch) -> None:
    async def fake_bootstrap(_session):
        return BootstrapResponse(
            workspaces=[BootstrapOption(id="ws-1", label="Macro Desk", value="macro-desk")],
            modes=[BootstrapOption(id="scheduled_release", label="Scheduled Release", value="scheduled_release")],
            states=[BootstrapOption(id="active", label="Active", value="active")],
        )

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(tracks_routes, "fetch_track_bootstrap", fake_bootstrap)

    response = client.get("/api/v1/tracks/bootstrap")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["workspaces"][0]["label"] == "Macro Desk"
    assert payload["modes"][0]["value"] == "scheduled_release"


def test_create_track_endpoint_returns_created_track(monkeypatch) -> None:
    async def fake_create_track(_session, **_kwargs):
        return TrackDetail(
            trackId="66666666-6666-6666-6666-666666666661",
            name="US Inflation",
            slug="us-inflation",
            description="Track inflation",
            mode="scheduled_release",
            state="active",
            memoryWindowDays=30,
            alertPolicy={"delivery": "in_app"},
            topSummary=None,
            metrics=TrackMetrics(
                storyCount=0,
                activeStoryCount=0,
                lastActivityAt=None,
            ),
        )

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(tracks_routes, "create_track", fake_create_track)

    response = client.post(
        "/api/v1/tracks",
        json={
            "workspaceId": "11111111-1111-1111-1111-111111111111",
            "name": "US Inflation",
            "mode": "scheduled_release",
            "state": "active",
            "memoryWindowDays": 30,
            "alertPolicy": {"delivery": "in_app"},
            "evidencePolicy": {"strict": True},
        },
    )

    app.dependency_overrides.clear()
    assert response.status_code == 201
    payload = response.json()
    assert payload["track"]["name"] == "US Inflation"
    assert payload["stories"] == []


def test_ingestion_sources_endpoint_returns_public_feeds() -> None:
    response = client.get("/api/v1/ingestion/sources")

    assert response.status_code == 200
    payload = response.json()
    assert any(item["sourceKey"] == "fed_press" for item in payload["items"])
    assert any(item["sourceKey"] == "bls_calendar" for item in payload["items"])


def test_ingestion_status_endpoint_returns_health_items(monkeypatch) -> None:
    async def fake_build_source_health_items(_session):
        return [
            SourceHealthItem(
                sourceKey="fed_press",
                displayName="Federal Reserve Press Releases",
                sourceType="official",
                documentType="press_release",
                feedKind="rss",
                feedUrl="https://www.federalreserve.gov/feeds/press_all.xml",
                status="healthy",
                isActive=True,
                lastRunStatus="completed",
                lastRunStartedAt=datetime(2026, 3, 8, tzinfo=timezone.utc),
                lastRunFinishedAt=datetime(2026, 3, 8, tzinfo=timezone.utc),
                lastSuccessAt=datetime(2026, 3, 8, tzinfo=timezone.utc),
                lastPublishedAt=datetime(2026, 3, 8, tzinfo=timezone.utc),
                discoveredCount=4,
                insertedCount=2,
                updatedCount=2,
                failedCount=0,
                errorText=None,
            )
        ]

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(ingestion_routes, "build_source_health_items", fake_build_source_health_items)

    response = client.get("/api/v1/ingestion/status")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["status"] == "healthy"
    assert payload["items"][0]["sourceKey"] == "fed_press"


def test_ingestion_pull_endpoint_returns_run_summary(monkeypatch) -> None:
    async def fake_pull_source(_session, *, source_key: str, limit: int):
        assert source_key == "fed_press"
        assert limit == 5
        return IngestionPullResponse(
            generatedAt=datetime(2026, 3, 8, tzinfo=timezone.utc),
            sourceKey="fed_press",
            runId="99999999-9999-9999-9999-999999999999",
            discoveredCount=3,
            insertedCount=2,
            updatedCount=1,
            failedCount=0,
            matchedTrackCount=2,
            storyCount=2,
            episodeCount=2,
            latestPublishedAt=datetime(2026, 3, 8, tzinfo=timezone.utc),
        )

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(ingestion_routes, "pull_source", fake_pull_source)

    response = client.post("/api/v1/ingestion/pull/fed_press?limit=5")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["sourceKey"] == "fed_press"
    assert payload["insertedCount"] == 2


def test_recent_notifications_endpoint_returns_items(monkeypatch) -> None:
    async def fake_fetch_recent_notifications(_session, workspace_id: str | None, limit: int):
        assert workspace_id is None
        assert limit == 4
        return [
            RecentNotificationItem(
                id="cccccccc-cccc-cccc-cccc-ccccccccccc1",
                title="US Inflation: CPI release confirms prior upside inflation concerns",
                bodyText="An official CPI release matched the track.",
                reason="official_confirmation_added",
                channel="in_app",
                createdAt=datetime(2026, 3, 8, tzinfo=timezone.utc),
                scheduledFor=datetime(2026, 3, 8, tzinfo=timezone.utc),
                sentAt=None,
                readAt=None,
                trackId="66666666-6666-6666-6666-666666666661",
                trackName="US Inflation",
                storyId="77777777-7777-7777-7777-777777777771",
                storyTitle="US CPI surprise keeps inflation pressure live",
                episodeId="88888888-8888-8888-8888-888888888881",
                episodeHeadline="CPI release confirms prior upside inflation concerns",
            )
        ]

    app.dependency_overrides[get_session] = override_session
    monkeypatch.setattr(
        notifications_routes,
        "fetch_recent_notifications",
        fake_fetch_recent_notifications,
    )

    response = client.get("/api/v1/notifications/recent?limit=4")

    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["channel"] == "in_app"
    assert payload["items"][0]["trackName"] == "US Inflation"
