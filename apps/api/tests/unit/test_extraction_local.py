from graphrag.demo.corpus import NOTES
from graphrag.graph.extraction.contracts import ChunkExtraction, ChunkInput
from graphrag.graph.extraction.local import RuleExtractor, extract_chunks

TYPES = ["PERSON", "ORGANIZATION", "LOCATION", "PRODUCT", "TECHNOLOGY", "EVENT", "CONCEPT", "OTHER"]


def run(*paragraphs: str, allowed: list[str] | None = None) -> ChunkExtraction:
    return extract_chunks([ChunkInput(p) for p in paragraphs], allowed or TYPES)[0]


def types(result: ChunkExtraction) -> dict[str, str]:
    return {e.name: e.type for e in result.entities}


def edges(result: ChunkExtraction) -> set[tuple[str, str, str]]:
    return {(r.source, r.predicate, r.target) for r in result.relations}


def test_entities_are_typed_from_titles_suffixes_places_and_verbs() -> None:
    result = run(
        "Helios Robotics Inc was founded by Dr. Mira Okafor in Lagos. "
        "The Global Logistics Summit was hosted by Port of Rotterdam Authority. "
        "The Atlas Platform is powered by the Orion Engine."
    )
    found = types(result)
    assert found["Mira Okafor"] == "PERSON"
    assert found["Helios Robotics"] == "ORGANIZATION"
    assert found["Lagos"] == "LOCATION"
    assert found["Global Logistics Summit"] == "EVENT"
    assert found["Atlas Platform"] == "PRODUCT"


def test_passive_voice_reverses_the_edge() -> None:
    result = run("Helios Robotics Inc was founded in 2018 by Dr. Mira Okafor.")
    assert ("Mira Okafor", "FOUNDED", "Helios Robotics") in edges(result)


def test_a_verb_after_and_belongs_to_the_subject_of_the_sentence() -> None:
    result = run("Helios acquired Northgate Sensors in 2024 and partnered with Orion Labs.")
    assert ("Helios", "ACQUIRED", "Northgate Sensors") in edges(result)
    assert ("Helios", "PARTNERED_WITH", "Orion Labs") in edges(result)


def test_roles_before_of_become_leadership_and_membership_edges() -> None:
    result = run("Mira Okafor, CEO of Helios Robotics, spoke. Daniel Reyes joined Helios Robotics.")
    assert ("Mira Okafor", "LEADS", "Helios Robotics") in edges(result)
    assert ("Daniel Reyes", "WORKS_AT", "Helios Robotics") in edges(result)


def test_an_unknown_name_takes_the_type_a_relation_requires() -> None:
    result = run("Helios Robotics acquired Northgate Sensors.")
    assert types(result)["Northgate Sensors"] == "ORGANIZATION"


def test_the_document_votes_on_a_type_so_a_short_name_follows_the_long_one() -> None:
    result = run("Helios announced a new product.", "Helios Robotics builds vehicles.")
    assert {e.type for e in result.entities if e.name.startswith("Helios")} == {"ORGANIZATION"}


def test_sentence_openers_and_lone_unknown_capitals_are_not_entities() -> None:
    result = run("However, Researchers met on Monday. The team left.")
    assert result.entities == []


def test_known_concepts_are_extracted_in_any_case() -> None:
    result = run("Predictive maintenance relies on sensor fusion and a Digital Twin.")
    assert {"Predictive maintenance", "Sensor fusion", "Digital twin"} <= set(types(result))


def test_types_outside_the_project_vocabulary_fall_back_or_drop() -> None:
    narrowed = run("Dr. Mira Okafor visited Rotterdam.", allowed=["PERSON", "OTHER"])
    assert types(narrowed)["Mira Okafor"] == "PERSON"
    assert types(narrowed)["Rotterdam"] == "OTHER"
    strict = run("Dr. Mira Okafor visited Rotterdam.", allowed=["PERSON"])
    assert "Rotterdam" not in types(strict)


def test_every_relation_endpoint_is_an_entity_of_the_same_chunk() -> None:
    for note in NOTES:
        for result in extract_chunks([ChunkInput(note.body)], TYPES):
            names = {e.name for e in result.entities}
            for relation in result.relations:
                assert relation.source in names
                assert relation.target in names
                assert relation.source != relation.target


async def test_the_extractor_object_matches_the_function() -> None:
    chunks = [ChunkInput("Mira Okafor founded Helios Robotics Inc in Rotterdam.")]
    direct = extract_chunks(chunks, TYPES)
    assert await RuleExtractor().extract(chunks, TYPES) == direct


def test_the_demo_corpus_yields_a_rich_connected_graph() -> None:
    entities: set[str] = set()
    predicates: set[str] = set()
    for note in NOTES:
        for result in extract_chunks([ChunkInput(note.body)], TYPES):
            entities.update(e.name for e in result.entities)
            predicates.update(r.predicate for r in result.relations)
    assert len(entities) >= 50
    assert {"FOUNDED", "ACQUIRED", "INVESTED_IN", "PARTNERED_WITH", "SUPPLIES"} <= predicates
