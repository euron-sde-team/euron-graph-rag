"""Documents, entities and builds change the graph; counts stay consistent when they do."""

from __future__ import annotations

import httpx
import pytest

from tests.integration.support import (
    Account,
    get_json,
    import_texts,
    settle,
    signup,
)

pytestmark = pytest.mark.integration

ALPHA = (
    "Orion Labs partnered with Nova Systems in 2024. Orion Labs is headquartered in Lisbon. "
    "Dr. Ana Duarte founded Orion Labs in 2019."
)
BETA = "Orion partnered with Nova Systems on a second project. Nova Systems is based in Madrid."


async def project_with(client: httpx.AsyncClient, *texts: str) -> tuple[Account, str]:
    owner = await signup(client, "Lifecycle Owner")
    await import_texts(
        client,
        owner,
        owner.project,
        [
            {"type": "text", "title": f"Note {i}", "text": text, "external_id": f"note-{i}"}
            for i, text in enumerate(texts)
        ],
    )
    await settle(client)
    return owner, f"/api/v1/projects/{owner.project}"


async def entity_named(client: httpx.AsyncClient, owner: Account, base: str, name: str) -> dict:
    page = await get_json(client, owner, f"{base}/graph/entities", q=name, limit=20)
    return next(e for e in page["items"] if e["name"] == name)


async def test_a_short_name_is_merged_into_the_full_name_by_the_build(
    client: httpx.AsyncClient,
) -> None:
    owner, base = await project_with(client, ALPHA, BETA)
    entities = (await get_json(client, owner, f"{base}/graph/entities", limit=50))["items"]
    names = {e["name"] for e in entities}
    assert {"Orion Labs", "Nova Systems", "Ana Duarte", "Lisbon", "Madrid"} <= names
    assert "Orion" not in names
    orion = next(e for e in entities if e["name"] == "Orion Labs")
    assert "Orion" in orion["aliases"]
    detail = await get_json(client, owner, f"{base}/graph/entities/{orion['id']}")
    partners = [n for n in detail["neighbors"] if n["relation"]["predicate"] == "PARTNERED_WITH"]
    assert len(partners) == 1, "both documents evidence one relation, not two"
    assert partners[0]["relation"]["evidence_count"] == 2
    assert partners[0]["relation"]["weight"] == 2.0


async def test_deleting_a_document_removes_what_only_it_supported(
    client: httpx.AsyncClient,
) -> None:
    owner, base = await project_with(client, ALPHA, BETA)
    documents = (await get_json(client, owner, f"{base}/documents"))["items"]
    beta = next(d for d in documents if d["external_id"] == "note-1")
    before = await get_json(client, owner, f"{base}/overview")
    response = await client.delete(f"{base}/documents/{beta['id']}", headers=owner.headers)
    assert response.status_code == 204
    await settle(client)
    after = await get_json(client, owner, f"{base}/overview")
    assert after["counts"]["documents"] == before["counts"]["documents"] - 1
    assert after["graph_version"] > before["graph_version"]
    names = {
        e["name"]
        for e in (await get_json(client, owner, f"{base}/graph/entities", limit=50))["items"]
    }
    assert "Madrid" not in names, "only the deleted note mentioned Madrid"
    assert "Lisbon" in names
    nova = await entity_named(client, owner, base, "Nova Systems")
    detail = await get_json(client, owner, f"{base}/graph/entities/{nova['id']}")
    assert all(n["relation"]["evidence_count"] == 1 for n in detail["neighbors"])


async def test_reprocessing_a_document_replaces_its_contribution(
    client: httpx.AsyncClient,
) -> None:
    owner, base = await project_with(client, ALPHA)
    document = (await get_json(client, owner, f"{base}/documents"))["items"][0]
    before = await entity_named(client, owner, base, "Orion Labs")
    response = await client.post(
        f"{base}/documents/{document['id']}/reprocess", headers=owner.headers
    )
    assert response.status_code == 200
    await settle(client)
    after = await entity_named(client, owner, base, "Orion Labs")
    assert after["mention_count"] == before["mention_count"]
    assert after["id"] == before["id"] or after["name"] == before["name"]
    reread = await get_json(client, owner, f"{base}/documents/{document['id']}")
    assert reread["status"] == "ready"
    assert reread["entity_count"] == document["entity_count"]


async def test_the_same_text_is_not_ingested_twice(client: httpx.AsyncClient) -> None:
    owner, _ = await project_with(client, ALPHA)
    again = await import_texts(
        client,
        owner,
        owner.project,
        [{"type": "text", "title": "Copy", "text": ALPHA, "external_id": "copy"}],
    )
    assert again["created"] == [] and len(again["duplicates"]) == 1


async def test_entities_can_be_renamed_merged_and_deleted_by_hand(
    client: httpx.AsyncClient,
) -> None:
    owner, base = await project_with(
        client, "Aurora Dynamics acquired Boreal Dynamics. Dr. Ana Duarte founded Boreal Dynamics."
    )
    aurora = await entity_named(client, owner, base, "Aurora Dynamics")
    boreal = await entity_named(client, owner, base, "Boreal Dynamics")

    taken = await client.patch(
        f"{base}/graph/entities/{aurora['id']}",
        json={"name": "Boreal Dynamics"},
        headers=owner.headers,
    )
    assert taken.status_code == 422 and taken.json()["error"]["code"] == "name_taken"
    renamed = await client.patch(
        f"{base}/graph/entities/{aurora['id']}",
        json={"name": "Aurora Group", "description": "A holding company."},
        headers=owner.headers,
    )
    assert renamed.status_code == 200 and renamed.json()["aliases"] == ["Aurora Dynamics"]

    merged = await client.post(
        f"{base}/graph/merge",
        json={"survivor_id": boreal["id"], "entity_ids": [aurora["id"], boreal["id"]]},
        headers=owner.headers,
    )
    assert merged.status_code == 200 and merged.json()["merged"] == 1
    survivor = await get_json(client, owner, f"{base}/graph/entities/{boreal['id']}")
    assert {"Aurora Group", "Aurora Dynamics"} <= set(survivor["aliases"])
    assert all(n["entity"]["id"] != boreal["id"] for n in survivor["neighbors"]), "no self loop"
    gone = await client.get(f"{base}/graph/entities/{aurora['id']}", headers=owner.headers)
    assert gone.status_code == 404

    ana = await entity_named(client, owner, base, "Ana Duarte")
    assert (
        await client.delete(f"{base}/graph/entities/{ana['id']}", headers=owner.headers)
    ).status_code == 204
    listing = await get_json(client, owner, f"{base}/graph/entities", limit=50)
    assert "Ana Duarte" not in {e["name"] for e in listing["items"]}


async def test_graph_settings_narrow_what_new_documents_extract(
    client: httpx.AsyncClient,
) -> None:
    owner = await signup(client, "Settings Owner")
    base = f"/api/v1/projects/{owner.project}"
    updated = await client.patch(
        base,
        json={"settings": {"entity_types": ["person", "other"], "auto_build": False}},
        headers=owner.headers,
    )
    assert updated.status_code == 200
    assert updated.json()["settings"]["entity_types"] == ["PERSON", "OTHER"]
    await import_texts(
        client,
        owner,
        owner.project,
        [{"type": "text", "title": "N", "text": ALPHA, "external_id": "n"}],
    )
    await settle(client)
    types = {
        e["type"]
        for e in (await get_json(client, owner, f"{base}/graph/entities", limit=50))["items"]
    }
    assert types <= {"PERSON", "OTHER"} and "PERSON" in types
    builds = await get_json(client, owner, f"{base}/builds")
    assert builds["total"] == 0, "auto_build is off: nothing builds until asked"
    assert (await client.post(f"{base}/builds", headers=owner.headers)).status_code == 202
    await settle(client)
    builds = await get_json(client, owner, f"{base}/builds")
    assert builds["items"][0]["status"] == "completed" and builds["items"][0]["trigger"] == "manual"


async def test_the_duplicate_preview_lists_what_a_build_would_merge(
    client: httpx.AsyncClient,
) -> None:
    owner = await signup(client, "Preview Owner")
    base = f"/api/v1/projects/{owner.project}"
    await client.patch(base, json={"settings": {"auto_build": False}}, headers=owner.headers)
    await import_texts(
        client,
        owner,
        owner.project,
        [
            {"type": "text", "title": "A", "text": ALPHA, "external_id": "a"},
            {"type": "text", "title": "B", "text": BETA, "external_id": "b"},
        ],
    )
    await settle(client)
    groups = await get_json(client, owner, f"{base}/graph/duplicates")
    assert [(g["survivor"]["name"], [m["name"] for m in g["members"]]) for g in groups] == [
        ("Orion Labs", ["Orion"])
    ]
    assert groups[0]["members"][0]["reason"] == "containment"
