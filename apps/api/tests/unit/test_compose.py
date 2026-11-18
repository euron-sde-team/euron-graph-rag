from graphrag.ai.llm import Usage
from graphrag.graph.search.compose import (
    NO_ANSWER,
    digest_answer,
    extractive_answer,
    local_points,
    model_answer,
    model_points,
)
from graphrag.graph.search.contracts import ContextItem


def item(n: int, text: str, score: float = 0.5, kind: str = "chunk") -> ContextItem:
    return ContextItem(n, kind, f"id{n}", f"Source {n}", text, score)  # type: ignore[arg-type]


ITEMS = [
    item(
        1, "Helios Robotics was founded by Mira Okafor in 2018. The weather in Rotterdam is mild."
    ),
    item(2, "Voltaic Cells supplies batteries for the Atlas Platform."),
]


def test_the_extractive_answer_quotes_the_best_sentence_with_its_citation() -> None:
    answer = extractive_answer("Who founded Helios Robotics?", ITEMS)
    assert answer.text == "Helios Robotics was founded by Mira Okafor in 2018 [1]."
    assert answer.cited == [1]
    assert answer.answerer == "local"


def test_sentences_are_read_in_source_order() -> None:
    answer = extractive_answer(
        "Who founded Helios Robotics, and who supplies batteries for the Atlas Platform?", ITEMS
    )
    assert answer.cited == [1, 2]
    assert answer.text.index("[1]") < answer.text.index("[2]")


def test_a_question_nothing_answers_says_so_without_citations() -> None:
    answer = extractive_answer("What is the airspeed of a swallow?", ITEMS)
    assert answer.text == NO_ANSWER
    assert answer.cited == []


def test_headings_are_not_sentences() -> None:
    source = item(
        1, "## Overview\n\nHelios Robotics builds autonomous vehicles for container terminals."
    )
    answer = extractive_answer("What does Helios Robotics build?", [source])
    assert answer.text == "Helios Robotics builds autonomous vehicles for container terminals [1]."


def test_the_digest_opens_every_source_for_broad_questions() -> None:
    answer = digest_answer(ITEMS, per_item=1)
    assert answer.cited == [1, 2]
    assert digest_answer([]).text == NO_ANSWER


def test_local_points_score_sentences_against_the_question() -> None:
    points = local_points("Who founded Helios Robotics?", ITEMS[0])
    assert points[0].text.startswith("Helios Robotics was founded")
    assert points[0].score > 20
    assert local_points("airspeed of a swallow", ITEMS[0]) == []


class FakeClient:
    provider = "fake"
    default_model = "m"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages: list[dict[str, str]] = []

    async def complete(self, messages, *, model=None, max_tokens):  # type: ignore[no-untyped-def]
        self.messages = messages
        return self.reply, Usage(30, 12)

    async def aclose(self) -> None:
        return None


async def test_a_model_answer_keeps_valid_citations_and_drops_invented_ones() -> None:
    client = FakeClient("Mira Okafor founded it [1]. Also something [9].")
    answer = await model_answer(client, "Who founded Helios?", ITEMS, 200)  # type: ignore[arg-type]
    assert answer.text == "Mira Okafor founded it [1]. Also something ."
    assert answer.cited == [1]
    assert (answer.prompt_tokens, answer.completion_tokens) == (30, 12)
    assert "[2] Source 2" in client.messages[1]["content"]


async def test_model_points_are_parsed_clamped_and_filtered() -> None:
    reply = '{"points": [{"description": "A", "score": 140}, {"description": "B", "score": "x"}, {"score": 3}]}'
    points, prompt, completion = await model_points(
        FakeClient(reply),
        "q",
        ITEMS[0],
        100,  # type: ignore[arg-type]
    )
    assert [(p.text, p.score) for p in points] == [("A", 100.0), ("B", 0.0)]
    assert (prompt, completion) == (30, 12)
