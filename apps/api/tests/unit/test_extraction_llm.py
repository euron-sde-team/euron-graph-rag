import pytest

from graphrag.ai.llm import Usage
from graphrag.core.errors import UpstreamError
from graphrag.graph.extraction.contracts import ChunkInput
from graphrag.graph.extraction.llm import (
    LlmExtractor,
    build_messages,
    normalize_predicate,
    parse_reply,
    to_extraction,
)

TYPES = ["PERSON", "ORGANIZATION", "OTHER"]


class FakeClient:
    provider = "fake"
    default_model = "m1"

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    async def complete(
        self, messages: list[dict[str, str]], *, model: str | None = None, max_tokens: int
    ) -> tuple[str, Usage]:
        self.calls.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply, Usage(10, 5)

    async def aclose(self) -> None:
        return None


def test_replies_are_found_inside_prose_and_code_fences() -> None:
    assert parse_reply('Sure! ```json\n{"entities": []}\n``` Hope that helps.') == {"entities": []}
    assert parse_reply('Here: {"a": {"b": "}"}} trailing') == {"a": {"b": "}"}}
    assert parse_reply("no json here") is None
    assert parse_reply('{"broken": ') is None
    assert parse_reply("[1, 2, 3]") is None


def test_predicates_become_upper_snake_case() -> None:
    assert normalize_predicate("partnered with") == "PARTNERED_WITH"
    assert normalize_predicate("  works-at!! ") == "WORKS_AT"
    assert normalize_predicate("") == "RELATED_TO"


def test_normalization_drops_bad_rows_and_fixes_types_and_endpoints() -> None:
    payload = {
        "entities": [
            {"name": "Dr. Mira Okafor", "type": "person", "description": "CEO"},
            {"name": "Helios Robotics Inc", "type": "Company"},
            "not an object",
            {"name": 7},
        ],
        "relations": [
            {"source": "Mira Okafor", "target": "Helios Robotics", "predicate": "leads"},
            {"source": "Mira Okafor", "target": "Mira Okafor", "predicate": "knows"},
            {"source": "Mira Okafor", "target": "Newcomer Co", "predicate": "advises"},
            {"source": "x"},
        ],
    }
    result = to_extraction(payload, TYPES)
    by_name = {e.name: e.type for e in result.entities}
    assert by_name["Mira Okafor"] == "PERSON"
    assert by_name["Helios Robotics"] == "OTHER"  # "Company" is outside the vocabulary
    assert by_name["Newcomer"] == "OTHER"  # an endpoint the model forgot to list
    assert [(r.source, r.predicate, r.target) for r in result.relations] == [
        ("Mira Okafor", "LEADS", "Helios Robotics"),
        ("Mira Okafor", "ADVISES", "Newcomer"),
    ]


def test_the_prompt_names_the_allowed_types_and_the_passage() -> None:
    system, user = build_messages(ChunkInput("Text body.", "Heading"), TYPES)
    assert system["role"] == "system"
    assert "PERSON, ORGANIZATION, OTHER" in user["content"]
    assert "Section: Heading" in user["content"]
    assert "Text body." in user["content"]


async def test_each_chunk_gets_one_completion() -> None:
    reply = '{"entities": [{"name": "Helios", "type": "ORGANIZATION"}], "relations": []}'
    client = FakeClient(reply, reply)
    extractor = LlmExtractor(client, 300)
    results = await extractor.extract([ChunkInput("a"), ChunkInput("b")], TYPES)
    assert len(client.calls) == 2
    assert [e.name for r in results for e in r.entities] == ["Helios", "Helios"]
    assert extractor.name == "fake:m1"


async def test_an_unparsable_reply_falls_back_to_the_rules_for_that_chunk() -> None:
    client = FakeClient("I cannot do that.")
    chunk = ChunkInput("Dr. Mira Okafor founded Helios Robotics Inc in Rotterdam.")
    [result] = await LlmExtractor(client, 300).extract(
        [chunk], ["PERSON", "ORGANIZATION", "LOCATION", "OTHER"]
    )
    assert "Mira Okafor" in {e.name for e in result.entities}


async def test_a_provider_failure_propagates_so_the_job_retries() -> None:
    client = FakeClient(UpstreamError("down"))
    with pytest.raises(UpstreamError):
        await LlmExtractor(client, 300).extract([ChunkInput("text")], TYPES)
