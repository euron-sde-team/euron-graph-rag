"""The ingestion pipeline end to end: documents to chunks, entities, relations, communities."""

from __future__ import annotations

import httpx
import pytest

from tests.integration.conftest import Graph
from tests.integration.support import get_json

pytestmark = pytest.mark.integration


async def test_every_note_reaches_ready_with_chunks_and_graph_counts(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    page = await get_json(client, graph.owner, f"{graph.base}/documents", limit=100)
    assert page["total"] == 14
    for document in page["items"]:
        assert document["status"] == "ready", document
        assert document["stage"] == "done"
        assert document["chunk_count"] >= 1
        assert document["entity_count"] >= 3
        assert document["extracted_at"] is not None


async def test_entities_converge_across_documents_and_duplicates_are_merged(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    entities = await get_json(client, graph.owner, f"{graph.base}/graph/entities", limit=200)
    by_name = {e["name"]: e for e in entities["items"]}
    helios = by_name["Helios Robotics"]
    assert helios["type"] == "ORGANIZATION"
    assert helios["mention_count"] >= 10
    # "Helios" on its own was merged into the company and kept as an alias.
    assert "Helios" not in by_name
    assert "Helios" in helios["aliases"]
    assert len({e["key"] if "key" in e else e["name"] for e in entities["items"]}) == len(
        entities["items"]
    )
    assert by_name["Mira Okafor"]["type"] == "PERSON"
    assert by_name["Rotterdam"]["type"] == "LOCATION"


async def test_an_entity_shows_its_relations_and_the_passages_behind_them(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    listing = await get_json(
        client, graph.owner, f"{graph.base}/graph/entities", q="Helios Robotics", limit=5
    )
    entity_id = next(e["id"] for e in listing["items"] if e["name"] == "Helios Robotics")
    detail = await get_json(client, graph.owner, f"{graph.base}/graph/entities/{entity_id}")
    predicates = {
        (n["direction"], n["relation"]["predicate"], n["entity"]["name"])
        for n in detail["neighbors"]
    }
    assert ("out", "ACQUIRED", "Northgate Sensors") in predicates
    assert ("in", "INVESTED_IN", "Tidewater Capital") in predicates
    assert detail["sources"], "an entity always has source passages"
    assert any("Helios" in s["text"] for s in detail["sources"])
    acquired = next(n for n in detail["neighbors"] if n["relation"]["predicate"] == "ACQUIRED")
    assert acquired["quote"]
    assert acquired["chunk_id"]
    assert detail["communities"], "entities belong to communities after the build"


async def test_communities_form_a_hierarchy_with_reports_and_cited_findings(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    tree = await get_json(client, graph.owner, f"{graph.base}/communities/tree")
    levels = sorted({c["level"] for c in tree})
    assert levels[0] == 0 and len(levels) >= 2
    ids = {c["id"] for c in tree}
    assert all(c["parent_id"] in ids for c in tree if c["level"] > 0)
    top = (await get_json(client, graph.owner, f"{graph.base}/communities", level=0))["items"]
    detail = await get_json(client, graph.owner, f"{graph.base}/communities/{top[0]['id']}")
    assert detail["title"] and detail["summary"]
    assert detail["members"], detail
    assert detail["findings"]
    assert any(f["sources"] for f in detail["findings"])


async def test_the_build_is_recorded_and_the_dashboard_reflects_the_graph(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    builds = await get_json(client, graph.owner, f"{graph.base}/builds")
    completed = [b for b in builds["items"] if b["status"] == "completed"]
    assert completed
    stats = completed[0]["stats"]
    assert stats["communities"] >= 3
    assert stats["modularity"] > 0.2
    overview = await get_json(client, graph.owner, f"{graph.base}/overview")
    assert overview["counts"]["documents"] == 14
    assert overview["counts"]["entities"] == stats["entities"]
    assert overview["pipeline"]["failed"] == 0
    assert overview["latest_build"]["status"] == "completed"


async def test_explore_returns_a_consistent_subgraph(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    explored = await get_json(client, graph.owner, f"{graph.base}/graph/explore", limit=40)
    ids = {n["id"] for n in explored["nodes"]}
    assert 10 <= len(ids) <= 40
    assert explored["edges"]
    assert all(e["source"] in ids and e["target"] in ids for e in explored["edges"])
    assert explored["communities"]
    only_people = await get_json(
        client, graph.owner, f"{graph.base}/graph/explore", type="PERSON", limit=40
    )
    assert {n["type"] for n in only_people["nodes"]} == {"PERSON"}


async def test_a_neighbourhood_view_centres_on_the_focus_entity(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    listing = await get_json(
        client, graph.owner, f"{graph.base}/graph/entities", q="Northgate", limit=3
    )
    focus = listing["items"][0]["id"]
    view = await get_json(
        client, graph.owner, f"{graph.base}/graph/explore", focus=focus, hops=1, limit=30
    )
    assert view["nodes"][0]["id"] == focus
    assert view["focus"] == focus
    assert len(view["nodes"]) >= 4


async def test_chunks_of_a_document_are_listed_in_order(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    documents = await get_json(client, graph.owner, f"{graph.base}/documents", limit=1)
    document_id = documents["items"][0]["id"]
    chunks = await get_json(client, graph.owner, f"{graph.base}/documents/{document_id}/chunks")
    assert [c["ordinal"] for c in chunks["items"]] == sorted(c["ordinal"] for c in chunks["items"])
    assert chunks["total"] == documents["items"][0]["chunk_count"]
    detail = await get_json(client, graph.owner, f"{graph.base}/documents/{document_id}")
    assert detail["entities"], "a document lists the entities it mentions"
