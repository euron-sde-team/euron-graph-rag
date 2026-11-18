"""Who may do what: roles, API keys, project isolation, sign-in and the activity trail."""

from __future__ import annotations

import httpx
import pytest

from tests.integration.conftest import Graph
from tests.integration.support import (
    PASSWORD,
    Account,
    add_member,
    bearer,
    get_json,
    import_texts,
    settle,
    signup,
)

pytestmark = pytest.mark.integration


async def test_roles_gate_every_write(client: httpx.AsyncClient, graph: Graph) -> None:
    viewer = await signup(client, "Viewer Person")
    editor = await signup(client, "Editor Person")
    await add_member(client, graph.owner, graph.project, viewer, "viewer")
    await add_member(client, graph.owner, graph.project, editor, "editor")

    # A viewer reads and asks, and changes nothing.
    assert (await client.get(f"{graph.base}/overview", headers=viewer.headers)).status_code == 200
    ask = await client.post(
        f"{graph.base}/query",
        json={"question": "Who founded Helios Robotics?", "mode": "local"},
        headers=viewer.headers,
    )
    assert ask.status_code == 200
    page = await get_json(client, viewer, f"{graph.base}/graph/entities", q="Helios", limit=1)
    entity_id = page["items"][0]["id"]
    for method, path, body in (
        (
            "POST",
            f"{graph.base}/documents/import",
            {"items": [{"type": "text", "title": "t", "text": "x y z"}]},
        ),
        ("PATCH", f"{graph.base}/graph/entities/{entity_id}", {"name": "Renamed"}),
        ("DELETE", f"{graph.base}/graph/entities/{entity_id}", None),
        ("POST", f"{graph.base}/builds", None),
        ("POST", f"{graph.base}/api-keys", {"name": "k", "role": "viewer"}),
    ):
        response = await client.request(method, path, json=body, headers=viewer.headers)
        assert response.status_code == 403, (method, path, response.text)

    # An editor builds the graph but does not administer the project.
    assert (await client.post(f"{graph.base}/builds", headers=editor.headers)).status_code == 202
    await settle(client)
    members = await client.get(f"{graph.base}/members", headers=editor.headers)
    assert members.status_code == 200
    forbidden = await client.patch(graph.base, json={"name": "Mine"}, headers=editor.headers)
    assert forbidden.status_code == 403


async def test_projects_are_invisible_to_outsiders(client: httpx.AsyncClient, graph: Graph) -> None:
    outsider = await signup(client, "Outsider")
    for path in (
        graph.base,
        f"{graph.base}/graph/entities",
        f"{graph.base}/communities",
        f"{graph.base}/overview",
        f"{graph.base}/documents",
    ):
        assert (await client.get(path, headers=outsider.headers)).status_code == 404, path
    listing = await get_json(client, outsider, "/api/v1/projects")
    assert graph.project not in {p["slug"] for p in listing}
    other = await get_json(client, graph.owner, "/api/v1/projects")
    entity = (await get_json(client, graph.owner, f"{graph.base}/graph/entities", limit=1))[
        "items"
    ][0]
    cross = await client.get(
        f"/api/v1/projects/{outsider.project}/graph/entities/{entity['id']}",
        headers=outsider.headers,
    )
    assert cross.status_code == 404, "an id from another project resolves to nothing"
    assert other


async def test_api_keys_carry_a_role_and_are_bound_to_one_project(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    created = await client.post(
        f"{graph.base}/api-keys", json={"name": "ci", "role": "viewer"}, headers=graph.owner.headers
    )
    assert created.status_code == 201
    key = created.json()["key"]
    assert key.startswith("grk_")
    asked = await client.post(
        f"{graph.base}/query",
        json={"question": "Who founded Helios Robotics?", "mode": "local"},
        headers=bearer(key),
    )
    assert asked.status_code == 200
    write = await client.post(f"{graph.base}/builds", headers=bearer(key))
    assert write.status_code == 403
    stranger = await signup(client, "Other Project Owner")
    elsewhere = await client.get(
        f"/api/v1/projects/{stranger.project}/overview", headers=bearer(key)
    )
    assert elsewhere.status_code == 404
    key_id = created.json()["id"]
    assert (
        await client.delete(f"{graph.base}/api-keys/{key_id}", headers=graph.owner.headers)
    ).status_code == 204
    revoked = await client.get(f"{graph.base}/overview", headers=bearer(key))
    assert revoked.status_code == 401


async def test_an_editor_key_can_ingest(client: httpx.AsyncClient) -> None:
    owner = await signup(client, "Key Owner")
    base = f"/api/v1/projects/{owner.project}"
    created = await client.post(
        f"{base}/api-keys", json={"name": "ingest", "role": "editor"}, headers=owner.headers
    )
    key = created.json()["key"]
    response = await client.post(
        f"{base}/documents/import",
        json={
            "items": [
                {
                    "type": "text",
                    "title": "Via key",
                    "text": "Orion Labs partnered with Nova Systems.",
                }
            ]
        },
        headers=bearer(key),
    )
    assert response.status_code == 201
    await settle(client)


async def test_members_roles_and_the_last_owner_rule(client: httpx.AsyncClient) -> None:
    owner = await signup(client, "Owner")
    guest = await signup(client, "Guest")
    base = f"/api/v1/projects/{owner.project}"
    await add_member(client, owner, owner.project, guest, "viewer")
    promoted = await client.patch(
        f"{base}/members/{guest.user_id}", json={"role": "owner"}, headers=owner.headers
    )
    assert promoted.status_code == 200
    demoted = await client.patch(
        f"{base}/members/{owner.user_id}", json={"role": "viewer"}, headers=guest.headers
    )
    assert demoted.status_code == 200
    last = await client.delete(f"{base}/members/{guest.user_id}", headers=guest.headers)
    assert last.status_code == 422 and last.json()["error"]["code"] == "last_owner"
    activity = await get_json(client, guest, f"{base}/activity")
    actions = {e["action"] for e in activity["items"]}
    assert {"project.created", "member.added", "member.role_changed"} <= actions


async def test_sign_in_password_change_and_lockout(client: httpx.AsyncClient) -> None:
    person: Account = await signup(client, "Sign In")
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": person.email, "password": "wrong-password-1"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "invalid_credentials"
    ok = await client.post("/api/v1/auth/login", json={"email": person.email, "password": PASSWORD})
    assert ok.status_code == 200
    client.cookies.clear()
    changed = await client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "A-new-password-2026"},
        headers=person.headers,
    )
    assert changed.status_code == 200
    client.cookies.clear()
    stale = await client.get("/api/v1/auth/me", headers=person.headers)
    assert stale.status_code == 401, "changing the password signs every session out"
    again = await client.post(
        "/api/v1/auth/login", json={"email": person.email, "password": "A-new-password-2026"}
    )
    assert again.status_code == 200
    client.cookies.clear()


async def test_system_info_probes_and_error_envelope(client: httpx.AsyncClient) -> None:
    info = (await client.get("/api/v1/system/info")).json()
    assert info["extractor"] == {"provider": "local", "model": "rule-based", "deterministic": True}
    assert info["embedding"]["dim"] == 384
    assert info["search_modes"] == ["local", "global", "hybrid"]
    assert (await client.get("/livez")).status_code == 200
    ready = await client.get("/readyz")
    assert ready.status_code == 200 and ready.json()["checks"]["database"] == "ok"
    metrics = (await client.get("/metrics")).text
    assert "graphrag_extractions_total" in metrics and "graphrag_queries_total" in metrics
    missing = await client.get("/api/v1/projects/nope", headers={"x-request-id": "abc123"})
    assert missing.status_code == 401
    body = missing.json()["error"]
    assert body["code"] and body["request_id"] and missing.headers["x-request-id"]


async def test_documents_can_be_downloaded_in_their_original_form(
    client: httpx.AsyncClient,
) -> None:
    owner = await signup(client, "Download Owner")
    base = f"/api/v1/projects/{owner.project}"
    created = await import_texts(
        client,
        owner,
        owner.project,
        [{"type": "text", "title": "Original", "text": "Orion Labs partnered with Nova Systems."}],
    )
    await settle(client)
    document_id = created["created"][0]["id"]
    download = await client.get(f"{base}/documents/{document_id}/file", headers=owner.headers)
    assert download.status_code == 200
    assert download.content == b"Orion Labs partnered with Nova Systems."
