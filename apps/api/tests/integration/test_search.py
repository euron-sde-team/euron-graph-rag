"""Local, global and hybrid search over the demo graph."""

from __future__ import annotations

import re

import httpx
import pytest

from tests.integration.conftest import Graph
from tests.integration.support import bearer, get_json, settle, signup

pytestmark = pytest.mark.integration


async def ask(client: httpx.AsyncClient, graph: Graph, question: str, **body: object) -> dict:
    response = await client.post(
        f"{graph.base}/query",
        json={"question": question, "cache": False, **body},
        headers=graph.owner.headers,
    )
    assert response.status_code == 200, response.text
    result: dict = response.json()
    return result


async def test_local_search_answers_from_cited_passages_and_shows_its_graph(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    result = await ask(client, graph, "Who founded Helios Robotics?", mode="local")
    assert "Mira Okafor" in result["answer"]
    cited = [c for c in result["citations"] if c["cited"]]
    assert cited and all(c["kind"] == "chunk" for c in cited)
    assert {int(n) for n in re.findall(r"\[(\d+)\]", result["answer"])} == {c["n"] for c in cited}
    assert cited[0]["document_title"] == "Helios Robotics: company profile"
    assert cited[0]["document_id"] and cited[0]["location"]
    seeds = [n for n in result["nodes"] if n["role"] == "seed"]
    assert "Helios Robotics" in {n["name"] for n in seeds}
    assert {n["role"] for n in result["nodes"]} == {"seed", "neighbor"}
    assert all(e["source_id"] in {n["id"] for n in result["nodes"]} for e in result["edges"])
    assert [s["name"] for s in result["steps"]][:3] == ["embed", "passages", "seeds"]
    assert result["steps"][-1]["name"] == "total"


async def test_hops_widen_the_neighbourhood(client: httpx.AsyncClient, graph: Graph) -> None:
    near = await ask(client, graph, "Who founded Helios Robotics?", mode="local", hops=0)
    far = await ask(client, graph, "Who founded Helios Robotics?", mode="local", hops=2)
    assert {n["role"] for n in near["nodes"]} == {"seed"}
    assert len(far["nodes"]) > len(near["nodes"])


async def test_global_search_maps_community_reports_into_one_answer(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    result = await ask(
        client, graph, "How is predictive maintenance used in port terminals?", mode="global"
    )
    assert result["answer"]
    assert result["communities"] and all(c["points"] for c in result["communities"])
    assert result["nodes"] == []
    kinds = {c["kind"] for c in result["citations"]}
    assert kinds == {"community"}
    assert any(c["supports"] for c in result["citations"]), "reports point back to chunks"
    assert [s["name"] for s in result["steps"]][1:4] == ["communities", "map", "reduce"]


async def test_a_broad_question_is_answered_from_the_most_central_communities(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    result = await ask(
        client, graph, "What are the main themes across these documents?", mode="global"
    )
    assert "no passages" not in result["answer"]
    assert any("most central" in s["detail"] for s in result["steps"])


async def test_hybrid_search_cites_passages_and_community_reports(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    result = await ask(
        client,
        graph,
        "How does Helios Robotics depend on its suppliers and investors?",
        mode="hybrid",
    )
    assert {c["kind"] for c in result["citations"]} == {"chunk", "community"}
    assert result["nodes"] and result["communities"]


async def test_a_question_the_graph_cannot_answer_says_so(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    result = await ask(client, graph, "What is the airspeed of an unladen swallow?", mode="local")
    assert "no passages" in result["answer"]
    assert not any(c["cited"] for c in result["citations"])


async def test_identical_questions_are_cached_until_the_graph_changes(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    question = "Which companies has Tidewater Capital invested in? (cache check)"
    first = await ask(client, graph, question, mode="local", cache=True)
    second = await ask(client, graph, question, mode="local", cache=True)
    assert first["cached"] is False and second["cached"] is True
    assert second["answer"] == first["answer"] and second["id"] != first["id"]
    # A rebuild replaces the communities, which retires every cached answer of the project.
    await client.post(f"{graph.base}/builds", headers=graph.owner.headers)
    await settle(client)
    third = await ask(client, graph, question, mode="local", cache=True)
    assert third["cached"] is False


async def test_history_lists_questions_and_replays_one(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    result = await ask(client, graph, "Where is Kestrel Analytics based?", mode="local")
    page = await get_json(client, graph.owner, f"{graph.base}/queries", mode="local", limit=5)
    assert page["items"][0]["id"] == result["id"]
    assert page["items"][0]["citation_count"] >= 1
    replay = await get_json(client, graph.owner, f"{graph.base}/queries/{result['id']}")
    assert replay["answer"] == result["answer"]
    assert replay["citations"] == result["citations"]


async def test_questions_are_validated_and_stay_inside_the_project(
    client: httpx.AsyncClient, graph: Graph
) -> None:
    short = await client.post(
        f"{graph.base}/query", json={"question": "hi"}, headers=graph.owner.headers
    )
    assert short.status_code == 422
    stranger = await signup(client, "Stranger")
    other = await client.post(
        f"{graph.base}/query",
        json={"question": "Who founded Helios Robotics?"},
        headers=bearer(stranger.token),
    )
    assert other.status_code == 404
    mine = await client.post(
        f"/api/v1/projects/{stranger.project}/query",
        json={"question": "Who founded Helios Robotics?", "mode": "local"},
        headers=stranger.headers,
    )
    assert mine.status_code == 200
    assert not any(c["cited"] for c in mine.json()["citations"]), "an empty graph cites nothing"
