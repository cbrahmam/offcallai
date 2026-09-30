# backend/tests/test_incident_collaboration.py
"""
Tests for incident comments, the incident timeline and the organization team
list -- the endpoints the UI depends on for collaborating during an incident.
"""

import uuid
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incident import Incident, IncidentSeverity, IncidentStatus
from app.models.organization import Organization
from app.models.team import Team
from app.models.user import User


@pytest.fixture
async def incident(db_session: AsyncSession, test_organization: Organization, test_user: User) -> Incident:
    """An acknowledged, resolved incident so the timeline has milestones."""
    created = datetime.utcnow() - timedelta(hours=2)
    inc = Incident(
        id=uuid.uuid4(),
        organization_id=test_organization.id,
        title="Checkout latency spike",
        description="p99 above 3s",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.RESOLVED,
        created_by_id=test_user.id,
        acknowledged_by_id=test_user.id,
        resolved_by_id=test_user.id,
        created_at=created,
        acknowledged_at=created + timedelta(minutes=4),
        resolved_at=created + timedelta(minutes=40),
    )
    db_session.add(inc)
    await db_session.commit()
    await db_session.refresh(inc)
    return inc


@pytest.mark.asyncio
class TestIncidentComments:
    async def test_comments_start_empty(self, async_client: AsyncClient, auth_headers, incident):
        resp = await async_client.get(f"/api/v1/incidents/{incident.id}/comments", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {"comments": [], "total": 0}

    async def test_post_then_read_back(self, async_client: AsyncClient, auth_headers, incident):
        resp = await async_client.post(
            f"/api/v1/incidents/{incident.id}/comments",
            headers=auth_headers,
            json={"content": "Scaled the pool back up.", "is_internal": True},
        )
        assert resp.status_code == 201
        created = resp.json()
        assert created["content"] == "Scaled the pool back up."
        assert created["is_internal"] is True
        assert created["user_name"]

        listed = await async_client.get(f"/api/v1/incidents/{incident.id}/comments", headers=auth_headers)
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] == 1
        assert body["comments"][0]["id"] == created["id"]

    async def test_empty_content_rejected(self, async_client: AsyncClient, auth_headers, incident):
        resp = await async_client.post(
            f"/api/v1/incidents/{incident.id}/comments",
            headers=auth_headers,
            json={"content": ""},
        )
        assert resp.status_code == 422

    async def test_unknown_incident_is_404(self, async_client: AsyncClient, auth_headers):
        resp = await async_client.get(f"/api/v1/incidents/{uuid.uuid4()}/comments", headers=auth_headers)
        assert resp.status_code == 404

    async def test_malformed_id_is_400(self, async_client: AsyncClient, auth_headers):
        resp = await async_client.get("/api/v1/incidents/not-a-uuid/comments", headers=auth_headers)
        assert resp.status_code == 400

    async def test_requires_authentication(self, async_client: AsyncClient, incident):
        resp = await async_client.get(f"/api/v1/incidents/{incident.id}/comments")
        assert resp.status_code in (401, 403)

    async def test_author_can_delete(self, async_client: AsyncClient, auth_headers, incident):
        created = await async_client.post(
            f"/api/v1/incidents/{incident.id}/comments",
            headers=auth_headers,
            json={"content": "temporary"},
        )
        comment_id = created.json()["id"]

        deleted = await async_client.delete(
            f"/api/v1/incidents/{incident.id}/comments/{comment_id}", headers=auth_headers
        )
        assert deleted.status_code == 204

        listed = await async_client.get(f"/api/v1/incidents/{incident.id}/comments", headers=auth_headers)
        assert listed.json()["total"] == 0


@pytest.mark.asyncio
class TestIncidentTimeline:
    async def test_lifecycle_milestones_present(self, async_client: AsyncClient, auth_headers, incident):
        resp = await async_client.get(f"/api/v1/incidents/{incident.id}/timeline", headers=auth_headers)
        assert resp.status_code == 200

        events = resp.json()["events"]
        types = [e["type"] for e in events]
        assert "created" in types
        assert "acknowledged" in types
        assert "resolved" in types

    async def test_events_are_chronological(self, async_client: AsyncClient, auth_headers, incident):
        resp = await async_client.get(f"/api/v1/incidents/{incident.id}/timeline", headers=auth_headers)
        timestamps = [e["timestamp"] for e in resp.json()["events"]]
        assert timestamps == sorted(timestamps)

    async def test_comments_appear_in_timeline(self, async_client: AsyncClient, auth_headers, incident):
        await async_client.post(
            f"/api/v1/incidents/{incident.id}/comments",
            headers=auth_headers,
            json={"content": "Mitigated by rollback."},
        )
        resp = await async_client.get(f"/api/v1/incidents/{incident.id}/timeline", headers=auth_headers)

        comments = [e for e in resp.json()["events"] if e["type"] == "comment"]
        assert len(comments) == 1
        assert comments[0]["details"]["comment"] == "Mitigated by rollback."

    async def test_unknown_incident_is_404(self, async_client: AsyncClient, auth_headers):
        resp = await async_client.get(f"/api/v1/incidents/{uuid.uuid4()}/timeline", headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestOrganizationTeams:
    async def test_lists_teams_with_member_counts(
        self, async_client: AsyncClient, auth_headers, db_session: AsyncSession,
        test_organization: Organization, test_user: User
    ):
        team = Team(id=uuid.uuid4(), organization_id=test_organization.id, name="SRE")
        team.members.append(test_user)
        db_session.add(team)
        await db_session.commit()

        resp = await async_client.get("/api/v1/organizations/teams", headers=auth_headers)
        assert resp.status_code == 200

        body = resp.json()
        assert body["total"] == 1
        assert body["teams"][0]["name"] == "SRE"
        assert body["teams"][0]["member_count"] == 1

    async def test_empty_when_no_teams(self, async_client: AsyncClient, auth_headers):
        resp = await async_client.get("/api/v1/organizations/teams", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == {"teams": [], "total": 0}

    async def test_requires_authentication(self, async_client: AsyncClient):
        resp = await async_client.get("/api/v1/organizations/teams")
        assert resp.status_code in (401, 403)
