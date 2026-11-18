from graphrag.ai.llm import Usage
from graphrag.graph.summaries import (
    ChildBrief,
    EntityBrief,
    LlmReporter,
    LocalReporter,
    RelationBrief,
    ReportInput,
    build_reporter,
    template_report,
)


def sample(children: tuple[ChildBrief, ...] = ()) -> ReportInput:
    return ReportInput(
        level=0,
        entities=[
            EntityBrief(
                "e1", "Helios Robotics", "ORGANIZATION", "Helios Robotics builds vehicles.", 9.0, 5
            ),
            EntityBrief("e2", "Mira Okafor", "PERSON", "Mira Okafor is the CEO.", 4.0, 2),
            EntityBrief("e3", "Northgate Sensors", "ORGANIZATION", "", 3.0, 2),
        ],
        relations=[
            RelationBrief(
                "Helios Robotics",
                "Northgate Sensors",
                "ACQUIRED",
                "Helios acquired Northgate. It was in 2024.",
                2.0,
                ("c1",),
            ),
            RelationBrief(
                "Mira Okafor", "Helios Robotics", "LEADS", "Mira leads Helios.", 1.0, ("c2",)
            ),
            RelationBrief("Helios Robotics", "Mira Okafor", "RELATED_TO", "x", 0.4, ("c3",)),
        ],
        children=children,
    )


def test_the_template_report_names_the_leaders_and_cites_relations() -> None:
    report = template_report(sample())
    assert report.title == "Helios Robotics, Mira Okafor and Northgate Sensors"
    assert report.summary.startswith("Helios Robotics builds vehicles.")
    assert "Helios Robotics acquired Northgate Sensors" in report.summary
    assert "3 entities (2 organizations, 1 person) and 3 relationships" in report.summary
    assert report.findings[0].summary == "Helios Robotics acquired Northgate Sensors"
    assert report.findings[0].explanation == "Helios acquired Northgate"
    assert report.findings[0].chunk_ids == ("c1",)


def test_a_parent_report_mentions_its_children() -> None:
    report = template_report(sample((ChildBrief("Hardware", "x"), ChildBrief("People", "y"))))
    assert "It breaks down into Hardware and People." in report.summary


async def test_the_local_reporter_is_the_template() -> None:
    assert await LocalReporter().report(sample()) == template_report(sample())


class FakeClient:
    provider = "fake"
    default_model = "m"

    def __init__(self, reply: str) -> None:
        self.reply = reply

    async def complete(self, messages, *, model=None, max_tokens):  # type: ignore[no-untyped-def]
        return self.reply, Usage()

    async def aclose(self) -> None:
        return None


async def test_a_model_report_keeps_the_model_words_and_attaches_chunks() -> None:
    reply = (
        '{"title": "Helios and its acquisitions", "summary": "Helios grows by buying firms.", '
        '"findings": [{"summary": "Helios Robotics acquired Northgate Sensors", '
        '"explanation": "Bought in 2024."}]}'
    )
    report = await LlmReporter(FakeClient(reply), 400).report(sample())
    assert report.title == "Helios and its acquisitions"
    assert report.findings[0].chunk_ids == ("c1",)


async def test_an_unusable_model_reply_falls_back_to_the_template() -> None:
    report = await LlmReporter(FakeClient("nope"), 400).report(sample())
    assert report == template_report(sample())


def test_the_reporter_follows_the_configured_client() -> None:
    assert isinstance(build_reporter(None, 100), LocalReporter)
    assert isinstance(build_reporter(FakeClient(""), 100), LlmReporter)  # type: ignore[arg-type]
