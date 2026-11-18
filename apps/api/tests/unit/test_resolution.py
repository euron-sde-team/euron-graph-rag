from graphrag.graph.resolution import Candidate, compatible, find_duplicates, merged_type


def c(
    i: int, name: str, kind: str = "ORGANIZATION", mentions: int = 1, *aliases: str
) -> Candidate[int]:
    return Candidate(i, name, kind, mentions, aliases)


def groups(*candidates: Candidate[int]) -> dict[int, dict[int, str]]:
    return {g.survivor: g.members for g in find_duplicates(candidates)}


def test_a_short_name_merges_into_the_one_longer_name_that_starts_with_it() -> None:
    found = groups(c(1, "Helios Robotics", mentions=9), c(2, "Helios", "OTHER"), c(3, "Northgate"))
    assert found == {1: {2: "containment"}}


def test_a_surname_matches_the_end_of_a_person_name() -> None:
    found = groups(c(1, "Mira Okafor", "PERSON", 5), c(2, "Okafor", "PERSON"))
    assert found == {1: {2: "containment"}}


def test_an_ambiguous_short_name_is_left_alone() -> None:
    found = groups(
        c(1, "Meridian Port Systems", "ORGANIZATION", 4),
        c(2, "Meridian Hauler", "OTHER", 2),
        c(3, "Meridian", "OTHER", 1),
    )
    assert 3 not in {m for members in found.values() for m in members}


def test_incompatible_types_never_merge() -> None:
    assert groups(c(1, "Atlas Platform", "PRODUCT"), c(2, "Atlas", "ORGANIZATION")) == {}
    assert not compatible("PERSON", "LOCATION")
    assert compatible("PERSON", "OTHER")


def test_an_acronym_merges_into_the_name_it_abbreviates() -> None:
    found = groups(c(1, "Helios Robotics Institute", mentions=3), c(2, "HRI", "OTHER"))
    assert found == {1: {2: "acronym"}}


def test_near_identical_spellings_merge() -> None:
    found = groups(c(1, "Northgate Sensors", mentions=4), c(2, "Northgate Sensers"))
    assert found == {1: {2: "fuzzy"}}


def test_a_known_alias_merges_even_when_the_names_differ() -> None:
    found = groups(c(1, "Kestrel Analytics", "ORGANIZATION", 5, "KA Software"), c(2, "KA Software"))
    assert found == {1: {2: "alias"}}


def test_merging_is_transitive_and_the_most_mentioned_survives() -> None:
    found = groups(
        c(1, "Helios", "OTHER", 1),
        c(2, "Helios Robotics", "ORGANIZATION", 7),
        c(3, "Helios Robotic", "ORGANIZATION", 2),
    )
    assert list(found) == [2]
    assert set(found[2]) == {1, 3}


def test_a_vague_survivor_takes_the_specific_type_of_its_members() -> None:
    assert merged_type("OTHER", ["ORGANIZATION"]) == "ORGANIZATION"
    assert merged_type("PERSON", ["ORGANIZATION"]) == "PERSON"


def test_no_duplicates_means_no_groups() -> None:
    assert find_duplicates([c(1, "Voltaic Cells"), c(2, "Lumen Energy")]) == []
